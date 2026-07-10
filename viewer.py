import matplotlib.pyplot as plt

def draw_paths(optimized_paths, ax=None):
    """
    Hàm vẽ đường cắt CNC chuẩn hóa cho giao diện Web.
    Nhận vào danh sách đường đi và trục tọa độ ax của Matplotlib.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 6))
    
    # Duyệt qua từng đường cắt trong danh sách để vẽ
    for path in optimized_paths:
        # Giả định path của bạn chứa danh sách các điểm dạng tọa độ [(x1, y1), (x2, y2), ...]
        # Tách tọa độ X và Y để vẽ
        x_coords = [point[0] for point in path]
        y_coords = [point[1] for point in path]
        
        # Vẽ đường cắt lên trục tọa độ
        ax.plot(x_coords, y_coords, marker='o', linestyle='-', linewidth=1.5)
        
    ax.set_title("Mo phỏng duong cat CNC")
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.grid(True)
    ax.set_aspect('equal', adjustable='box')
