import tkinter as tk
from gui import CutterDashboard

def main():
    # Khởi tạo lõi giao diện Tkinter nền tảng gốc
    root = tk.Tk()
    
    # Khởi tạo Dashboard điều khiển trung tâm
    app = CutterDashboard(root)
    
    # Giữ cho vòng lặp phần mềm chạy liên tục bảo toàn trạng thái
    root.mainloop()

if __name__ == "__main__":
    main()