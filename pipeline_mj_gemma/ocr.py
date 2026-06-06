import easyocr
import tempfile, os

ocr_reader = easyocr.Reader(["ko", "en"])

def extract_text_from_image(file_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    result = ocr_reader.readtext(tmp_path, detail=0)
    os.remove(tmp_path)
    return " ".join(result)