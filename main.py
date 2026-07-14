import streamlit as st
import os
import math
import tempfile
import plotly.graph_objects as go

from dxf_reader import DXFReader
from part_detector import PartDetector
from toolpath import ToolpathGenerator
from gcode_writer import GCodeWriter

# ==========================================
# CẤU HÌNH TRANG & CACHE
# ==========================================
st.set_page_config(page_title="CAM DXF Control Pro", layout="wide")

@st.cache_data(show_spinner="Đang phân tích file DXF...")
def process_dxf_file(file_bytes, filename):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
        tmp_file.write(file_bytes)
        tmp_path = tmp_file.name

    try:
        reader = DXFReader(tmp_path)
        raw_lines = reader.read_entities()
        detector = PartDetector()
        detected_parts = detector.detect_parts(raw_lines)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
    return detected_parts

# ==========================================
# THUẬT TOÁN NESTING
# ==========================================
def apply_nesting_to_parts(parts, sheet_w, sheet_h, margin):
    nested_parts = []
    cur_x = margin
    cur_y = margin
    row_max_h = 0

    for part in parts:
        pts = part.get("points", [])
        if not pts:
            nested_parts.append(part)
            continue

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        p_w = max_x - min_x
        p_h = max_y - min_y

        if cur_x + p_w + margin > sheet_w:
            cur_x = margin
            cur_y += row_max_h + margin
            row_max_h = 0

        dx = cur_x - min_x
        dy = cur_y - min_y

        new_pts = [(x + dx, y + dy) for x, y in pts]
        
        new_part = part.copy()
        new_part["points"] = new_pts
        nested_parts.append(new_part)

        cur_x += p_w + margin
        row_max_h = max(row_max_h, p_h)

    return nested_parts

# ==========================================
# THUẬT TOÁN DỊCH CHUYỂN GỐC TỌA ĐỘ (WORK ZERO)
# ==========================================
def apply_work_zero_shift(paths, zero_position, is_nested, sheet_w, sheet_h):
    """
    Dịch chuyển tọa độ của toàn bộ Toolpath dựa theo gốc Work Zero được chọn.
    """
    if not paths:
        return paths

    # 1. TÍNH BIA (BOUNDING BOX) CỦA TOÀN BỘ SẢN PHẨM HOẶC TẤM PHÔI
    if is_nested:
        min_x, max_x = 0, sheet_w
        min_y, max_y = 0, sheet_h
    else:
        all_x = [p[0] for path in paths for p in path["points"]]
        all_y = [p[1] for path in paths for p in path["points"]]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

    # 2. XÁC ĐỊNH TỌA ĐỘ GỐC MỚI (OFFSET X, Y)
    offset_x, offset_y = 0.0, 0.0

    if zero_position == "Bottom-Left (Góc dưới - Trái) [Default]":
        offset_x, offset_y = min_x, min_y
    elif zero_position == "Center (Tâm phôi)":
        offset_x, offset_y = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0
    elif zero_position == "Top-Left (Góc trên - Trái)":
        offset_x, offset_y = min_x, max_y
    elif zero_position == "Bottom-Right (Góc dưới - Phải)":
        offset_x, offset_y = max_x, min_y
    elif zero_position == "Top-Right (Góc trên - Phải)":
        offset_x, offset_y = max_x, max_y
    # Nếu chọn "Gốc bản vẽ DXF (Original DXF Zero)" thì offset_x = 0, offset_y = 0

    # 3. DỊCH CHUYỂN TẤT CẢ ĐIỂM
    shifted_paths = []
    for path in paths:
        new_pts = [(x - offset_x, y - offset_y) for x, y in path["points"]]
        new_path = path.copy()
        new_path["points"] = new_pts
        shifted_paths.append(new_path)

    return shifted_paths, offset_x, offset_y

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
st.title("🛠️ CAM DXF Cutter Control Dashboard - Pro Edition")

col_sidebar, col_display = st.columns([1, 2.5])

