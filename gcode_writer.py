class GCodeWriter:
    def __init__(self, safe_z=5.0, cut_z=-2.0, travel_feed=3000):
        self.safe_z = safe_z          # Cao độ di chuyển nhanh an toàn không cắt
        self.cut_z = cut_z            # Độ sâu âm xuống để cắt đứt vật liệu
        self.travel_feed = travel_feed  # Tốc độ di chuyển nhanh G0 (mm/phút)

    def save(self, optimized_paths, file_path):
        """Ghi dữ liệu ra file vật lý cấu trúc mở rộng .nc hoặc .gcode"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # Thiết lập ban đầu (Header)
                f.write("; --- BAN MA G-CODE DUOC TAO BOI DXF_CUTTER ---\n")
                f.write("G21 ; Thang do: Milimet\n")
                f.write("G90 ; He toa do: Tuyet doi\n")
                f.write(f"G0 Z{self.safe_z} F{self.travel_feed} ; Nhấc dao an toàn\n\n")

                for idx, path in enumerate(optimized_paths):
                    pts = path['points']
                    f.write(f"; -> Bat dau duong cat so {idx+1} ({path['type'].upper()})\n")
                    
                    # 1. Di chuyển nhanh đến điểm bắt đầu trên mặt phẳng XY
                    f.write(f"G0 X{pts[0][0]:.3f} Y{pts[0][1]:.3f}\n")
                    
                    # 2. Đâm dao xuống độ sâu cắt
                    f.write(f"G1 Z{self.cut_z} F500\n")
                    
                    # 3. Tiến hành nội suy cắt theo biên dạng với tốc độ Feedrate chỉ định
                    for pt in pts[1:]:
                        f.write(f"G1 X{pt[0]:.3f} Y{pt[1]:.3f} F{path['feed']}\n")
                    
                    # 4. Cắt xong đường này, nhấc dao lên trước khi sang vị trí mới
                    f.write(f"G0 Z{self.safe_z}\n\n")

                # Kết thúc chương trình (Footer)
                f.write("; --- KET THUC CHUONG TRINH ---\n")
                f.write("M5 ; Tat truc quay / nguon laser\n")
                f.write("G0 X0 Y0 ; Quay ve goc toa do may\n")
                f.write("M30 ; Reset chuong trinh\n")
            return True
        except Exception as e:
            print(f"Lỗi ghi file G-code: {e}")
            return False