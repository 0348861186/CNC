import math
from shapely.geometry import Polygon

class ToolpathGenerator:
    def __init__(self, tool_diameter=3.0, feed_rate=1500, lead_length=5.0):
        self.tool_radius = float(tool_diameter) / 2
        self.feed_rate = int(feed_rate)
        self.lead_length = float(lead_length) # Độ dài đường mồi (mm)

    def _add_lead_in_out(self, coords):
        """Tự động tính toán điểm mồi nhô ra ngoài góc vuông"""
        if len(coords) < 3:
            return coords

        # Lấy điểm đầu tiên (góc xuất phát) và điểm kế tiếp để tính góc hướng đi
        p0 = coords[0]
        p1 = coords[1]
        p_last = coords[-2] # Điểm áp chót trước khi đóng vòng

        # Tính toán hướng vector của cạnh đầu tiên để phóng đường mồi ngược lại
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        angle = math.atan2(dy, dx)

        # Tính toán tọa độ điểm Lead-in (lùi lại ngược hướng cắt 45 độ ra ngoài)
        lead_in_x = p0[0] - self.lead_length * math.cos(angle - math.pi/4)
        lead_in_y = p0[1] - self.lead_length * math.sin(angle - math.pi/4)
        lead_in_point = (lead_in_x, lead_in_y)

        # Tính toán tọa độ điểm Lead-out (tiếp tục lao ra ngoài sau khi cắt xong)
        dx_out = p0[0] - p_last[0]
        dy_out = p0[1] - p_last[1]
        angle_out = math.atan2(dy_out, dx_out)
        
        lead_out_x = p0[0] + self.lead_length * math.cos(angle_out)
        lead_out_y = p0[1] + self.lead_length * math.sin(angle_out)
        lead_out_point = (lead_out_x, lead_out_y)

        # Tạo chuỗi hành trình mới: Điểm mồi -> Đường cắt gốc -> Điểm ra dao
        new_coords = [lead_in_point] + list(coords) + [lead_out_point]
        return new_coords

    def generate(self, parts, mode="compensation"):
        processed_paths = []

        for part in parts:
            poly = part['polygon_obj']
            
            if mode == "online" or self.tool_radius <= 0:
                # Chế độ KHÔNG BÙ DAO
                coords_list = [part['exterior']]
            else:
                # Chế độ BÙ DAO
                offset_exterior = poly.buffer(self.tool_radius, cap_style=3, join_style=2)
                if not offset_exterior.is_empty:
                    if offset_exterior.geom_type == 'MultiPolygon':
                        poly_target = list(offset_exterior.geoms)[0]
                    else:
                        poly_target = offset_exterior
                    coords_list = [list(poly_target.exterior.coords)]
                else:
                    continue

            # Áp dụng đường mồi Lead-in/Lead-out vào tọa độ cắt
            for coords in coords_list:
                if self.lead_length > 0:
                    final_coords = self._add_lead_in_out(coords)
                else:
                    final_coords = coords

                processed_paths.append({
                    'type': 'exterior', 
                    'coords': [final_coords], 
                    'feed': self.feed_rate
                })

        return processed_paths