# --- CỘT TRÁI: CẤU HÌNH ---
with col_sidebar:
    st.header("⚙️ Cấu hình vận hành")
    uploaded_file = st.file_uploader("📂 Tải File DXF Bản Vẽ", type=["dxf"])

    # 🎯 THIẾT LẬP GỐC TỌA ĐỘ WORK ZERO (MỚI BỔ SUNG)
    with st.expander("🎯 Thiết lập Gốc tọa độ (Work Zero - G54)", expanded=True):
        zero_option = st.selectbox(
            "Chọn vị trí đặt gốc 0 (X0, Y0):",
            [
                "Bottom-Left (Góc dưới - Trái) [Default]",
                "Center (Tâm phôi)",
                "Top-Left (Góc trên - Trái)",
                "Bottom-Right (Góc dưới - Phải)",
                "Top-Right (Góc trên - Phải)",
                "Gốc bản vẽ DXF (Original DXF Zero)"
            ]
        )

    with st.expander("🛠️ Thông số cắt", expanded=False):
        tool_dia = st.number_input("Đường kính dao (mm):", value=3.0, step=0.1)
        feed_rate = st.number_input("Tốc độ cắt F (mm/phút):", value=1200, step=100)
        cut_z = st.number_input("Độ sâu cắt Z (mm):", value=-2.0, step=0.5)
        safe_z = st.number_input("Chiều cao an toàn Safe Z (mm):", value=5.0, step=1.0)
        lead_len = st.number_input("Chiều dài đường mồi (mm):", value=5.0, step=0.5)
        
        mode_option = st.selectbox("Chế độ bù dao:", ["Bù bán kính dao", "Không bù dao (Chạy trên nét)"])
        mode_str = "compensation" if mode_option == "Bù bán kính dao" else "online"

    with st.expander("🧩 Kích thước khổ phôi (Nesting)", expanded=False):
        sheet_w = st.number_input("Rộng phôi X (mm):", value=600, step=50)
        sheet_h = st.number_input("Dài phôi Y (mm):", value=400, step=50)
        part_margin = st.number_input("Khoảng cách giữa chi tiết (mm):", value=5.0, step=1.0)

    with st.expander("💰 Cấu hình báo giá", expanded=False):
        g00_speed = st.number_input("Tốc độ G00 (mm/phút):", value=5000, step=500)
        cost_per_minute = st.number_input("Chi phí máy (VNĐ/phút):", value=2000, step=500)

if "is_nested" not in st.session_state:
    st.session_state.is_nested = False

