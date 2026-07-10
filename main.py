import streamlit as st
import io
import matplotlib.pyplot as plt

# Nhập các file xử lý thuật toán hiện tại của bạn trong dự án
import dxf_reader
import toolpath
import optimizer
import gcode_writer
import viewer

st.title("Ứng dụng Xử lý Bản vẽ CNC & G-code")

# 1. Khung tải file DXF từ máy tính
uploaded_file = st.file_uploader("Tải file DXF của bạn lên tại đây", type=["dxf"])

if uploaded_file is not None:
    st.success("Đã tải file lên thành công!")
    
    try:
        # Đọc dữ liệu file DXF từ bộ nhớ tạm của Streamlit dưới dạng văn bản/bytes
        file_bytes = uploaded_file.read()
        
        # 2. Gọi các hàm xử lý logic từ dự án cũ của bạn
        # Bước A: Đọc dữ liệu hình học thực thể từ file DXF
        # (Nếu hàm trong dxf_reader.py nhận đường dẫn file, ta lưu tạm file_bytes hoặc truyền trực tiếp dữ liệu)
        # Tùy thuộc vào code của bạn, ở đây giả định hàm xử lý là parse_dxf hoặc read_dxf
        try:
            # Thử đọc trực tiếp chuỗi bytes bằng ezdxf thông qua io.BytesIO nếu code bạn hỗ trợ
            dxf_data = dxf_reader.parse_dxf(io.BytesIO(file_bytes))
        except:
            # Phương án dự phòng nếu code cũ của bạn nhận chuỗi string text thô
            dxf_data = dxf_reader.parse_dxf(file_bytes.decode("utf-8", errors="ignore"))
            
        # Bước B: Tính toán Toolpath và Tối ưu hóa thứ tự các đường cắt CNC
        # (Thay thế 'geometry_processing' bằng hàm thực tế trong file optimizer.py hoặc toolpath.py của bạn)
        optimized_paths = optimizer.optimize_paths(dxf_data)
        
        # 3. Hiển thị kết quả đồ họa trực quan (Thay thế cho thư mục viewer.py cũ)
        st.subheader("Cấu trúc đường cắt dự kiến")
        
        # Tạo khung hình vẽ bằng thư viện matplotlib để đưa lên web
        fig, ax = plt.subplots(figsize=(6, 6))
        
        # Gọi hàm xử lý vẽ từ file viewer.py của bạn
        # Truyền biến dữ liệu đường cắt và trục vẽ ax vào hàm của bạn
        viewer.draw_paths(optimized_paths, ax=ax)
        
        # Lệnh hiển thị hình ảnh đồ họa lên giao diện Web Streamlit
        st.pyplot(fig)
        
        # 4. Xuất kết quả chuỗi G-code và tạo nút tải về máy
        st.subheader("Xuất kết quả G-code")
        
        # Gọi hàm tạo chuỗi văn bản G-code từ file gcode_writer.py của bạn
        gcode_data = gcode_writer.generate_gcode(optimized_paths)
        
        st.download_button(
            label="Tải về file G-code (.nc)",
            data=gcode_data,
            file_name="output_cnc.nc",
            mime="text/plain"
        )
        
    except Exception as e:
        # Nếu cấu trúc tên hàm bên trong các file .py của bạn khác với tên tôi giả định, web sẽ báo lỗi tại đây
        st.error(f"Lưu ý: Bạn cần đồng bộ lại tên hàm xử lý logic. Chi tiết lỗi hệ thống: {e}")
