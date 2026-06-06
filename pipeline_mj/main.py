from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from huggingface_hub import InferenceClient
import whisper
from dotenv import load_dotenv
import easyocr
import tempfile, os

load_dotenv()
app = FastAPI()


HF_TOKEN = os.getenv("HF_TOKEN" )
MODEL_NAME = "LGAI-EXAONE/EXAONE-4.0-32B"

client = InferenceClient(model=MODEL_NAME, token=HF_TOKEN)
stt_model = whisper.load_model("base")
ocr_reader = easyocr.Reader(["ko", "en"])



class TextInput(BaseModel):
    text: str

class ChatInput(BaseModel):
    question: str

def call_llm(prompt: str) -> str:
    return client.text_generation(prompt, max_new_tokens=1024)




# 기초 안건 생성
@app.post("/agenda")
def generate_agenda(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    ocr_result = ocr_reader.readtext(tmp_path, detail=0)
    ocr_text = " ".join(ocr_result)
    os.remove(tmp_path)

    prompt = f"다음 문서를 바탕으로 회의 기초안건을 작성해줘:\n{ocr_text}"
    result = call_llm(prompt)

    return {"agenda": result}

# STT 원문 출력. 음성 -> 텍스트
@app.post("/stt")
def transcribe(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

        result = stt_model.transcribe(tmp_path, language="ko")
        os.remove(tmp_path)

        return {"transcript": result["text"]}


# 태스크 추출 (원문 -> 할일 목록)
@app.post("/tasks")
def extract_tasks(body: TextInput):
    prompt = f"다음 회의 내용에서 할일 목록을 추출해줘:\n{body.text}"
    result = call_llm(prompt)

    return {"tasks": result}


# 요약 생성
@app.post("/summary")
def summarize(body: TextInput):
    prompt = f"다음 회의 내용을 요약해줘:\n{body.text}"
    result = call_llm(prompt)

    return {"summary": result}



# 나중에 작업. RAG
@app.post("/chat")
def chat(body: ChatInput):
    retrieved_docs = "검색된 문서 (임시)"

    prompt = f"참고문서: {retrieved_docs}\n질문: {body.question}"
    result = call_llm(prompt)

    return {"answer": result}