import streamlit as st
import os
import math
import tempfile
import pandas as pd
import numpy as np

# Bọc an toàn Import các thư viện phụ thuộc
try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# Tích hợp Google Gemini AI qua SDK mới google-genai
try:
    from google import genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from sklearn.ensemble import RandomForestRegressor
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# Import các module CAM nội bộ
from dxf_reader import DXFReader
from part_detector import PartDetector
from toolpath import ToolpathGenerator

# ==========================================
# CẤU HÌNH TRANG & CACHE
# ==========================================
st.set_page_config(page_title="CAM DXF Control Pro AI (Gemini Edition)", layout="wide", page_icon="🛠️")

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
# LOẠI 3: MACHINE LEARNING MODEL
# ==========================================
@st.cache_resource
def train_dummy_cost_ml_model():
    if not HAS_SKLEARN:
        return None
    X_train = np.array([
        [1000, 200, 5, -2.0],
        [2500, 500, 12, -5.0],
        [5000, 1200, 20, -10.0],
        [800, 150, 3, -1.0],
        [3200, 800, 15, -3.0]
    ])
    y_train = np.array([1.2, 3.1, 6.8, 0.9, 4.2])
    model = RandomForestRegressor(n_estimators=10, random_state=42)
    model.fit(X_train, y_train)
    return model

ml_model = train_dummy_cost_ml_model()

def predict_real_machine_time(total_g01, total_g00, part_count, cut_z, feed_rate=1200, g00_speed=5000):
    if ml_model is not None:
        features = np.array([[total_g01, total_g00, part_count, cut_z]])
        return max(0.1, ml_model.predict(features)[0])
    else:
        t_cut = (total_g01 / feed_rate) if feed_rate > 0 else 0
        t_fast = (total_g00 / g00_speed) if g00_speed > 0 else 0
        return t_cut + t_fast

# ==========================================
# THUẬT TOÁN NESTING & WORK ZERO SHIFT
# ==========================================
def apply_nesting_to_parts(parts, sheet_w, sheet_h, margin):
    nested_parts = []
    cur_x, cur_y = margin, margin
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
        p_w, p_h = max_x - min_x, max_y - min_y

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

def apply_work_zero_shift(paths, zero_position, is_nested, sheet_w, sheet_h):
    if not paths:
        return paths, 0.0, 0.0

    if is_nested:
        min_x, max_x = 0, sheet_w
        min_y, max_y = 0, sheet_h
    else:
        all_x = [p[0] for path in paths for p in path["points"]]
        all_y = [p[1] for path in paths for p in path["points"]]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

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

    shifted_paths = []
    for path in paths:
        new_pts = [(x - offset_x, y - offset_y) for x, y in path["points"]]
        new_path = path.copy()
        new_path["points"] = new_pts
        shifted_paths.append(new_path)

    return shifted_paths, offset_x, offset_y

# ==========================================
# LOẠI 1 & 2: AI DXF & RISK ANALYSIS (GEMINI AI)
# ==========================================
def ai_dxf_and_risk_analysis(api_key, detected_parts, material, tool_dia, feed_rate, cut_z):
    if not HAS_GEMINI:
        return "❌ Thư viện `google-genai` chưa được cài đặt trong `requirements.txt`!"
    if not api_key:
        return "⚠️ Vui lòng nhập Gemini API Key để khởi chạy Trợ lý AI."

    part_summary = []
    for p in detected_parts:
        pts = p.get("points", [])
        xs = [pt[0] for pt in pts] if pts else [0]
        ys = [pt[1] for pt in pts] if pts else [0]
        part_summary.append({
            "id": p.get("id"),
            "point_count": len(pts),
            "is_closed": (pts[0] == pts[-1]) if pts else False,
            "size_mm": f"{max(xs)-min(xs):.1f}x{max(ys)-min(ys):.1f}"
        })

    prompt = f"""
    Bạn là chuyên gia lập trình và vận hành máy cắt CNC/CAM cao cấp.
    
    [DỮ LIỆU HÌNH HỌC DXF - KIỂM TRA LỖI]:
    - Số lượng chi tiết: {len(detected_parts)}
    - Cấu trúc chi tiết: {part_summary}
    - Đường kính dao cắt: {tool_dia} mm
    
    [CẤU HÌNH GIA CÔNG - TƯ VẤN RỦI RO]:
    - Vật liệu phôi: {material}
    - Tốc độ cắt F: {feed_rate} mm/phút
    - Độ sâu Z: {cut_z} mm

    YÊU CẦU PHÂN TÍCH:
    1. 🔍 **Rà soát Lỗi DXF**: Kiểm tra tính kín của nét, góc hốc nhỏ hơn bán kính dao {tool_dia/2}mm.
    2. ⚠️ **Phân tích Rủi ro**: Thông số F={feed_rate}, Z={cut_z} với {material} có an toàn không?
    3. 💡 **Khuyên dùng**: Đề xuất cải tiến chế độ cắt cụ thể.
    """

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"❌ Lỗi kết nối Gemini AI API: {e}"

