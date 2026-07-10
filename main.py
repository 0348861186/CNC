import streamlit as st
import os
import math
import plotly.graph_objects as go

from dxf_reader import DXFReader
from part_detector import PartDetector
from toolpath import ToolpathGenerator
from gcode_writer import GCodeWriter


# ==========================================
# CẤU HÌNH TRANG
# ==========================================

st.set_page_config(layout="wide")

st.title("CAM DXF Cutter Control Dashboard - Web Phiên Bản Cao Cấp")


# Chia layout
col_sidebar, col_display = st.columns([1, 2])


# ==========================================
# CỘT TRÁI - CẤU HÌNH
# ==========================================

with col_sidebar:

    st.header("⚙️ Cấu hình vận hành")


    uploaded_file = st.file_uploader(
        "📂 Tải File DXF Bản Vẽ",
        type=["dxf"]
    )


    tool_dia = st.number_input(
        "Đường kính dao (mm):",
        value=3.0,
        step=0.1
    )


    feed_rate = st.number_input(
        "Tốc độ cắt F (mm/phút):",
        value=1200,
        step=100
    )


    cut_z = st.number_input(
        "Độ sâu cắt Z (mm):",
        value=-2.0,
        step=0.5
    )


    lead_len = st.number_input(
        "Chiều dài đường mồi (mm):",
        value=5.0,
        step=0.5
    )


    mode_option = st.selectbox(
        "Chế độ bù dao:",
        [
            "Bù bán kính dao",
            "Không bù dao (Chạy trên nét)"
        ]
    )


    mode_str = (
        "compensation"
        if mode_option == "Bù bán kính dao"
        else "online"
    )


    st.subheader("💰 Cấu hình báo giá")


    g00_speed = st.number_input(
        "Tốc độ chạy nhanh G00 (mm/phút):",
        value=5000,
        step=500
    )


    cost_per_minute = st.number_input(
        "Chi phí máy (VNĐ/phút):",
        value=2000,
        step=500
    )



# ==========================================
# CỘT PHẢI - XỬ LÝ
# ==========================================

with col_display:


    if uploaded_file is not None:


        st.success(
            f"Đã nạp file: {uploaded_file.name}"
        )


        try:


            # ------------------------------
            # LƯU FILE TẠM
            # ------------------------------

            temp_filename = "temp_" + uploaded_file.name


            with open(temp_filename, "wb") as f:
                f.write(uploaded_file.getbuffer())



            # ------------------------------
            # ĐỌC DXF
            # ------------------------------

            reader = DXFReader(temp_filename)

            raw_lines = reader.read_entities()


            detector = PartDetector()

            detected_parts = detector.detect_parts(raw_lines)



            if os.path.exists(temp_filename):
                os.remove(temp_filename)



            st.info(
                f"Tìm thấy {len(detected_parts)} chi tiết kín."
            )



            # ------------------------------
            # SẮP XẾP THỨ TỰ CẮT
            # ------------------------------

            st.subheader(
                "🔄 Sắp xếp thứ tự cắt"
            )


            part_options = [
                f"Chi tiết số: {p['id']}"
                for p in detected_parts
            ]


            ordered_selection = st.multiselect(
                "Chọn thứ tự chạy dao:",
                options=part_options,
                default=part_options
            )



            final_ordered_parts = []


            for name in ordered_selection:

                part_id = int(
                    name.replace(
                        "Chi tiết số: ",
                        ""
                    )
                )


                for part in detected_parts:

                    if part["id"] == part_id:

                        final_ordered_parts.append(part)

                        break



            if not final_ordered_parts:

                final_ordered_parts = detected_parts



            # ------------------------------
            # TẠO TOOLPATH
            # ------------------------------

            generator = ToolpathGenerator(
                tool_diameter=tool_dia,
                feed_rate=feed_rate,
                lead_length=lead_len
            )


            raw_paths = generator.generate(
                final_ordered_parts,
                mode=mode_str
            )



            optimized_paths = []


            for item in raw_paths:

                for sub in item["coords"]:

                    optimized_paths.append(
                        {
                            "type": item["type"],
                            "feed": item["feed"],
                            "points": sub
                        }
                    )



            # ------------------------------
            # TÍNH CHI PHÍ
            # ------------------------------

            st.subheader(
                "⏱️ Thống kê gia công"
            )


            total_g01_len = 0

            total_g00_len = 0


            current_x = 0
            current_y = 0



            for path in optimized_paths:


                pts = path["points"]


                sx, sy = pts[0]


                total_g00_len += math.sqrt(
                    (sx-current_x)**2 +
                    (sy-current_y)**2
                )



                for i in range(len(pts)-1):

                    x1,y1 = pts[i]

                    x2,y2 = pts[i+1]


                    total_g01_len += math.sqrt(
                        (x2-x1)**2 +
                        (y2-y1)**2
                    )



                current_x,current_y = pts[-1]



            time_cut = (
                total_g01_len/feed_rate
                if feed_rate>0 else 0
            )


            time_fast = (
                total_g00_len/g00_speed
                if g00_speed>0 else 0
            )


            total_time = time_cut + time_fast


            cost = total_time * cost_per_minute



            m1,m2,m3 = st.columns(3)


            m1.metric(
                "Thời gian",
                f"{int(total_time)} phút"
            )


            m2.metric(
                "Chiều dài cắt",
                f"{total_g01_len:.1f} mm"
            )


            m3.metric(
                "Chi phí",
                f"{cost:,.0f} VNĐ"
            )



            # ------------------------------
            # HIỂN THỊ PLOTLY
            # ------------------------------

            st.subheader(
                "📊 Mô phỏng đường chạy dao"
            )


            fig = go.Figure()


            cx,cy = 0,0



            for idx,path in enumerate(optimized_paths):


                pts = path["points"]


                xs,ys = zip(*pts)


                sx,sy = pts[0]



                fig.add_trace(
                    go.Scatter(
                        x=[cx,sx],
                        y=[cy,sy],
                        mode="lines",
                        line=dict(
                            dash="dot"
                        ),
                        showlegend=False
                    )
                )



                fig.add_trace(
                    go.Scatter(
                        x=xs,
                        y=ys,
                        mode="lines",
                        name=f"Cắt #{idx+1}"
                    )
                )



                cx,cy = pts[-1]



            fig.update_layout(

                xaxis_title="X (mm)",

                yaxis_title="Y (mm)",

                height=600,

                yaxis=dict(
                    scaleanchor="x"
                )
            )



            st.plotly_chart(
                fig,
                use_container_width=True
            )



            # ------------------------------
            # XUẤT GCODE
            # ------------------------------

            st.subheader(
                "💾 Xuất G-code"
            )


            try:

                writer = GCodeWriter(
                    optimized_paths
                )

                gcode_text = writer.write()



            except:


                gcode_text = (
                    "(Generated G-Code)\n"
                    "G21\n"
                    "G90\n"
                )


                for path in optimized_paths:

                    for x,y in path["points"]:

                        gcode_text += (
                            f"G1 X{x:.3f} "
                            f"Y{y:.3f} "
                            f"F{feed_rate}\n"
                        )



            st.download_button(

                label="📥 Tải file G-code (.nc)",

                data=gcode_text,

                file_name=
                uploaded_file.name.replace(
                    ".dxf",
                    ".nc"
                ),

                mime="text/plain"

            )



        except Exception as e:


            st.error(
                f"Lỗi hệ thống: {e}"
            )



    else:


        st.info(
            "Vui lòng tải file DXF để bắt đầu."
        )
