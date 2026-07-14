import streamlit as st
import openai  # Hoặc dùng google.generativeai

# ==========================================
# CẤU HÌNH AI ASSISTANT (Thêm vào Sidebar)
# ==========================================
with st.sidebar:
    st.divider()
    st.header("🤖 Trợ lý AI CAM Co-pilot")
    api_key = st.text_input("Nhập OpenAI / Gemini API Key:", type="password")
    material = st.selectbox("Chọn vật liệu phôi:", ["Nhôm 6061", "Gỗ MDF / Plywood", "Mica / Acrylic", "Thép C45"])

def ai_analyze_cam_setup(material, tool_dia, feed_rate, cut_z, safe_z, part_count):
    """Hàm gửi dữ liệu thông số cắt cho AI để phân tích rủi ro"""
    if not api_key:
        return "⚠️ Vui lòng nhập API Key ở cột bên trái để sử dụng Trợ lý AI."
    
    prompt = f"""
    Bạn là một chuyên gia lập trình CAM/CNC lâu năm. 
    Hãy đánh giá thiết lập gia công sau và chỉ ra các rủi ro (nếu có) cũng như lời khuyên:
    - Vật liệu gia công: {material}
    - Đường kính dao: {tool_dia} mm
    - Tốc độ cắt F: {feed_rate} mm/phút
    - Độ sâu mỗi lát cắt Z: {cut_z} mm
    - Chiều cao an toàn Safe Z: {safe_z} mm
    - Số lượng chi tiết kín: {part_count}

    Hãy đưa ra nhận xét ngắn gọn (dưới 150 từ), súc tích theo 3 mục:
    1. 🎯 Đánh giá thông số (An toàn hay Nguy hiểm?)
    2. ⚠️ Rủi ro tiềm ẩn (Gãy dao, cháy phôi, bavia...?)
    3. 💡 Lời khuyên tối ưu.
    """
    
    try:
        # Ví dụ gọi OpenAI API (Bạn có thể đổi sang Gemini API)
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Lỗi kết nối AI: {e}"

# ==========================================
# HIỂN THỊ TRONG MÀN HÌNH CHÍNH (Tab AI)
# ==========================================
# (Thêm một Tab mới cạnh Tab Mô phỏng / G-code)
tab_sim, tab_gcode, tab_ai = st.tabs(["📊 Mô phỏng 2D", "💾 Xuất G-Code", "🤖 AI Kiểm định An toàn"])

with tab_ai:
    st.subheader("🔍 AI Phân tích & Cảnh báo Rủi ro Gia công")
    if st.button("🚀 Bắt đầu Phân tích với AI", type="primary"):
        with st.spinner("AI đang kiểm tra bản vẽ và thông số cắt..."):
            ai_result = ai_analyze_cam_setup(
                material, tool_dia, feed_rate, cut_z, safe_z, len(detected_parts)
            )
            st.markdown(ai_result)