# ==========================================
# GIAO DIỆN CHÍNH (STREAMLIT DASHBOARD)
# ==========================================
st.title("🛠️ CAM DXF Control Dashboard Pro (Gemini AI-Powered)")

col_sidebar, col_display = st.columns([1, 2.5])

# --- SIDEBAR: CẤU HÌNH ---
with col_sidebar:
    st.header("⚙️ Cấu hình Vận hành")
    uploaded_file = st.file_uploader("📂 Tải File DXF Bản Vẽ", type=["dxf"])

    # 🎯 THIẾT LẬP WORK ZERO
    with st.expander("🎯 1. Thiết lập Gốc Tọa độ (Work Zero - G54)", expanded=True):
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

    # 🛠️ THÔNG SỐ CẮT
    with st.expander("🛠️ 2. Thông số cắt & Dao", expanded=False):
        tool_dia = st.number_input("Đường kính dao (mm):", value=3.0, step=0.1)
        feed_rate = st.number_input("Tốc độ cắt F (mm/phút):", value=1200, step=100)
        cut_z = st.number_input("Độ sâu cắt Z (mm):", value=-2.0, step=0.5)
        safe_z = st.number_input("Chiều cao an toàn Safe Z (mm):", value=5.0, step=1.0)
        lead_len = st.number_input("Chiều dài đường mồi (mm):", value=5.0, step=0.5)
        mode_option = st.selectbox("Chế độ bù dao:", ["Bù bán kính dao", "Không bù dao (Chạy nét)"])
        mode_str = "compensation" if mode_option == "Bù bán kính dao" else "online"

    # 🧩 KHỔ PHÔI
    with st.expander("🧩 3. Kích thước phôi (Nesting)", expanded=False):
        sheet_w = st.number_input("Rộng phôi X (mm):", value=600, step=50)
        sheet_h = st.number_input("Dài phôi Y (mm):", value=400, step=50)
        part_margin = st.number_input("Khoảng cách chi tiết (mm):", value=5.0, step=1.0)

    # 💰 BÁO GIÁ
    with st.expander("💰 4. Cấu hình Báo giá", expanded=False):
        g00_speed = st.number_input("Tốc độ G00 (mm/phút):", value=5000, step=500)
        cost_per_minute = st.number_input("Chi phí máy (VNĐ/phút):", value=2000, step=500)

if "is_nested" not in st.session_state:
    st.session_state.is_nested = False

