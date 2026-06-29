# AI Services

HPM의 AI 기능을 담당하는 FastAPI 서비스 모음입니다. 백엔드 Django 서버는 회의 녹음, 문서 업로드, 회의록 생성, 챗봇 요청을 받을 때 이 폴더의 AI 서버들을 호출합니다.

## 전체 구조

```text
ai/
├─ ocr/       # 문서/이미지 OCR 추출 서버
├─ stt/       # 회의 음성 STT 서버
├─ parsed/    # 내부 문서 파싱, 청킹, 임베딩, Qdrant 적재 서버
└─ vllm/      # 회의록/안건/준비자료/챗봇 LLM + RAG 서버
```

## 서비스별 역할

| 폴더 | 역할 | 대표 API |
| --- | --- | --- |
| `ocr` | PDF/이미지에서 텍스트 추출 | `/ocr`, `/ocr/jobs` |
| `stt` | 회의 녹음 파일을 텍스트로 변환 | `/stt`, `/transcribe`, `/stt/jobs` |
| `parsed` | 업로드 문서를 파싱하고 벡터 DB에 적재 | `/internal-docs/ingest`, `/internal-docs/ingest/jobs` |
| `vllm` | 회의록 생성, 안건 생성, 준비자료 생성, RAG 챗봇 | `/generate-minutes`, `/generate-agendas`, `/generate-preparation`, `/chat` |

## 백엔드와의 연결

Django 백엔드는 `.env`의 RunPod/AI 서버 URL을 통해 각 서비스를 호출합니다.

| Django 환경변수 | 연결 대상 |
| --- | --- |
| `RUNPOD_CORE_BASE_URL` 또는 `RUNPOD_BASE_URL` | `ai/vllm` LLM/RAG 서버 |
| `RUNPOD_STT_BASE_URL` | `ai/stt` STT 서버 |
| `RUNPOD_OCR_BASE_URL` | `ai/ocr` OCR 서버 |
| `RUNPOD_PARSED_BASE_URL` | `ai/parsed` 문서 ingest 서버 |
| `RAG_SERVER_URL` | 챗봇용 `/chat` 엔드포인트 |

## 공통 환경변수 로딩

각 AI 서비스는 자기 폴더의 `config.py`에서 `.env` 후보를 순서대로 읽습니다.

```text
ai/<service>/.env
ai/.env
/workspace/final_1team/runpod/.env
/workspace/final_1team/.env
/workspace/runpod/.env
/workspace/.env
```

`.env`에는 토큰, 모델 ID, Qdrant 주소, RunPod 환경 설정이 들어갈 수 있으므로 Git에 올리지 않습니다.

## .env 양식

`ai/.env`에 공통값을 두고, 서비스별로 다른 값은 `ai/ocr/.env`, `ai/stt/.env`, `ai/parsed/.env`, `ai/vllm/.env`에서 덮어쓰는 방식이 편합니다.

```dotenv
# Hugging Face
HF_TOKEN=
HF_HUB_ENABLE_HF_TRANSFER=1

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=mineru_pdf_chunks_ko_sroberta
QDRANT_COLLECTION_PROJECT_MODE=true
QDRANT_COLLECTION_PREFIX=hpm_project

# Embedding
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL_ID=jhgan/ko-sroberta-multitask
EMBEDDING_DEVICE=auto
EMBEDDING_BATCH_SIZE=16

# Common runtime
MAX_NEW_TOKENS=2048
HF_HUB_ENABLE_HF_TRANSFER=1
```

## 공통 의존 서비스

- GPU/CUDA 환경: STT, OCR, LLM, 임베딩 모델 실행에 필요할 수 있습니다.
- Hugging Face token: 일부 모델 다운로드나 diarization에 필요합니다.
- Qdrant: 문서/회의록 RAG 검색용 벡터 DB입니다.
- vLLM 또는 llama.cpp: `ai/vllm`의 텍스트 생성 백엔드입니다.
- MinerU: `ai/parsed`에서 PDF 문서 파싱에 사용됩니다.
- PaddleOCR-VL: `ai/ocr`의 기본 OCR 백엔드입니다.

## 로컬 실행 예시

각 서비스는 독립 실행을 전제로 합니다. 포트는 충돌을 피해서 조정할 수 있습니다.

```bash
# OCR
cd ai/ocr
pip install -r requirements-ocr.txt
uvicorn ocr_server:app --host 0.0.0.0 --port 8501 --reload

# STT
cd ai/stt
pip install -r requirements-stt.txt
uvicorn stt_server:app --host 0.0.0.0 --port 8502 --reload

# Parsed
cd ai/parsed
pip install -r requirements.txt
uvicorn parsed_server:app --host 0.0.0.0 --port 8503 --reload

# Core LLM/RAG
cd ai/vllm
pip install -r requirements.txt
uvicorn core_server:app --host 0.0.0.0 --port 8504 --reload
```

실제 RunPod 배포에서는 각 폴더의 실행 스크립트나 컨테이너 설정에 맞춰 포트를 조정합니다.

## 데이터 흐름

1. 사용자가 프론트엔드에서 회의나 문서를 업로드합니다.
2. Django 백엔드가 파일을 저장하고 필요한 AI 서버로 요청합니다.
3. STT는 회의 음성을 텍스트로 변환합니다.
4. OCR/parsed는 문서를 텍스트와 chunk로 분해하고 Qdrant에 적재합니다.
5. vLLM 서버는 회의록, 안건, 준비자료, 챗봇 답변을 생성합니다.
6. 결과는 Django DB와 프론트엔드 화면으로 돌아갑니다.

## 개발 시 주의사항

- 모델 파일, 캐시, `.env`, Qdrant 저장소, 업로드 파일은 Git에 올리지 않습니다.
- GPU 서버에서는 한 번에 여러 무거운 작업이 몰리지 않도록 job API를 우선 사용합니다.
- 긴 작업은 동기 API보다 `/jobs` API로 요청하고 상태를 polling하는 방식이 안정적입니다.
- 백엔드의 URL 설정과 실제 AI 서버 포트가 다르면 기능이 실패합니다.
