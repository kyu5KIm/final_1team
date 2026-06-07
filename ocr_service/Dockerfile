FROM python:3.10-slim
RUN pip install fastapi uvicorn easyocr
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]