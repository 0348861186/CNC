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
    (Trong thực tế, bạn sẽ dùng pd.read_csv('history_cnc_logs.csv'))
    """
    # Dữ liệu mẫu lịch sử: [Chiều dài G01, Chiều dài G00, Số lần nhấc dao, Độ sâu Z] -> Thời gian thực tế (phút)
    X_train = np.array([
        [1000, 200, 5, -2.0],
        [2500, 500, 12, -5.0],
        [5000, 1200, 20, -10.0],
        [800, 150, 3, -1.0],
        [3200, 800, 15, -3.0]
    ])
    y_train = np.array([1.2, 3.1, 6.8, 0.9, 4.2]) # Thời gian thực tế đo bằng đồng hồ trên máy

    model = RandomForestRegressor(n_estimators=10, random_state=42)
    model.fit(X_train, y_train)
    return model

ml_model = train_dummy_cost_ml_model()

def predict_real_machine_time(total_g01, total_g00, part_count, cut_z):
    """Sử dụng mô hình ML để dự đoán thời gian thực tế (có tính độ trễ máy/tăng giảm tốc)"""
    features = np.array([[total_g01, total_g00, part_count, cut_z]])
    predicted_time = ml_model.predict(features)[0]
    return predicted_time

# ==========================================
# LOẠI 2 & LOẠI 1: AI CHECK LỖI DXF & TƯ VẤN THÔNG SỐ (GỌI LLM)
# ==========================================
def ai_dxf_and_risk_analysis(api_key, detected_parts, material, tool_dia, feed_rate, cut_z):
    """
    Hàm kết hợp cả LOẠI 1 (Tư vấn chế độ cắt) và LOẠI 2 (Kiểm tra hình học DXF)
    """
    if not api_key:
        return "⚠️ Vui lòng nhập OpenAI / Gemini API Key để khởi chạy AI."

    # Tổng hợp dữ liệu hình học DXF để AI kiểm tra lỗi (LOẠI 2)
    part_summary = []
    for p in detected_parts:
        pts = p.get("points", [])
        part_summary.append({
            "id": p.get("id"),
            "point_count": len(pts),
            "is_closed": pts[0] == pts[-1] if pts else False
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
    1. 🔍 **Rà soát Lỗi DXF (Loại 2)**: Kiểm tra các chi tiết có kín không (`is_closed`), số lượng điểm có bất thường không. Bán kính dao {tool_dia}mm có nguy cơ không chui vừa các hốc nhỏ không?
    2. ⚠️ **Phân tích Rủi ro & Chế độ cắt (Loại 1)**: Thông số F={feed_rate}, Z={cut_z} cho vật liệu {material} đã tối ưu chưa? Có nguy cơ gãy dao hoặc bavia không?
    3. 💡 **Đề xuất hiệu chỉnh**: Hướng dẫn kỹ sư điều chỉnh cụ thể.
    """

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Lỗi kết nối AI: {e}"

# ==========================================
# TÍCH HỢP VÀO GIAO DIỆN STREAMLIT
# ==========================================
# (Đoạn này đặt trong Tab "🤖 AI Control Center")
tab_sim, tab_gcode, tab_ai = st.tabs(["📊 Mô phỏng 2D", "💾 Xuất G-Code", "🤖 AI Control Center"])

with tab_ai:
    st.subheader("🤖 Trung tâm Trợ lý AI & Machine Learning")
    
    # 1. Hiển thị dự đoán Machine Learning (LOẠI 3)
    st.markdown("### 📈 1. Dự đoán thời gian & Chi phí thực tế (Machine Learning)")
    
    # Giả định lấy được thông số tính toán từ bước trước
    demo_g01 = 3500.0 # mm
    demo_g00 = 800.0  # mm
    demo_parts = len(detected_parts) if 'detected_parts' in locals() else 5
    demo_z = -2.0

    real_time_pred = predict_real_machine_time(demo_g01, demo_g00, demo_parts, demo_z)
    real_cost_pred = real_time_pred * cost_per_minute

    c1, c2 = st.columns(2)
    c1.metric("⏱️ Thời gian thực tế máy chạy (ML dự đoán)", f"{real_time_pred:.2f} phút")
    c2.metric("💰 Chi phí thực tế ước tính (ML dự đoán)", f"{real_cost_pred:,.0f} VNĐ")
    st.caption("ℹ️ *Mô hình ML dự đoán dựa trên thời gian tăng/giảm tốc thực tế của động cơ và lịch sử các lần chạy trước.*")

    st.divider()

    # 2. Hiển thị Phân tích AI LLM (LOẠI 1 & LOẠI 2)
    st.markdown("### 🔍 2. AI Kiểm tra Lỗi DXF & Tư vấn Thông số Gia công (LLM API)")
    
    api_key_input = st.text_input("Nhập OpenAI API Key để kích hoạt AI:", type="password")
    selected_material = st.selectbox("Vật liệu phôi cắt:", ["Nhôm 6061", "Gỗ Plywood", "Mica/Acrylic", "Thép C45"])

    if st.button("🚀 Chạy kiểm tra AI Toàn diện", type="primary"):
        if 'detected_parts' in locals():
            with st.spinner("AI đang rà soát hình học DXF và đánh giá rủi ro..."):
                ai_report = ai_dxf_and_risk_analysis(
                    api_key_input, detected_parts, selected_material, tool_dia, feed_rate, cut_z
                )
                st.markdown(ai_report)
        else:
            st.warning("Vui lòng tải file DXF lên trước khi chạy phân tích AI.")
