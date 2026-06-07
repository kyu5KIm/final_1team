FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04
RUN apt-get update && apt-get install -y python3-pip ffmpeg
RUN pip install fastapi uvicorn whisperx
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]