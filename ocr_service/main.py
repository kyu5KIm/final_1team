from fastapi import FastAPI, UploadFile, File
import easyocr

app = FastAPI()
reader = easyocr.Reader(['ko', 'en'])

@app.post("/ocr")
async def ocr(file: UploadFile = File(...)):
    image_bytes = await file.read()
    result = reader.readtext(image_bytes, detail=0)
    return {"text": "\n".join(result)}