# OCR Service

문서 또는 이미지 파일에서 텍스트를 추출하는 FastAPI 서버입니다. 기본 백엔드는 PaddleOCR-VL이며, 설정에 따라 Qwen VL 모델을 직접 로딩하는 경로도 가지고 있습니다.

## 역할

- PDF, 이미지 파일 업로드를 받아 OCR 수행
- OCR 결과를 텍스트로 정리해 반환
- 긴 OCR 작업을 위한 비동기 job API 제공
- GPU 작업 충돌을 줄이기 위한 lock 사용

## OCR 결과와 청킹 구조

OCR 서버의 직접 역할은 문서나 이미지에서 텍스트를 추출하는 것입니다. 추출된 텍스트는 이후 `ai/parsed` 단계에서 chunk로 나뉘고, Qdrant에 적재되어 RAG 검색에 사용됩니다.

기존에는 OCR 결과를 일정 길이 기준으로 단순 분할하는 flat chunk 구조에 가깝게 사용했습니다. 이 방식은 구현은 단순하지만, 문서의 제목, 페이지, 조문, 표, 섹션 같은 상위 문맥이 chunk 안에서 쉽게 끊기는 문제가 있었습니다.

그래서 문서 검색 품질을 높이기 위해 Hierarchical Parent-Child 구조로 바꿨습니다.

Hierarchical Parent-Child 구조는 문서를 하나의 평평한 chunk 목록으로만 보지 않고, "상위 문맥(parent)"과 "검색 단위(child)"를 함께 관리하는 방식입니다. parent는 원문에서 chunk가 속한 큰 단위이고, child는 실제 임베딩과 벡터 검색에 사용하는 작은 단위입니다.

| 구분 | 역할 |
| --- | --- |
| Parent | 문서, 페이지, 제목, 조문, 섹션, 표처럼 원문 구조를 설명하는 상위 문맥 |
| Child | 실제 embedding/search에 쓰기 좋은 작은 단위 텍스트 |

예를 들어 "정보보안 규정 PDF" 안에 "제3장 접근권한 관리"라는 섹션이 있고, 그 안에 "제12조 권한 부여" 본문이 있다면 parent는 문서명/장/조문/페이지 정보이고, child는 검색에 사용할 500~700 token 정도의 본문 조각입니다.

이 구조로 바꾼 이유는 다음과 같습니다.

- 작은 child chunk로 검색 정확도와 recall을 유지할 수 있습니다.
- 답변 생성 시에는 parent 문맥을 같이 참고해 내용이 중간에 끊기지 않습니다.
- OCR 문서에서 중요한 페이지, 제목, 조문 번호, 표 정보를 metadata로 유지할 수 있습니다.
- 법령/규정/회의자료처럼 계층이 중요한 문서에서 근거 추적이 쉬워집니다.
- 단순 길이 분할보다 표, 이미지 캡션, 본문을 구분하기 쉬워 RAG 답변 품질이 안정됩니다.

정리하면, child는 "잘 찾기 위한 단위"이고 parent는 "제대로 이해하기 위한 문맥"입니다.

## 주요 파일

| 파일 | 설명 |
| --- | --- |
| `ocr_server.py` | FastAPI 앱, OCR API, job 관리 |
| `config.py` | OCR 백엔드, 모델 ID, PaddleOCR-VL URL, 토큰 수 등 환경 설정 |
| `model_runtime.py` | Qwen OCR 모델 로딩/추론 로직 |
| `runtime_locks.py` | GPU 작업 lock |
| `schemas.py` | 공통 응답 모델 |
| `requirements-ocr.txt` | OCR 서버 의존성 |
| `runpod_start_paddleocr_wrapper.sh` | PaddleOCR-VL serving 실행 후 OCR 래퍼 서버 실행 |

