from shapely.geometry import Polygon, MultiLineString
from shapely.ops import polygonize

class PartDetector:
    def __init__(self):
        pass

    def detect_parts(self, raw_lines):
        """Kết nối các đường nét rời rạc thành các khối đa giác kín (Parts)"""
        if not raw_lines:
            return []

        # Chuyển đổi dữ liệu thô thành đối tượng MultiLineString của Shapely
        mls = MultiLineString(raw_lines)
        
        # Tự động tìm kiếm và đóng kín các vùng tạo thành Polygon
        polygons = list(polygonize(mls))
        
        parts_data = []
        for idx, poly in enumerate(polygons):
            # Lấy danh sách tọa độ đường viền ngoài cùng
            exterior_coords = list(poly.exterior.coords)
            
            # Lấy danh sách tọa độ các lỗ thủng bên trong (nếu có)
            interiors = [list(hole.coords) for hole in poly.interiors]
            
            parts_data.append({
                'id': idx + 1,
                'exterior': exterior_coords,
                'interiors': interiors,
                'polygon_obj': poly # Lưu lại đối tượng gốc phục vụ tính toán hình học
            })
            
        return parts_data