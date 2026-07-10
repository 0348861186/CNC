import streamlit as st
import os
import io
import plotly.graph_objects as go  # Sử dụng Plotly thay cho Matplotlib

# Nhập các file xử lý thuật toán hiện tại của bạn trong dự án
from dxf_reader import DXFReader
from part_detector import PartDetector
from toolpath import ToolpathGenerator
from gcode_writer import GCodeWriter

st.set_page_config(layout="wide") 
st.title("CAM DXF Cutter Control Dashboard - Web Phiên Bản Cao Cấp")

# Thiết lập layout thành 2 cột
col_sidebar, col_display = st.columns([1, 2]) # Tỷ lệ 1:2 giúp vùng hiển thị rộng hơn

# ==========================================
# KHU VỰC CÀI ĐẶT THÔNG SỐ (CỘT BÊN TRÁI)
# ==========================================
with col_sidebar:
    st.header("⚙️ Cấu hình vận hành")
    
    # 1. Khung tải file DXF từ máy tính
    uploaded_file = st.file_uploader("📂 Tải File DXF Bản Vẽ", type=["dxf"])
    
    # Các ô nhập thông số công nghệ
    tool_dia = st.number_input("Đường kính dao (mm):", value=3.0, step=0.1)
    feed_rate = st.number_input("Tốc độ cắt F (mm/p):", value=1200, step=100)
    cut_z = st.number_input("Độ sâu cắt Z (mm):", value=-2.0, step=0.5)
    lead_len = st.number_input("Chiều dài đường mồi (mm):", value=5.0, step=0.5)
    
    # Lựa chọn chế độ bù dao
    mode_option = st.selectbox(
        "Chế độ bù mạch cắt:",
        ["Bù bán kính dao", "Không bù dao (Chạy trên nét)"]
    )
    mode_str = "compensation" if mode_option == "Bù bán kính dao" else "online"

