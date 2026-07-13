import streamlit as st
import os
import math
import tempfile
from io import BytesIO
import plotly.graph_objects as go

from dxf_reader import DXFReader
from part_detector import PartDetector
from toolpath import ToolpathGenerator
from gcode_writer import GCodeWriter

# ==========================================
# CẤU HÌNH TRANG & CACHE
# ==========================================
st.set_page_config(page_title="CAM DXF Control", layout="wide")

@st.cache_data(show_spinner="Đang phân tích file DXF...")
def process_dxf_file(file_bytes, filename):
    """Lưu tạm vào bộ nhớ tạm thời gian thực và phân tích chi tiết DXF"""
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
# GIAO DIỆN
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

    with st.expander("💰 Cấu hình báo giá", expanded=False):
        g00_speed = st.number_input("Tốc độ chạy nhanh G00 (mm/phút):", value=5000, step=500)
        cost_per_minute = st.number_input("Chi phí máy (VNĐ/phút):", value=2000, step=500)

# --- CỘT PHẢI: HIỂN THỊ VÀ XỬ LÝ ---
with col_display:
    if uploaded_file is not None:
        try:
            # Phân tích DXF với Cache
            detected_parts = process_dxf_file(uploaded_file.getvalue(), uploaded_file.name)
            st.success(f"✅ Đã nạp thành công: **{uploaded_file.name}** | Phát hiện **{len(detected_parts)}** chi tiết kín.")

            # Sắp xếp thứ tự cắt
            part_map = {f"Chi tiết #{p['id']}": p for p in detected_parts}
            selected_names = st.multiselect(
                "🔄 Sắp xếp thứ tự gia công:",
                options=list(part_map.keys()),
                default=list(part_map.keys())
            )
            
            final_ordered_parts = [part_map[name] for name in selected_names] if selected_names else detected_parts

            # Tạo Toolpath
            generator = ToolpathGenerator(
                tool_diameter=tool_dia,
                feed_rate=feed_rate,
                lead_length=lead_len
            )
            raw_paths = generator.generate(final_ordered_parts, mode=mode_str)

            optimized_paths = []
            for item in raw_paths:
                for sub in item["coords"]:
                    optimized_paths.append({
                        "type": item.get("type", "G1"),
                        "feed": item.get("feed", feed_rate),
                        "points": sub
                    })

            # Tính toán thống kê & thời gian
            total_g01_len = 0
            total_g00_len = 0
            cx, cy = 0, 0

            for path in optimized_paths:
                pts = path["points"]
                sx, sy = pts[0]
                
                # Chạy G00 trên mặt phẳng + Hạ/Nhấc dao (Z Safe)
                travel_2d = math.sqrt((sx - cx)**2 + (sy - cy)**2)
                travel_z = abs(safe_z - cut_z) * 2  # Nhấc lên Z_safe và hạ xuống Z_cut
                total_g00_len += travel_2d + travel_z

                # Độ dài đường cắt G01
                for i in range(len(pts) - 1):
                    x1, y1 = pts[i]
                    x2, y2 = pts[i+1]
                    total_g01_len += math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

                cx, cy = pts[-1]

            time_cut_min = (total_g01_len / feed_rate) if feed_rate > 0 else 0
            time_fast_min = (total_g00_len / g00_speed) if g00_speed > 0 else 0
            total_time_min = time_cut_min + time_fast_min
            
            total_sec = int(total_time_min * 60)
            mins, secs = divmod(total_sec, 60)
            cost = total_time_min * cost_per_minute

            # GIAO DIỆN TAB PHÂN CHIA HỢP LÝ
            tab_sim, tab_cost, tab_gcode = st.tabs(["📊 Mô phỏng 2D", "⏱️ Thống kê & Báo giá", "💾 Xuất G-Code"])

            with tab_sim:
                fig = go.Figure()
                cur_x, cur_y = 0, 0
                
                for idx, path in enumerate(optimized_paths):
                    pts = path["points"]
                    xs, ys = zip(*pts)
                    sx, sy = pts[0]

                    # Đường di chuyển không cắt (G00)
                    fig.add_trace(go.Scatter(
                        x=[cur_x, sx], y=[cur_y, sy],
                        mode="lines",
                        line=dict(color="gray", dash="dot", width=1),
                        showlegend=False,
                        hoverinfo="skip"
                    ))

                    # Đường cắt thực tế (G01)
                    fig.add_trace(go.Scatter(
                        x=xs, y=ys,
                        mode="lines",
                        name=f"Chi tiết #{idx+1}"
                    ))
                    cur_x, cur_y = pts[-1]

                fig.update_layout(
                    xaxis_title="X (mm)",
                    yaxis_title="Y (mm)",
                    height=550,
                    yaxis=dict(scaleanchor="x", scaleratio=1),
                    margin=dict(l=20, r=20, t=30, b=20)
                )
                st.plotly_chart(fig, use_container_width=True)

            with tab_cost:
                m1, m2, m3 = st.columns(3)
                m1.metric("Thời gian ước tính", f"{mins} phút {secs} giây")
                m2.metric("Tổng chiều dài cắt (G01)", f"{total_g01_len:,.1f} mm")
                m3.metric("Chi phí gia công", f"{cost:,.0f} VNĐ")

            with tab_gcode:
                # Tạo G-code
                try:
                    writer = GCodeWriter(optimized_paths)
                    gcode_text = writer.write()
                except Exception as writer_err:
                    # Dự phòng tạo G-code đơn giản
                    gcode_lines = ["(Generated G-Code)", "G21 (Units: mm)", "G90 (Absolute Positioning)", f"G0 Z{safe_z}"]
                    for path in optimized_paths:
                        pts = path["points"]
                        gcode_lines.append(f"G0 X{pts[0][0]:.3f} Y{pts[0][1]:.3f}")
                        gcode_lines.append(f"G1 Z{cut_z:.3f} F300")
                        for x, y in pts[1:]:
                            gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f} F{feed_rate}")
                        gcode_lines.append(f"G0 Z{safe_z}")
                    gcode_text = "\n".join(gcode_lines)

                col_preview, col_down = st.columns([3, 1])
                with col_preview:
                    st.text_area("Xem trước G-code:", value=gcode_text[:1000] + "\n...", height=180)
                with col_down:
                    out_name = os.path.splitext(uploaded_file.name)[0] + ".nc"
                    st.download_button(
                        label="📥 Tải file G-code (.nc)",
                        data=gcode_text,
                        file_name=out_name,
                        mime="text/plain",
                        use_container_width=True
                    )

        except Exception as e:
            st.error(f"❌ Có lỗi xảy ra trong quá trình xử lý: {e}")
    else:
        st.info("👋 Vui lòng tải file DXF ở cột bên trái để bắt đầu mô phỏng.")
