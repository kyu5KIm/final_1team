from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from stt import transcribe_audio
from ocr import extract_text_from_image
from llm_gemma import call_llm
from chat.router_gemma import router

app = FastAPI(title="Meeting AI Pipeline - Gemma")
app.include_router(router)

class TextInput(BaseModel):
    text: str

@app.post("/agenda")
def generate_agenda(file: UploadFile = File(...)):
    ocr_text = extract_text_from_image(file.file.read())
    prompt = f"다음 문서를 바탕으로 회의 기초안건을 작성해줘:\n{ocr_text}"
    return {"agenda": call_llm(prompt)}

@app.post("/stt")
def transcribe(file: UploadFile = File(...)):
    transcript = transcribe_audio(file.file.read())
    return {"transcript": transcript}

@app.post("/tasks")
def extract_tasks(body: TextInput):
    prompt = f"다음 회의 내용에서 담당자와 할일 목록을 추출해줘:\n{body.text}"
    return {"tasks": call_llm(prompt)}

@app.post("/summary")
def summarize(body: TextInput):
    prompt = f"다음 회의 내용을 3~5줄로 요약해줘:\n{body.text}"
    return {"summary": call_llm(prompt)}