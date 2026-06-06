import whisper
import tempfile, os

stt_model = whisper.load_model("base")

def transcribe_audio(file_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    result = stt_model.transcribe(tmp_path, language="ko")
    os.remove(tmp_path)
    return result["text"]

