import ezdxf

class DXFReader:
    def __init__(self, file_path):
        self.file_path = file_path
        self.doc = None
        self.msp = None

    def read_entities(self):
        """Đọc file DXF và chuyển đổi các thực thể thành danh sách các chuỗi tọa độ (polyline)"""
        try:
            self.doc = ezdxf.readfile(self.file_path)
            self.msp = self.doc.modelspace()
        except IOError:
            print(f"Không thể mở file: {self.file_path}")
            return []
        except ezdxf.DXFStructureError:
            print(f"File DXF bị lỗi cấu trúc: {self.file_path}")
            return []

        raw_lines = []

        # Đọc các đoạn thẳng (LINE)
        for entity in self.msp.query('LINE'):
            start = (entity.dxf.start.x, entity.dxf.start.y)
            end = (entity.dxf.end.x, entity.dxf.end.y)
            raw_lines.append([start, end])

        # Đọc các đường đa tuyến (LWPOLYLINE / POLYLINE)
        for entity in self.msp.query('LWPOLYLINE POLYLINE'):
            points = [(pt[0], pt[1]) for pt in entity.get_points(format='xy')]
            if entity.is_closed:
                points.append(points[0])
            if len(points) > 1:
                raw_lines.append(points)

        # Đọc đường tròn (CIRCLE) - Tự động xấp xỉ thành hình đa giác 64 cạnh
        for entity in self.msp.query('CIRCLE'):
            center = entity.dxf.center
            radius = entity.dxf.radius
            points = []
            import math
            for i in range(65):
                angle = math.radians(i * (360 / 64))
                x = center.x + radius * math.cos(angle)
                y = center.y + radius * math.sin(angle)
                points.append((x, y))
            raw_lines.append(points)

        return raw_lines