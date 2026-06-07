from fastapi import FastAPI, UploadFile, File
import whisperx
import tempfile, os

app = FastAPI()
model = whisperx.load_model("large-v2", device="cuda", compute_type="float16")

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    
    audio = whisperx.load_audio(tmp_path)
    result = model.transcribe(audio, batch_size=16)
    os.remove(tmp_path)
    
    text = " ".join([seg["text"] for seg in result["segments"]])
    return {"transcript": text}