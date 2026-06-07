from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from chat.router_gemma import router
import httpx, os

app = FastAPI(title="Meeting AI Pipeline")
app.include_router(router)

LLM_URL = os.getenv("LLM_URL", "http://localhost:8001")
STT_URL = os.getenv("STT_URL", "http://localhost:8002")
OCR_URL = os.getenv("OCR_URL", "http://localhost:8003")

class TextInput(BaseModel):
    text: str

def call_llm(prompt: str) -> str:
    payload = {
        "model": "gemma",  # vLLM은 모델명 아무거나 줘도 됨
        "messages": [
            {"role": "system", "content": "반드시 한국어로만 답해라. 최종 답변만 출력해라."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
        "temperature": 0.0
    }
    resp = httpx.post(f"{LLM_URL}/v1/chat/completions", json=payload, timeout=60)
    return resp.json()["choices"][0]["message"]["content"].strip()

@app.post("/agenda")
async def generate_agenda(file: UploadFile = File(...)):
    image_bytes = await file.read()
    ocr_resp = httpx.post(f"{OCR_URL}/ocr", files={"file": image_bytes}, timeout=30)
    ocr_text = ocr_resp.json()["text"]
    prompt = f"다음 문서를 바탕으로 회의 기초안건을 작성해줘:\n{ocr_text}"
    return {"agenda": call_llm(prompt)}

@app.post("/stt")
async def transcribe(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    stt_resp = httpx.post(f"{STT_URL}/transcribe", files={"file": audio_bytes}, timeout=60)
    return {"transcript": stt_resp.json()["transcript"]}

@app.post("/tasks")
def extract_tasks(body: TextInput):
    prompt = f"다음 회의 내용에서 담당자와 할일 목록을 추출해줘:\n{body.text}"
    return {"tasks": call_llm(prompt)}

@app.post("/summary")
def summarize(body: TextInput):
    prompt = f"다음 회의 내용을 3~5줄로 요약해줘:\n{body.text}"
    return {"summary": call_llm(prompt)}