# --- CỘT PHẢI: XỬ LÝ ---
with col_display:
    if uploaded_file is not None:
        try:
            detected_parts = process_dxf_file(uploaded_file.getvalue(), uploaded_file.name)
            st.success(f"✅ Đã nạp file: **{uploaded_file.name}** | Tìm thấy **{len(detected_parts)}** chi tiết.")

            # Sắp xếp & chọn chi tiết
            st.subheader("🔄 Quản lý & Tối ưu vị trí")
            col_sel, col_btn1, col_btn2 = st.columns([2, 1, 1])
            
            with col_sel:
                part_map = {f"Chi tiết #{p['id']}": p for p in detected_parts}
                selected_names = st.multiselect("Chọn chi tiết:", options=list(part_map.keys()), default=list(part_map.keys()), label_visibility="collapsed")
            
            final_ordered_parts = [part_map[name] for name in selected_names] if selected_names else detected_parts

            with col_btn1:
                if st.button("🧩 Tối ưu xếp phôi", use_container_width=True, type="primary"):
                    st.session_state.is_nested = True
                    st.toast("✅ Đã tự động xếp vị trí trên tấm phôi!", icon="🧩")

            with col_btn2:
                if st.button("↩️ Khôi phục gốc", use_container_width=True):
                    st.session_state.is_nested = False
                    st.toast("🔄 Đã quay lại vị trí bản vẽ gốc.")

            # Xử lý Nesting
            parts_to_process = apply_nesting_to_parts(final_ordered_parts, sheet_w, sheet_h, part_margin) if st.session_state.is_nested else final_ordered_parts

            # Tạo Toolpath ban đầu
            generator = ToolpathGenerator(tool_diameter=tool_dia, feed_rate=feed_rate, lead_length=lead_len)
            raw_paths = generator.generate(parts_to_process, mode=mode_str)

            raw_optimized_paths = []
            for item in raw_paths:
                for sub in item["coords"]:
                    raw_optimized_paths.append({
                        "type": item.get("type", "G1"),
                        "feed": item.get("feed", feed_rate),
                        "points": sub
                    })

            # 🎯 ÁP DỤNG DỊCH CHUYỂN WORK ZERO
            optimized_paths, shift_x, shift_y = apply_work_zero_shift(
                raw_optimized_paths, zero_option, st.session_state.is_nested, sheet_w, sheet_h
            )

            # MÔ PHỎNG VẼ PLOTLY (CÓ ĐÁNH DẤU GỐC TỌA ĐỘ X0 Y0)
            fig = go.Figure()

            # 1. Đánh dấu điểm Work Zero (0,0) màu Đỏ
            fig.add_trace(go.Scatter(
                x=[0], y=[0],
                mode="markers+text",
                marker=dict(color="red", size=14, symbol="x-open-dot", line=dict(width=2)),
                text=["📍 Work Zero (0,0)"],
                textposition="top right",
                name="Gốc Work Zero (G54)"
            ))

            # 2. Vẽ khung tấm phôi nếu đang Nesting
            if st.session_state.is_nested:
                fig.add_trace(go.Scatter(
                    x=[0 - shift_x, sheet_w - shift_x, sheet_w - shift_x, 0 - shift_x, 0 - shift_x],
                    y=[0 - shift_y, 0 - shift_y, sheet_h - shift_y, sheet_h - shift_y, 0 - shift_y],
                    mode="lines",
                    name="Khung phôi",
                    line=dict(color="orange", width=1.5, dash="dash")
                ))

            # 3. Vẽ đường cắt
            for idx, path in enumerate(optimized_paths):
                xs, ys = zip(*path["points"])
                fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=f"Cắt #{idx+1}"))

            fig.update_layout(
                xaxis_title="X (mm)", yaxis_title="Y (mm)", 
                height=480, yaxis=dict(scaleanchor="x"),
                margin=dict(l=10, r=10, t=20, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)

            # XUẤT G-CODE CÓ ĐẦY ĐỦ THÔNG TIN WORK ZERO
            st.subheader("💾 Xuất file G-Code")
            
            gcode_lines = [
                f"(----------------------------------------)",
                f"(PROGRAM NAME : {uploaded_file.name})",
                f"(WORK ZERO POS: {zero_option})",
                f"(SAFE Z       : {safe_z} mm)",
                f"(CUT Z        : {cut_z} mm)",
                f"(TOOL DIA     : {tool_dia} mm)",
                f"(----------------------------------------)",
                "G21 (Units: mm)",
                "G90 (Absolute coordinates)",
                "G54 (Select Work Coordinate System)",
                f"G0 Z{safe_z:.3f}"
            ]

            for path in optimized_paths:
                pts = path["points"]
                gcode_lines.append(f"G0 X{pts[0][0]:.3f} Y{pts[0][1]:.3f}")
                gcode_lines.append(f"G1 Z{cut_z:.3f} F300")
                for x, y in pts[1:]:
                    gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f} F{feed_rate}")
                gcode_lines.append(f"G0 Z{safe_z:.3f}")
            
            gcode_lines.append("M30 (End of Program)")
            gcode_text = "\n".join(gcode_lines)

            col_down, col_info = st.columns([1, 2])
            with col_down:
                out_name = os.path.splitext(uploaded_file.name)[0] + ("_nested.nc" if st.session_state.is_nested else ".nc")
                st.download_button(
                    label="📥 Tải File G-Code (.nc)",
                    data=gcode_text,
                    file_name=out_name,
                    mime="text/plain",
                    use_container_width=True,
                    type="primary"
                )
            with col_info:
                st.caption(f"📌 **Gốc tọa độ hiện tại:** `{zero_option}` | Tọa độ điểm bắt đầu: `X0 Y0` được đánh dấu chữ **X đỏ** trên bản vẽ.")

        except Exception as e:
            st.error(f"Lỗi xử lý: {e}")
    else:
        st.info("👋 Vui lòng tải file DXF ở cột bên trái để bắt đầu.")
