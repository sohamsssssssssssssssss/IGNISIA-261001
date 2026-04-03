import camelot
from paddleocr import PaddleOCR
from typing import Dict, Any, List

class PDFOcrService:
    def __init__(self):
        # Initialize PaddleOCR
        # use_angle_cls=True to detect text orientation
        self.ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)

    def extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text from scanned PDF/image using PaddleOCR.
        Returns extracted fields with confidence scores.
        """
        result = self.ocr.ocr(file_path, cls=True)
        extracted_fields = []
        overall_confidence = 0.0
        count = 0
        
        # result is a list of lines, each line is a list of bounding boxes and text
        # Example format: [[[[x1,y1], [x2,y2], ...], ('Text', confidence_score)], ...]
        if not result or not result[0]:
            return {"fields": [], "average_confidence": 0.0, "requires_manual_review": True}
            
        for line in result[0]:
            if len(line) == 2:
                bbox, (text, conf) = line
                extracted_fields.append({
                    "text": text,
                    "confidence": float(conf),
                    "bbox": bbox
                })
                overall_confidence += conf
                count += 1
                
        avg_conf = overall_confidence / count if count > 0 else 0.0
        
        # Fields with < 0.75 conf flag for officer review. Avg < 0.5 escalates document.
        requires_manual_review = avg_conf < 0.50
        review_fields = [f for f in extracted_fields if f["confidence"] < 0.75]
        
        return {
            "fields": extracted_fields,
            "average_confidence": avg_conf,
            "requires_manual_review": requires_manual_review,
            "review_queue_fields": review_fields
        }

    def extract_tables(self, file_path: str) -> List[Any]:
        """
        Extract tabular financial data using Camelot (lattice mode).
        """
        # Camelot reads PDF files
        tables = camelot.read_pdf(file_path, flavor='lattice', pages='all')
        
        parsed_tables = []
        for table in tables:
            parsed_tables.append({
                "page": table.page,
                "accuracy": table.accuracy,
                "whitespace": table.whitespace,
                "df": table.df  # Pandas DataFrame
            })
            
        return parsed_tables
