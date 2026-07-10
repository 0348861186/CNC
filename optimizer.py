import math

class PathOptimizer:
    def __init__(self):
        pass

    def _get_distance(self, p1, p2):
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    def optimize(self, raw_paths, start_point=(0, 0)):
        """Sắp xếp lại thứ tự hành trình của các đường cắt để tối ưu quãng đường trống"""
        # Phẳng hóa danh sách đường cắt (tách lẻ từng đường biên)
        flat_paths = []
        for item in raw_paths:
            for sub_path in item['coords']:
                flat_paths.append({
                    'type': item['type'],
                    'feed': item['feed'],
                    'points': sub_path
                })

        optimized = []
        current_pos = start_point

        while flat_paths:
            # Tìm kiếm đường đi có điểm bắt đầu gần vị trí hiện tại của đầu cắt nhất
            nearest_idx = min(
                range(len(flat_paths)),
                key=lambda i: self._get_distance(current_pos, flat_paths[i]['points'][0])
            )
            target_path = flat_paths.pop(nearest_idx)
            optimized.append(target_path)
            # Cập nhật vị trí kết thúc của đầu cắt làm vị trí hiện tại mới
            current_pos = target_path['points'][-1]

        return optimized