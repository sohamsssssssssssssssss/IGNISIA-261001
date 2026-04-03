import json
from app.models.gstr import GSTR1, GSTR2A, GSTR3B

class GSTParser:
    @staticmethod
    def parse_gstr1(file_path: str) -> GSTR1:
        with open(file_path, 'r') as f:
            data = json.load(f)
        # Parse logic here
        return GSTR1(**data)
        
    @staticmethod
    def parse_gstr2a(file_path: str) -> GSTR2A:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return GSTR2A(**data)

    @staticmethod
    def parse_gstr3b(file_path: str) -> GSTR3B:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return GSTR3B(**data)