## API

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/health` | 서버 상태, OCR 백엔드, CUDA 여부 확인 |
| `POST` | `/ocr` | 파일을 업로드하고 OCR 결과를 바로 반환 |
| `POST` | `/ocr/jobs` | OCR job 생성 |
| `GET` | `/ocr/jobs/{job_id}` | OCR job 상태/결과 조회 |

## 실행 방법

```bash
cd ai/ocr
pip install -r requirements-ocr.txt
uvicorn ocr_server:app --host 0.0.0.0 --port 8501 --reload
```

PaddleOCR-VL serving까지 같이 띄우는 RunPod용 실행 스크립트는 다음과 같습니다.

```bash
cd ai/ocr
bash runpod_start_paddleocr_wrapper.sh
```

이 스크립트는 내부적으로 다음 흐름을 수행합니다.

1. PaddleOCR-VL serving을 `127.0.0.1:8080`에서 시작
2. 포트 준비 상태 확인
3. OCR wrapper를 `0.0.0.0:8501`에서 시작

## 주요 환경변수

| 이름 | 기본값 | 설명 |
| --- | --- | --- |
| `OCR_BACKEND` | `paddleocr_vl` | `paddleocr_vl` 또는 `qwen` |
| `OCR_MODEL_ID` | `Qwen/Qwen3-VL-4B-Instruct` | Qwen OCR 경로에서 사용할 모델 |
| `PADDLEOCR_VL_URL` | `http://127.0.0.1:8080` | PaddleOCR-VL serving 주소 |
| `PADDLEOCR_VL_TIMEOUT_SEC` | `600` | PaddleOCR-VL 요청 타임아웃 |
| `PADDLEOCR_VL_RETURN_MARKDOWN_IMAGES` | `false` | markdown image 포함 여부 |
| `PADDLEOCR_VL_VISUALIZE` | `false` | 시각화 결과 생성 여부 |
| `LOAD_IN_4BIT` | `true` | Qwen 모델 4bit 로딩 여부 |
| `MAX_NEW_TOKENS` | `2048` | Qwen 생성 최대 토큰 |
| `PRELOAD_OCR_MODEL` | `false` | 시작 시 OCR 모델 선로딩 여부 |
| `OCR_JOB_WORKERS` | `1` | OCR job worker 수 |

## .env 양식

`ai/ocr/.env` 예시입니다.

```dotenv
# OCR backend: paddleocr_vl 또는 qwen
OCR_BACKEND=paddleocr_vl

# PaddleOCR-VL serving
PADDLEOCR_VL_URL=http://127.0.0.1:8080
PADDLEOCR_VL_TIMEOUT_SEC=600
PADDLEOCR_VL_RETURN_MARKDOWN_IMAGES=false
PADDLEOCR_VL_VISUALIZE=false

# Qwen OCR backend를 사용할 때
OCR_MODEL_ID=Qwen/Qwen3-VL-4B-Instruct
LOAD_IN_4BIT=true
TORCH_DTYPE=auto
MAX_NEW_TOKENS=2048
PRELOAD_OCR_MODEL=false

# Job worker
OCR_JOB_WORKERS=1

# Hugging Face token이 필요한 모델을 사용할 때만 입력
HF_TOKEN=
HF_HUB_ENABLE_HF_TRANSFER=1
```

## 요청 예시

```bash
curl -X POST "http://localhost:8501/ocr" \
  -F "file=@sample.pdf"
```

비동기 job 방식:

```bash
curl -X POST "http://localhost:8501/ocr/jobs" \
  -F "file=@sample.pdf"

curl "http://localhost:8501/ocr/jobs/{job_id}"
```

## 백엔드 연동

Django 백엔드에서는 `RUNPOD_OCR_BASE_URL` 값을 통해 이 서버를 호출하는 형태를 권장합니다.

```text
RUNPOD_OCR_BASE_URL=http://localhost:8501
```

## 주의사항

- PaddleOCR-VL backend를 사용할 때는 별도 serving 프로세스가 먼저 준비되어야 합니다.
- Qwen backend는 모델 로딩과 GPU 메모리 사용량이 큽니다.
- 업로드 파일이 비어 있으면 400 오류를 반환합니다.
- `.env`, 모델 캐시, 임시 OCR 결과는 Git에 올리지 않습니다.