# ==========================================
# KHU VỰC XỬ LÝ LOGIC VÀ ĐỒ HỌA (CỘT BÊN PHẢI)
# ==========================================
with col_display:
    if uploaded_file is not None:
        st.success(f" Đã nạp thành công file: {uploaded_file.name}")
        
        try:
            # Bước 1: Tạo file tạm để đọc dữ liệu
            temp_filename = f"temp_{uploaded_file.name}"
            with open(temp_filename, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Bước 2: Đọc bản vẽ và nhận diện chi tiết
            reader = DXFReader(temp_filename)
            raw_lines = reader.read_entities()

            detector = PartDetector()
            detected_parts = detector.detect_parts(raw_lines)
            
            # Xóa file tạm sau khi đọc xong hình học vào bộ nhớ
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            
            st.info(f"Tìm thấy {len(detected_parts)} chi tiết kín trong bản vẽ.")
            
            # ==================================================
            # CHỨC NĂNG THAY ĐỔI THỨ TỰ CẮT THEO Ý MUỐN
            # ==================================================
            st.subheader("🔄 Sắp xếp lại thứ tự cắt chi tiết")
            
            part_options = [f"Chi tiết số: {part['id']}" for part in detected_parts]
            st.markdown("*Mẹo: Chọn hoặc xóa các số bên dưới để xếp thứ tự chạy dao mong muốn.*")
            
            ordered_selection = st.multiselect(
                "Thứ tự cắt hiện tại (Hãy xếp lại nếu muốn):",
                options=part_options,
                default=part_options
            )
            
            # Đồng bộ lại mảng detected_parts dựa trên thứ tự người dùng chọn
            final_ordered_parts = []
            for selected_name in ordered_selection:
                part_id = int(selected_name.split(": ")[1])
                for part in detected_parts:
                    if part['id'] == part_id:
                        final_ordered_parts.append(part)
                        break
            
            if not final_ordered_parts:
                final_ordered_parts = detected_parts
            
            # Bước 3: Tính toán Toolpath dựa trên danh sách chi tiết
            gen = ToolpathGenerator(tool_diameter=tool_dia, feed_rate=feed_rate, lead_length=lead_len)
            raw_paths = gen.generate(final_ordered_parts, mode=mode_str)

            # Phẳng hóa danh sách đường cắt tương thích với cấu hình đồ họa gốc
            optimized_paths = []
            for item in raw_paths:
                for sub_path in item['coords']:
                    optimized_paths.append({
                        'type': item['type'],
                        'feed': item['feed'],
                        'points': sub_path
                    })
                
            # ==========================================
            # MÀN HÌNH MÔ PHỎNG ĐỒ HỌA PLOTLY (NÂNG CẤP ✨)
            # ==========================================
            st.subheader("📊 Màn hình mô phỏng hình học tương tác (Zoom/Pan)")
            
            # Khởi tạo khung biểu đồ Plotly
            fig = go.Figure()
            
            current_x, current_y = 0.0, 0.0
            
            # Tiến hành vẽ lại cấu trúc đường đi của dao bằng Plotly
            for idx, path in enumerate(optimized_paths):
                pts = path['points']
                x_pts, y_pts = zip(*pts)
                start_x, start_y = pts[0][0], pts[0][1]
                
                # 1. Vẽ đường di dao nhanh G00 (Đường đứt nét màu xám)
                fig.add_trace(go.Scatter(
                    x=[current_x, start_x], 
                    y=[current_y, start_y],
                    mode='lines',
                    line=dict(color='gray', width=1.5, dash='dot'),
                    name=f'Di dao nhanh G00 (#{idx+1})',
                    showlegend=False
                ))
                
                # 2. Vẽ đường cắt thực tế G01 (Đường màu xanh lá)
                fig.add_trace(go.Scatter(
                    x=x_pts, y=y_pts,
                    mode='lines',
                    line=dict(color='green', width=2.5),
                    name=f'Đường cắt #{idx+1}'
                ))
                
                # 3. Đánh số thứ tự đường cắt #1, #2, #3 ngay tại điểm bắt đầu
                fig.add_trace(go.Scatter(
                    x=[start_x + 2], y=[start_y + 2],
                    mode='text',
                    text=[f"#{idx+1}"],
                    textposition="top right",
                    textfont=dict(color="purple", size=14, family="Arial Black"),
                    showlegend=False
                ))
                
                # 4. Vẽ dấu chấm đỏ tại điểm mồi dao
                if lead_len > 0:
                    fig.add_trace(go.Scatter(
                        x=[start_x], y=[start_y],
                        mode='markers',
                        marker=dict(color='red', size=6),
                        showlegend=False
                    ))

                # Cập nhật vị trí điểm cuối của dao
                current_x, current_y = pts[-1][0], pts[-1][1]
            
            # Cấu hình hiển thị tỷ lệ hệ trục tọa độ vuông góc 1:1 (Aspect Ratio Equal)
            fig.update_layout(
                title="Sơ đồ đường chạy dao cắt thực tế",
                xaxis_title="Trục X (mm)",
                yaxis_title="Trục Y (mm)",
                width=800,
                height=600,
                yaxis=dict(scaleanchor="x", scaleratio=1), # Giữ hình dáng không bị méo khi co giãn trình duyệt
                showlegend=True,
                hovermode='closest'
            )
            
            # Xuất trực tiếp khung vẽ tương tác lên Web
            st.plotly_chart(fig, use_container_width=True)
            
            # ==========================================
            # XUẤT FILE G-CODE VÀ TẠO NÚT TẢI VỀ
            # ==========================================
            st.subheader("💾 Xuất kết quả G-code")
            
            try:
                writer = GCodeWriter(optimized_paths)
                gcode_text = writer.write() 
            except:
                gcode_text = f"(G-Code Generated for {uploaded_file.name})\nG21\nG90\nM03\n"
                for p in optimized_paths:
                    for pt in p['points']:
                        gcode_text += f"G1 X{pt:.3f} Y{pt:.3f} F{feed_rate}\n"
            
            st.download_button(
                label="📥 Tải về file G-code (.nc)",
                data=gcode_text,
                file_name=f"output_{uploaded_file.name.replace('.dxf', '')}.nc",
                mime="text/plain"
            )
            
        except Exception as e:
            st.error(f"Đã xảy ra lỗi hệ thống trong quá trình tính toán logic: {e}")
    else:
        st.info("Vui lòng tải một file bản vẽ hình học dạng .dxf ở cột bên trái để bắt đầu hiển thị mô phỏng.")
