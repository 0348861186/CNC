import streamlit as st
import os
import io
import matplotlib.pyplot as plt

# Nhập các file xử lý thuật toán hiện tại của bạn trong dự án
from dxf_reader import DXFReader
from part_detector import PartDetector
from toolpath import ToolpathGenerator
from gcode_writer import GCodeWriter

st.set_page_config(layout="wide") 
st.title("CAM DXF Cutter Control Dashboard - Web Phiên Bản")

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
            # CHỨC NĂNG THAY ĐỔI THỨ TỰ CẮT THEO Ý MUỐN (MỚI ✨)
            # ==================================================
            st.subheader("🔄 Sắp xếp lại thứ tự cắt chi tiết")
            
            # Tạo danh sách tên hiển thị (Ví dụ: ["Chi tiết số: 1", "Chi tiết số: 2", ...])
            part_options = [f"Chi tiết số: {part['id']}" for part in detected_parts]
            
            # Hướng dẫn người dùng cách thao tác
            st.markdown("*Mẹo: Bạn hãy nhấp vào ô dưới đây, chọn hoặc xóa các số để xếp thứ tự chạy dao mong muốn (Ví dụ chọn số 4 trước, rồi đến 3, 2, 1).*")
            
            # Thanh chọn đa năng hỗ trợ đổi thứ tự bằng cách nhấp chọn lần lượt
            ordered_selection = st.multiselect(
                "Thứ tự cắt hiện tại (Hãy xếp lại nếu muốn):",
                options=part_options,
                default=part_options # Mặc định giữ nguyên thứ tự ban đầu 1, 2, 3, 4
            )
            
            # Đồng bộ lại mảng detected_parts dựa trên thứ tự người dùng vừa chọn trên Web
            final_ordered_parts = []
            for selected_name in ordered_selection:
                # Trích xuất lấy số ID từ chuỗi chữ "Chi tiết số: X"
                part_id = int(selected_name.split(": ")[1])
                # Tìm chi tiết tương ứng trong mảng gốc đưa vào mảng chạy dao mới
                for part in detected_parts:
                    if part['id'] == part_id:
                        final_ordered_parts.append(part)
                        break
            
            # Kiểm tra phòng trường hợp người dùng xóa hết hoặc chưa chọn đủ chi tiết
            if not final_ordered_parts:
                final_ordered_parts = detected_parts
                st.warning("Vui lòng không để trống mục thứ tự cắt. Hệ thống đang tạm dùng thứ tự mặc định.")
            
            # Bước 3: Tính toán Toolpath dựa trên danh sách chi tiết ĐÃ ĐỔI THỨ TỰ ở trên
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
            # MÀN HÌNH MÔ PHỎNG ĐỒ HỌA
            # ==========================================
            st.subheader("📊 Màn hình mô phỏng hình học đồ họa")
            
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.grid(True, linestyle='--', alpha=0.5)
            ax.set_title("Mô phỏng chạy dao theo thứ tự chỉ định", fontsize=10)
            
            current_x, current_y = 0.0, 0.0
            
            # Tiến hành vẽ lại cấu trúc đường đi của dao theo thứ tự mới sắp xếp
            for idx, path in enumerate(optimized_paths):
                pts = path['points']
                x_pts, y_pts = zip(*pts)
                start_x, start_y = pts[0][0], pts[0][1]
                
                # Vẽ đường di dao nhanh (Grey dotted line)
                ax.plot([current_x, start_x], [current_y, start_y], 
                        color='gray', linestyle=':', alpha=0.7, linewidth=1.5)
                
                # Vẽ đường cắt thực tế (Green line)
                ax.plot(x_pts, y_pts, color='green', linewidth=2)
                
                # Đánh số thứ tự đường cắt #1, #2, #3 lên hình vẽ để kiểm tra trực quan
                ax.text(start_x + 2, start_y + 2, f"#{idx+1}", color='purple', weight='bold', fontsize=12)
                
                if lead_len > 0:
                    ax.plot(start_x, start_y, 'or', markersize=4)

                # Cập nhật vị trí điểm cuối của dao
                current_x, current_y = pts[-1][0], pts[-1][1]
            
            ax.set_aspect('equal', adjustable='box')
            st.pyplot(fig)
            
            # ==========================================
            # XUẤT FILE G-CODE VÀ TẠO NÚT TẢI VỀ
            # ==========================================
            st.subheader("💾 Xuất kết quả G-code")
            
            try:
                writer = GCodeWriter(optimized_paths)
                gcode_text = writer.write() 
            except:
                # Dự phòng nếu class GCodeWriter cần cấu hình khác
                gcode_text = f"(G-Code Generated for {uploaded_file.name})\nG21\nG90\nM03\n"
                for p in optimized_paths:
                    for pt in p['points']:
                        gcode_text += f"G1 X{pt[0]:.3f} Y{pt[1]:.3f} F{feed_rate}\n"
            
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
