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
# THUẬT TOÁN NESTING (SẮP XẾP VẬT TƯ)
# ==========================================
def apply_nesting_to_parts(parts, sheet_w, sheet_h, margin):
    """Sắp xếp lại tọa độ X, Y của các chi tiết để tối ưu khổ phôi"""
    nested_parts = []
    cur_x = margin
    cur_y = margin
    row_max_h = 0

    for part in parts:
        # Lấy danh sách điểm của chi tiết
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

        # Nếu vượt quá chiều rộng tấm phôi -> Xuống dòng mới
        if cur_x + p_w + margin > sheet_w:
            cur_x = margin
            cur_y += row_max_h + margin
            row_max_h = 0

        # Dịch chuyển gốc tọa độ chi tiết về vị trí xếp mới
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
# GIAO DIỆN CHÍNH
# ==========================================
st.title("🛠️ CAM DXF Cutter Control Dashboard - Pro Edition")

col_sidebar, col_display = st.columns([1, 2.5])

# --- CỘT TRÁI: CẤU HÌNH ---
with col_sidebar:
    st.header("⚙️ Cấu hình vận hành")
    uploaded_file = st.file_uploader("📂 Tải File DXF Bản Vẽ", type=["dxf"])

    with st.expander("🛠️ Thông số cắt", expanded=True):
        tool_dia = st.number_input("Đường kính dao (mm):", value=3.0, step=0.1)
        feed_rate = st.number_input("Tốc độ cắt F (mm/phút):", value=1200, step=100)
        cut_z = st.number_input("Độ sâu cắt Z (mm):", value=-2.0, step=0.5)
        safe_z = st.number_input("Chiều cao an toàn Safe Z (mm):", value=5.0, step=1.0)
        lead_len = st.number_input("Chiều dài đường mồi (mm):", value=5.0, step=0.5)
        
        mode_option = st.selectbox(
            "Chế độ bù dao:",
            ["Bù bán kính dao", "Không bù dao (Chạy trên nét)"]
        )
        mode_str = "compensation" if mode_option == "Bù bán kính dao" else "online"

    with st.expander("🧩 Kích thước khổ phôi (Nesting)", expanded=True):
        sheet_w = st.number_input("Rộng phôi X (mm):", value=600, step=50)
        sheet_h = st.number_input("Dài phôi Y (mm):", value=400, step=50)
        part_margin = st.number_input("Khoảng cách giữa chi tiết (mm):", value=5.0, step=1.0)

    with st.expander("💰 Cấu hình báo giá", expanded=False):
        g00_speed = st.number_input("Tốc độ G00 (mm/phút):", value=5000, step=500)
        cost_per_minute = st.number_input("Chi phí máy (VNĐ/phút):", value=2000, step=500)

# Khởi tạo trạng thái Nesting
if "is_nested" not in st.session_state:
    st.session_state.is_nested = False

# --- CỘT PHẢI: XỬ LÝ ---
with col_display:
    if uploaded_file is not None:
        try:
            detected_parts = process_dxf_file(uploaded_file.getvalue(), uploaded_file.name)
            st.success(f"✅ Đã nạp file thành công: **{uploaded_file.name}** | Tìm thấy **{len(detected_parts)}** chi tiết kín.")

            # 🛠️ NÚT SẮP XẾP & CHỌN THỨ TỰ ĐƯỢC ĐẶT NGAY ĐÂY
            st.subheader("🔄 Quản lý & Sắp xếp vị trí")
            
            col_sel, col_btn1, col_btn2 = st.columns([2, 1, 1])
            
            with col_sel:
                part_map = {f"Chi tiết #{p['id']}": p for p in detected_parts}
                selected_names = st.multiselect(
                    "Chọn danh sách chi tiết cắt:",
                    options=list(part_map.keys()),
                    default=list(part_map.keys()),
                    label_visibility="collapsed"
                )
            
            final_ordered_parts = [part_map[name] for name in selected_names] if selected_names else detected_parts

            with col_btn1:
                # 🧩 NÚT SẮP XẾP TỐI ƯU VẬT TƯ (BẤM VÀO ĐÂY)
                if st.button("🧩 Tối ưu xếp phôi", use_container_width=True, type="primary"):
                    st.session_state.is_nested = True
                    st.toast("✅ Đã tự động sắp xếp tối ưu vị trí trên tấm phôi!", icon="🧩")

            with col_btn2:
                if st.button("↩️ Khôi phục vị trí gốc", use_container_width=True):
                    st.session_state.is_nested = False
                    st.toast("🔄 Đã quay lại vị trí bản vẽ gốc.")

            # Áp dụng thuật toán Nesting nếu bấm nút
            if st.session_state.is_nested:
                parts_to_process = apply_nesting_to_parts(final_ordered_parts, sheet_w, sheet_h, part_margin)
                st.info(f"📐 Đang hiển thị vị trí đã TỐI ƯU XẾP PHÔI (Khổ phôi: {sheet_w}x{sheet_h} mm)")
            else:
                parts_to_process = final_ordered_parts

            # Tạo đường chạy dao (Toolpath)
            generator = ToolpathGenerator(
                tool_diameter=tool_dia,
                feed_rate=feed_rate,
                lead_length=lead_len
            )
            raw_paths = generator.generate(parts_to_process, mode=mode_str)

            optimized_paths = []
            for item in raw_paths:
                for sub in item["coords"]:
                    optimized_paths.append({
                        "type": item.get("type", "G1"),
                        "feed": item.get("feed", feed_rate),
                        "points": sub
                    })

            # MÔ PHỎNG VẼ PLOTLY
            fig = go.Figure()

            # Nếu đang ở chế độ Nesting -> Vẽ thêm Khung Tấm Phôi
            if st.session_state.is_nested:
                fig.add_trace(go.Scatter(
                    x=[0, sheet_w, sheet_w, 0, 0],
                    y=[0, 0, sheet_h, sheet_h, 0],
                    mode="lines",
                    name="Tấm phôi gốc",
                    line=dict(color="red", width=2, dash="dash")
                ))

            for idx, path in enumerate(optimized_paths):
                xs, ys = zip(*path["points"])
                fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=f"Cắt #{idx+1}"))

            fig.update_layout(
                xaxis_title="X (mm)", yaxis_title="Y (mm)", 
                height=480, yaxis=dict(scaleanchor="x"),
                margin=dict(l=10, r=10, t=20, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)

            # XUẤT G-CODE NẰM NGAY DƯỚI ĐỒ THỊ
            st.subheader("💾 Xuất file G-Code")
            gcode_lines = ["G21", "G90", f"G0 Z{safe_z}"]
            for path in optimized_paths:
                pts = path["points"]
                gcode_lines.append(f"G0 X{pts[0][0]:.3f} Y{pts[0][1]:.3f}")
                gcode_lines.append(f"G1 Z{cut_z:.3f} F300")
                for x, y in pts[1:]:
                    gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f} F{feed_rate}")
                gcode_lines.append(f"G0 Z{safe_z}")
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

        except Exception as e:
            st.error(f"Lỗi xử lý: {e}")
    else:
        st.info("👋 Vui lòng tải file DXF ở cột bên trái để bắt đầu.")
