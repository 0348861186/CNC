import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from dxf_reader import DXFReader
from part_detector import PartDetector
from viewer import DXFViewer
from toolpath import ToolpathGenerator
from optimizer import PathOptimizer
from gcode_writer import GCodeWriter

class CutterDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("CAM DXF Cutter Control Dashboard - Thứ Tự Cắt Thủ Công")
        self.root.geometry("1100x650") # Mở rộng giao diện để chứa bảng danh sách
        
        self.raw_lines = []
        self.detected_parts = []
        self.viewer = DXFViewer()

        self._build_ui()

    def _build_ui(self):
        # Khu vực cài đặt thông số bên trái
        sidebar = tk.LabelFrame(self.root, text=" Cấu hình vận hành ", width=250, padx=10, pady=10)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        tk.Button(sidebar, text="📂 Tải File DXF Bản Vẽ", font=('Helvetica', 10, 'bold'), 
                  bg='#e1f5fe', command=self._action_load_dxf).pack(fill=tk.X, pady=8)

        tk.Label(sidebar, text="Đường kính dao (mm):").pack(anchor=tk.W, pady=(5,0))
        self.txt_tool_dia = tk.Entry(sidebar)
        self.txt_tool_dia.insert(0, "3.0")
        self.txt_tool_dia.pack(fill=tk.X, pady=2)

        tk.Label(sidebar, text="Tốc độ cắt F (mm/p):").pack(anchor=tk.W, pady=(5,0))
        self.txt_feed = tk.Entry(sidebar)
        self.txt_feed.insert(0, "1200")
        self.txt_feed.pack(fill=tk.X, pady=2)

        tk.Label(sidebar, text="Độ sâu cắt Z (mm):").pack(anchor=tk.W, pady=(5,0))
        self.txt_depth = tk.Entry(sidebar)
        self.txt_depth.insert(0, "-2.0")
        self.txt_depth.pack(fill=tk.X, pady=2)

        tk.Label(sidebar, text="Chiều dài đường mồi (mm):").pack(anchor=tk.W, pady=(5,0))
        self.txt_lead_len = tk.Entry(sidebar)
        self.txt_lead_len.insert(0, "5.0")
        self.txt_lead_len.pack(fill=tk.X, pady=2)

        tk.Label(sidebar, text="Chế độ bù mạch cắt:").pack(anchor=tk.W, pady=(5,0))
        self.cb_mode = ttk.Combobox(sidebar, values=["Bù bán kính dao", "Không bù dao (Chạy trên nét)"], state="readonly")
        self.cb_mode.current(0)
        self.cb_mode.pack(fill=tk.X, pady=2)

        tk.Button(sidebar, text="⚙️ Xử Lý & Xuất G-Code", font=('Helvetica', 10, 'bold'),
                  bg='#c8e6c9', command=self._action_export_gcode).pack(fill=tk.X, pady=20)

        # Bảng danh sách thứ tự cắt chi tiết ở giữa
        order_panel = tk.LabelFrame(self.root, text=" Thứ tự cắt chi tiết ", width=200, padx=5, pady=5)
        order_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        self.listbox_parts = tk.Listbox(order_panel, selectmode=tk.SINGLE, width=22)
        self.listbox_parts.pack(fill=tk.BOTH, expand=True, pady=5)
        
        btn_up = tk.Button(order_panel, text="🔼 Di chuyển lên", command=self._move_up)
        btn_up.pack(fill=tk.X, pady=2)
        
        btn_down = tk.Button(order_panel, text="🔽 Di chuyển xuống", command=self._move_down)
        btn_down.pack(fill=tk.X, pady=2)

        # Khu vực hiển thị bản vẽ đồ họa bên phải
        self.preview_panel = tk.LabelFrame(self.root, text=" Màn hình mô phỏng hình học đồ họa ")
        self.preview_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.viewer.draw_parts([], self.preview_panel)

    def _move_up(self):
        """Đẩy chi tiết được chọn lên trên trong danh sách cắt"""
        try:
            selected_idx = self.listbox_parts.curselection()
            if not selected_idx or selected_idx[0] == 0:
                return
            idx = selected_idx[0]
            # Hoán đổi trong mảng dữ liệu gốc
            self.detected_parts[idx], self.detected_parts[idx - 1] = \
                self.detected_parts[idx - 1], self.detected_parts[idx]
            self._update_listbox()
            self.listbox_parts.selection_set(idx - 1)
        except IndexError:
            pass

    def _move_down(self):
        """Đẩy chi tiết được chọn xuống dưới trong danh sách cắt"""
        try:
            selected_idx = self.listbox_parts.curselection()
            if not selected_idx or selected_idx[0] == len(self.detected_parts) - 1:
                return
            idx = selected_idx[0]
            # Hoán đổi trong mảng dữ liệu gốc
            self.detected_parts[idx], self.detected_parts[idx + 1] = \
                self.detected_parts[idx + 1], self.detected_parts[idx]
            self._update_listbox()
            self.listbox_parts.selection_set(idx + 1)
        except IndexError:
            pass

    def _update_listbox(self):
        """Cập nhật lại danh sách chữ hiển thị trên giao diện"""
        self.listbox_parts.delete(0, tk.END)
        for part in self.detected_parts:
            self.listbox_parts.insert(tk.END, f"Chi tiết số: {part['id']}")

    def _action_load_dxf(self):
        path = filedialog.askopenfilename(filetypes=[("AutoCAD DXF", "*.dxf")])
        if not path:
            return

        reader = DXFReader(path)
        self.raw_lines = reader.read_entities()

        detector = PartDetector()
        self.detected_parts = detector.detect_parts(self.raw_lines)

        self.viewer.draw_parts(self.detected_parts, self.preview_panel)
        self._update_listbox() # Cập nhật danh sách chi tiết lên bảng điều khiển
        messagebox.showinfo("Thành công", f"Đã nạp bản vẽ! Tìm thấy {len(self.detected_parts)} chi tiết kín.")

    def _action_export_gcode(self):
        if not self.detected_parts:
            messagebox.showwarning("Cảnh báo", "Bạn chưa tải hoặc chưa có dữ liệu cấu trúc chi tiết nào!")
            return

        try:
            tool_dia = float(self.txt_tool_dia.get())
            feed_rate = float(self.txt_feed.get())
            cut_z = float(self.txt_depth.get())
            lead_len = float(self.txt_lead_len.get())
        except ValueError:
            messagebox.showerror("Lỗi dữ liệu", "Vui lòng kiểm tra lại các thông số nhập vào!")
            return

        mode_str = "compensation" if self.cb_mode.current() == 0 else "online"

        # Sử dụng mảng self.detected_parts đã được người dùng sắp xếp thủ công qua nút bấm Lên/Xuống
        gen = ToolpathGenerator(tool_diameter=tool_dia, feed_rate=feed_rate, lead_length=lead_len)
        raw_paths = gen.generate(self.detected_parts, mode=mode_str)

        # Phẳng hóa danh sách đường cắt tương thích với cấu hình thủ công
        optimized_paths = []
        for item in raw_paths:
            for sub_path in item['coords']:
                optimized_paths.append({
                    'type': item['type'],
                    'feed': item['feed'],
                    'points': sub_path
                })

        # ĐỒ HỌA THỰC TẾ - Vẽ lại dựa trên thứ tự mới sắp xếp
        self.viewer.ax.clear()
        self.viewer.ax.grid(True, linestyle='--', alpha=0.5)
        self.viewer.ax.set_title("Mô phỏng chạy dao theo thứ tự chỉ định", fontsize=10)
        
        # Biến lưu vị trí dao hiện tại tách biệt trục X và trục Y để tránh lỗi Numpy phẳng mảng
        current_x, current_y = 0.0, 0.0
        
        for idx, path in enumerate(optimized_paths):
            pts = path['points']
            x_pts, y_pts = zip(*pts)
            start_x, start_y = pts[0][0], pts[0][1]
            
            # CHUẨN HÓA MỚI: Truyền mảng tọa độ X [X_cũ, X_mới] và Y [Y_cũ, Y_mới] tách biệt hoàn toàn để triệt tiêu lỗi gộp mảng inhomogeneous
            self.viewer.ax.plot([current_x, start_x], [current_y, start_y], 
                                color='gray', linestyle=':', alpha=0.7, linewidth=1.5)
            
            # Vẽ đường cắt G1 kèm số thứ tự cắt lên trên hình để người dùng kiểm tra
            self.viewer.ax.plot(x_pts, y_pts, color='green', linewidth=2)
            
            # Đánh số thứ tự #1, #2, #3, #4 lên tâm hoặc góc chi tiết
            self.viewer.ax.text(start_x + 2, start_y + 2, f"#{idx+1}", color='purple', weight='bold', fontsize=12)
            
            if lead_len > 0:
                self.viewer.ax.plot(start_x, start_y, 'or', markersize=4)

            # Cập nhật tọa độ kết thúc của dao sang chi tiết tiếp theo
            current_x, current_y = float(pts[-1][0]), float(pts[-1][1])
            
        self.viewer.ax.plot(0, 0, 'ro', markersize=8, label="Gốc Máy (X0 Y0)")
        self.viewer.ax.legend(loc="upper right", fontsize=8)
        
        if self.viewer.canvas:
            self.viewer.canvas.draw()

        save_path = filedialog.asksaveasfilename(defaultextension=".nc", 
                                                 filetypes=[("G-Code NC", "*.nc"), ("Tap File", "*.tap")])
        if save_path:
            writer = GCodeWriter(safe_z=5.0, cut_z=cut_z)
            if writer.save(optimized_paths, save_path):
                messagebox.showinfo("Thành công", "File G-code đã xuất thành công theo thứ tự sắp xếp của bạn!")