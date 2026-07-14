import streamlit as st
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import openai

# ==========================================
# LOẠI 3: MACHINE LEARNING - DỰ ĐOÁN THỜI GIAN/CHI PHÍ THỰC TẾ
# ==========================================
@st.cache_resource
def train_dummy_cost_ml_model():
    """
    Giả lập mô hình Machine Learning được huấn luyện từ lịch sử chạy máy thực tế.
    (Trong thực tế: pd.read_csv('history_cnc_logs.csv'))
    """
    # Features: [Chiều dài G01 (mm), Chiều dài G00 (mm), Số lượng chi tiết, Độ sâu Z (mm)]
    X_train = np.array([
        [1000, 200, 5, -2.0],
        [2500, 500, 12, -5.0],
        [5000, 1200, 20, -10.0],
        [800, 150, 3, -1.0],
        [3200, 800, 15, -3.0]
    ])
    y_train = np.array([1.2, 3.1, 6.8, 0.9, 4.2])  # Thời gian thực tế (phút)

    model = RandomForestRegressor(n_estimators=10, random_state=42)
    model.fit(X_train, y_train)
    return model

ml_model = train_dummy_cost_ml_model()

def predict_real_machine_time(total_g01, total_g00, part_count, cut_z):
    """Dự đoán thời gian gia công thực tế có tính độ trễ động cơ/tăng giảm tốc"""
    features = np.array([[total_g01, total_g00, part_count, cut_z]])
    predicted_time = ml_model.predict(features)[0]
    return max(0.1, predicted_time)

# ==========================================
# LOẠI 1 & LOẠI 2: AI PHÂN TÍCH RỦI RO & BẢN VẼ DXF (CALL API)
# ==========================================
def ai_dxf_and_risk_analysis(api_key, detected_parts, material, tool_dia, feed_rate, cut_z):
    """Kết hợp kiểm tra hình học DXF (Loại 2) và tư vấn thông số gia công (Loại 1)"""
    if not api_key:
        return "⚠️ Vui lòng nhập OpenAI API Key để khởi chạy Trợ lý AI."

    # Rút trích dữ liệu hình học DXF gửi cho AI
    part_summary = []
    for p in detected_parts:
        pts = p.get("points", [])
        if pts:
            xs = [pt[0] for pt in pts]
            ys = [pt[1] for pt in pts]
            width = max(xs) - min(xs)
            height = max(ys) - min(ys)
        else:
            width, height = 0, 0

        part_summary.append({
            "id": p.get("id"),
            "point_count": len(pts),
            "is_closed": (pts[0] == pts[-1]) if pts else False,
            "approx_size_mm": f"{width:.1f}x{height:.1f}"
        })

    prompt = f"""
    Bạn là chuyên gia lập trình và vận hành máy cắt CNC/CAM cao cấp.
    
    [DỮ LIỆU HÌNH HỌC DXF - KIỂM TRA LỖI]:
    - Số lượng chi tiết kín: {len(detected_parts)}
    - Cấu trúc chi tiết: {part_summary}
    - Đường kính dao sử dụng: {tool_dia} mm
    
    [CẤU HÌNH GIA CÔNG - TƯ VẤN RỦI RO]:
    - Vật liệu phôi: {material}
    - Tốc độ cắt F: {feed_rate} mm/phút
    - Độ sâu Z mỗi lát: {cut_z} mm

    YÊU CẦU PHÂN TÍCH:
    1. 🔍 **Rà soát Lỗi DXF (Loại 2)**: Kiểm tra các chi tiết có kín không (`is_closed`), kích thước hốc nhỏ so với đường kính dao {tool_dia}mm.
    2. ⚠️ **Phân tích Rủi ro & Chế độ cắt (Loại 1)**: Thông số F={feed_rate}, Z={cut_z} cho vật liệu {material} đã an toàn chưa? Có nguy cơ gãy dao hoặc bavia không?
    3. 💡 **Đề xuất hiệu chỉnh**: Hướng dẫn kỹ sư điều chỉnh chi tiết.
    """

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Lỗi kết nối AI API: {e}"

# ==========================================
# GIAO DIỆN STREAMLIT (TAB AI CONTROL CENTER)
# ==========================================
# Khởi tạo các giá trị mặc định phòng trường hợp chưa chạy qua luồng chính
if 'cost_per_minute' not in locals():
    cost_per_minute = 2000

# Tạo Tab hiển thị
tab_sim, tab_gcode, tab_ai = st.tabs(["📊 Mô phỏng 2D", "💾 Xuất G-Code", "🤖 AI Control Center"])

with tab_ai:
    st.subheader("🤖 Trung tâm Trợ lý AI & Machine Learning")
    
    # 1. Hiển thị dự đoán Machine Learning (LOẠI 3)
    st.markdown("### 📈 1. Dự đoán thời gian & Chi phí thực tế (Machine Learning)")
    
    # Lấy thông số thực tế từ chương trình chính nếu có
    current_g01 = total_g01_len if 'total_g01_len' in locals() else 3500.0
    current_g00 = total_g00_len if 'total_g00_len' in locals() else 800.0
    current_parts_count = len(detected_parts) if 'detected_parts' in locals() else 5
    current_cut_z = cut_z if 'cut_z' in locals() else -2.0

    real_time_pred = predict_real_machine_time(current_g01, current_g00, current_parts_count, current_cut_z)
    real_cost_pred = real_time_pred * cost_per_minute

    c1, c2 = st.columns(2)
    c1.metric("⏱️ Thời gian máy chạy thực tế (ML dự đoán)", f"{real_time_pred:.2f} phút")
    c2.metric("💰 Chi phí thực tế ước tính (ML dự đoán)", f"{real_cost_pred:,.0f} VNĐ")
    st.caption("ℹ️ *Mô hình ML dự đoán dựa trên thời gian tăng/giảm tốc thực tế của động cơ và lịch sử vận hành.*")

    st.divider()

    # 2. Hiển thị Phân tích AI LLM (LOẠI 1 & LOẠI 2)
    st.markdown("### 🔍 2. AI Kiểm tra Lỗi DXF & Tư vấn Thông số Gia công (LLM API)")
    
    api_key_input = st.text_input("Nhập OpenAI API Key để kích hoạt AI:", type="password", help="Ví dụ: sk-proj-...")
    selected_material = st.selectbox("Vật liệu phôi cắt:", ["Nhôm 6061", "Gỗ Plywood / MDF", "Mica / Acrylic", "Thép C45"])

    if st.button("🚀 Chạy kiểm tra AI Toàn diện", type="primary"):
        if 'detected_parts' in locals() and detected_parts:
            with st.spinner("AI đang rà soát hình học DXF và đánh giá rủi ro..."):
                current_tool_dia = tool_dia if 'tool_dia' in locals() else 3.0
                current_feed_rate = feed_rate if 'feed_rate' in locals() else 1200
                
                ai_report = ai_dxf_and_risk_analysis(
                    api_key_input, detected_parts, selected_material, 
                    current_tool_dia, current_feed_rate, current_cut_z
                )
                st.markdown(ai_report)
        else:
            st.warning("⚠️ Vui lòng tải file DXF lên trước khi chạy phân tích AI.")
