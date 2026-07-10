import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class DXFViewer:
    def __init__(self):
        # Tạo khung chứa đồ thị
        self.fig, self.ax = plt.subplots(figsize=(6, 5), dpi=100)
        self.ax.set_aspect('equal')
        self.ax.grid(True, linestyle='--', alpha=0.5)
        self.canvas = None          # Lưu đối tượng vẽ Matplotlib
        self.canvas_widget = None   # Lưu widget giao diện Tkinter

    def draw_parts(self, parts, canvas_frame):
        """Vẽ chi tiết lên khung giao diện Tkinter"""
        self.ax.clear()
        self.ax.grid(True, linestyle='--', alpha=0.5)
        self.ax.set_title("Bản xem trước tọa độ chi tiết cắt", fontsize=10)

        if not parts:
            self.ax.text(0.5, 0.5, "Không có dữ liệu hình học", ha='center', va='center')
        else:
            for part in parts:
                # Vẽ đường bao ngoài màu xanh lam
                x_ext, y_ext = zip(*part['exterior'])
                self.ax.plot(x_ext, y_ext, color='blue', linewidth=2, label=f"Part {part['id']}" if part['id']==1 else "")
                
                # Vẽ các lỗ bên trong màu đỏ (nếu có)
                for hole in part['interiors']:
                    x_hole, y_hole = zip(*hole)
                    self.ax.plot(x_hole, y_hole, color='red', linestyle='--', linewidth=1.5)

        # Xóa widget cũ nếu đã tồn tại để tránh đè giao diện
        if self.canvas_widget:
            self.canvas_widget.destroy()

        # Khởi tạo và nhúng đồ họa Matplotlib vào Tkinter Frame
        self.canvas = FigureCanvasTkAgg(self.fig, master=canvas_frame)
        self.canvas.draw()
        
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill='both', expand=True)