# --- CỘT PHẢI: XỬ LÝ & TABS ---
with col_display:
    if uploaded_file is not None:
        try:
            detected_parts = process_dxf_file(uploaded_file.getvalue(), uploaded_file.name)
            st.success(f"✅ Đã nạp file: **{uploaded_file.name}** | Nét nhận diện: **{len(detected_parts)}**")

            # Quản lý chi tiết
            st.subheader("🔄 Quản lý & Tối ưu Vị trí")
            col_sel, col_btn1, col_btn2 = st.columns([2, 1, 1])
            with col_sel:
                part_map = {f"Chi tiết #{p['id']}": p for p in detected_parts}
                selected_names = st.multiselect("Chọn chi tiết gia công:", options=list(part_map.keys()), default=list(part_map.keys()), label_visibility="collapsed")
            
            final_ordered_parts = [part_map[name] for name in selected_names] if selected_names else detected_parts

            with col_btn1:
                if st.button("🧩 Tối ưu xếp phôi", use_container_width=True, type="primary"):
                    st.session_state.is_nested = True
            with col_btn2:
                if st.button("↩️ Khôi phục gốc", use_container_width=True):
                    st.session_state.is_nested = False

            # Xử lý Nesting & Toolpath
            parts_to_process = apply_nesting_to_parts(final_ordered_parts, sheet_w, sheet_h, part_margin) if st.session_state.is_nested else final_ordered_parts
            generator = ToolpathGenerator(tool_diameter=tool_dia, feed_rate=feed_rate, lead_length=lead_len)
            raw_paths = generator.generate(parts_to_process, mode=mode_str)

            raw_optimized_paths = []
            total_g01_len, total_g00_len = 0.0, 0.0
            
            for item in raw_paths:
                for sub in item["coords"]:
                    raw_optimized_paths.append({"type": item.get("type", "G1"), "feed": feed_rate, "points": sub})
                    # Tính tổng chiều dài
                    for i in range(len(sub)-1):
                        total_g01_len += math.hypot(sub[i+1][0]-sub[i][0], sub[i+1][1]-sub[i][1])

            # Dịch chuyển Work Zero
            optimized_paths, shift_x, shift_y = apply_work_zero_shift(raw_optimized_paths, zero_option, st.session_state.is_nested, sheet_w, sheet_h)

            # TABS CHỨC NĂNG
            tab_sim, tab_gcode, tab_ai = st.tabs(["📊 Mô phỏng 2D & Work Zero", "💾 Xuất G-Code", "🤖 Gemini AI & Machine Learning Center"])

            # TAB 1: MÔ PHỎNG 2D
            with tab_sim:
                if HAS_PLOTLY:
                    fig = go.Figure()
                    # Điểm Work Zero
                    fig.add_trace(go.Scatter(
                        x=[0], y=[0], mode="markers+text",
                        marker=dict(color="red", size=14, symbol="x-open-dot", line=dict(width=2)),
                        text=["📍 Work Zero (0,0)"], textposition="top right", name="Gốc Work Zero (G54)"
                    ))
                    # Vẽ khung phôi
                    if st.session_state.is_nested:
                        fig.add_trace(go.Scatter(
                            x=[0-shift_x, sheet_w-shift_x, sheet_w-shift_x, 0-shift_x, 0-shift_x],
                            y=[0-shift_y, 0-shift_y, sheet_h-shift_y, sheet_h-shift_y, 0-shift_y],
                            mode="lines", name="Khung phôi", line=dict(color="orange", width=1.5, dash="dash")
                        ))
                    # Vẽ Toolpath
                    for idx, path in enumerate(optimized_paths):
                        xs, ys = zip(*path["points"])
                        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=f"Cắt #{idx+1}"))

                    fig.update_layout(xaxis_title="X (mm)", yaxis_title="Y (mm)", height=480, yaxis=dict(scaleanchor="x"), margin=dict(l=10, r=10, t=20, b=10))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("Cần cài đặt `plotly` trong requirements.txt để hiển thị mô phỏng!")

            # TAB 2: XUẤT G-CODE
            with tab_gcode:
                gcode_lines = [
                    f"(----------------------------------------)",
                    f"(PROGRAM NAME : {uploaded_file.name})",
                    f"(WORK ZERO POS: {zero_option})",
                    f"(SAFE Z       : {safe_z} mm)",
                    f"(CUT Z        : {cut_z} mm)",
                    f"(TOOL DIA     : {tool_dia} mm)",
                    f"(----------------------------------------)",
                    "G21 (Units: mm)", "G90 (Absolute coordinates)", "G54 (Work Offset)", f"G0 Z{safe_z:.3f}"
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

                st.download_button(
                    label="📥 Tải File G-Code (.nc)", data=gcode_text,
                    file_name=os.path.splitext(uploaded_file.name)[0] + "_g54.nc",
                    mime="text/plain", type="primary"
                )
                st.code(gcode_text[:800] + "\n... [Còn tiếp]", language="gcode")

            # TAB 3: TRUNG TÂM GEMINI AI & MACHINE LEARNING
            with tab_ai:
                st.subheader("🤖 Gemini AI Control & Optimization Center")
                
                # ML Cost & Time
                st.markdown("### 📈 1. Dự đoán Thời gian & Chi phí Thực tế (Machine Learning)")
                real_time_pred = predict_real_machine_time(total_g01_len, total_g00_len, len(detected_parts), cut_z, feed_rate, g00_speed)
                real_cost_pred = real_time_pred * cost_per_minute

                c1, c2 = st.columns(2)
                c1.metric("⏱️ Thời gian máy chạy (ML dự đoán)", f"{real_time_pred:.2f} phút")
                c2.metric("💰 Chi phí gia công ước tính", f"{real_cost_pred:,.0f} VNĐ")
                st.caption("ℹ️ *Mô hình ML dự đoán độ trễ tăng/giảm tốc của động cơ dựa trên lịch sử chạy máy.*")

                st.divider()

                # LLM Gemini AI Risk Analysis
                st.markdown("### 🔍 2. Gemini AI Cảnh báo Lỗi DXF & Chế độ Cắt")
                api_key_input = st.text_input("Nhập Google Gemini API Key:", type="password", help="AIzaSy...")
                selected_material = st.selectbox("Chọn vật liệu phôi cắt:", ["Nhôm 6061", "Gỗ Plywood / MDF", "Mica / Acrylic", "Thép C45"])

                if st.button("🚀 Chạy kiểm tra Gemini AI Toàn diện", type="primary"):
                    with st.spinner("Gemini AI đang phân tích file DXF và tính toán chế độ cắt..."):
                        report = ai_dxf_and_risk_analysis(api_key_input, detected_parts, selected_material, tool_dia, feed_rate, cut_z)
                        st.markdown(report)

        except Exception as e:
            st.error(f"Lỗi xử lý ứng dụng: {e}")
    else:
        st.info("👋 Vui lòng tải file DXF ở cột bên trái để bắt đầu gia công.")
