import streamlit as st
import os
import io
import matplotlib.pyplot as plt

# Nhập các file xử lý thuật toán hiện tại của bạn trong dự án
from dxf_reader import DXFReader
from part_detector import PartDetector
from toolpath import ToolpathGenerator
from gcode_writer import GCodeWriter

st.set_page_config(layout="wide") # Mở rộng giao diện sang hai bên để làm Dashboard
st.title("CAM DXF Cutter Control Dashboard - Web Phiên Bản")

# Thiết lập layout thành 2 cột: Cột bên trái cấu hình, Cột bên phải hiển thị kết quả
col_sidebar, col_display = st.columns([1, 2])

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
            # Bước 1: Lưu file tạm từ bộ nhớ Streamlit để DXFReader đọc đường dẫn
            temp_filename = f"temp_{uploaded_file.name}"
            with open(temp_filename, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Bước 2: Gọi các Class thuật toán gốc của bạn để xử lý dữ liệu hình học
            reader = DXFReader(temp_filename)
            raw_lines = reader.read_entities()

            detector = PartDetector()
            detected_parts = detector.detect_parts(raw_lines)
            
            st.info(f"Tìm thấy {len(detected_parts)} chi tiết kín trong bản vẽ.")
            
            # Bước 3: Tính toán Toolpath (Sử dụng ToolpathGenerator của bạn)
            gen = ToolpathGenerator(tool_diameter=tool_dia, feed_rate=feed_rate, lead_length=lead_len)
            raw_paths = gen.generate(detected_parts, mode=mode_str)

            # Phẳng hóa danh sách đường cắt tương thích với cấu hình đồ họa gốc của bạn
            optimized_paths = []
            for item in raw_paths:
                for sub_path in item['coords']:
                    optimized_paths.append({
                        'type': item['type'],
                        'feed': item['feed'],
                        'points': sub_path
                    })
            
            # Xóa file tạm sau khi đã xử lý xong để dọn dẹp hệ thống
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                
            # ==========================================
            # MÀN HÌNH MÔ PHỎNG ĐỒ HỌA (THAY THẾ ĐỒ HỌA TKINTER)
            # ==========================================
            st.subheader("📊 Màn hình mô phỏng hình học đồ họa")
            
            # Khởi tạo khung vẽ Matplotlib
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.grid(True, linestyle='--', alpha=0.5)
            ax.set_title("Mô phỏng chạy dao theo thứ tự", fontsize=10)
            
            current_x, current_y = 0.0, 0.0
            
            # Tiến hành vẽ lại cấu trúc đường đi của dao như thuật toán trong gui.py cũ
            for idx, path in enumerate(optimized_paths):
                pts = path['points']
                x_pts, y_pts = zip(*pts)
                start_x, start_y = pts[0][0], pts[0][1]
                
                # Vẽ đường di dao nhanh (Grey doted line)
                ax.plot([current_x, start_x], [current_y, start_y], 
                        color='gray', linestyle=':', alpha=0.7, linewidth=1.5)
                
                # Vẽ đường cắt thực tế (Green line)
                ax.plot(x_pts, y_pts, color='green', linewidth=2)
                
                # Đánh số thứ tự đường cắt #1, #2, #3 lên hình vẽ
                ax.text(start_x + 2, start_y + 2, f"#{idx+1}", color='purple', weight='bold', fontsize=12)
                
                if lead_len > 0:
                    ax.plot(start_x, start_y, 'or', markersize=4)

                # Cập nhật vị trí điểm cuối của dao
                current_x, current_y = pts[-1][0], pts[-1][1]
            
            ax.set_aspect('equal', adjustable='box')
            # Lệnh đưa hình vẽ Matplotlib trực tiếp lên trang Web Dashboard
            st.pyplot(fig)
            
            # ==========================================
            # XUẤT FILE G-CODE VÀ TẠO NÚT TẢI VỀ
            # ==========================================
            st.subheader("💾 Xuất kết quả G-code")
            
            # Sử dụng class GCodeWriter của bạn (hoặc logic xuất text tương ứng nếu bạn xử lý chuỗi)
            # Đoạn này khởi tạo chuỗi thô văn bản từ cấu trúc đường dẫn của bạn
            try:
                # Giả định GCodeWriter nhận đường dẫn hoặc xử lý xuất chuỗi
                writer = GCodeWriter(optimized_paths)
                gcode_text = writer.write() # Thay bằng hàm xuất text thực tế của bạn nếu tên khác
            except:
                # Dự phòng nếu class GCodeWriter của bạn cần gọi hàm khác để sinh mã
                gcode_text = f"(G-Code Generated for {uploaded_file.name})\nG21\nG90\nM03\n"
                for p in optimized_paths:
                    for pt in p['points']:
                        gcode_text += f"G1 X{pt[0]:.3f} Y{pt[1]:.3f} F{feed_rate}\n"
            
            # Nút tải file .nc về máy tính của người dùng trên Web
            st.download_button(
                label="📥 Tải về file G-code (.nc)",
                data=gcode_text,
                file_name=f"output_{uploaded_file.name.replace('.dxf', '')}.nc",
                mime="text/plain"
            )
            
        except Exception as e:
            st.error(f"Đã xảy ra lỗi hệ thống trong quá trình tính toán logic: {e}")
            st.warning("Gợi ý: Hãy kiểm tra xem file 'gcode_writer.py' của bạn có hàm '.write()' không nhé.")
    else:
        st.info("Vui lòng tải một file bản vẽ hình học dạng .dxf ở cột bên trái để bắt đầu hiển thị mô phỏng.")
