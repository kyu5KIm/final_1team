# Core LLM/RAG Service

회의록 생성, 안건 생성, 회의 준비자료 생성, 프로젝트/회의 챗봇 답변을 담당하는 FastAPI 서버입니다. 텍스트 생성 백엔드는 기본적으로 vLLM의 OpenAI-compatible API를 사용하며, 설정에 따라 llama.cpp 경로도 사용할 수 있습니다.

## 역할

- STT transcript 기반 회의록 생성
- 회의록 생성 job API 제공
- 이전 회의/내부 문서/외부 뉴스 기반 회의 준비자료 생성
- 안건 생성
- Qdrant 기반 RAG 챗봇 답변 생성
- 생성된 회의록을 Qdrant에 ingest하여 이후 검색에 활용

## 주요 파일

| 파일 | 설명 |
| --- | --- |
| `core_server.py` | FastAPI 앱, LLM/RAG API, job 관리 |
| `config.py` | LLM, Qdrant, embedding, vLLM endpoint 설정 |
| `model_runtime.py` | vLLM/llama.cpp/OpenAI-compatible 호출, 임베딩 로딩 |
| `prompts.py` | 회의록/안건/준비자료/챗봇 프롬프트 |
| `retrieval.py` | Qdrant/feature_chat 기반 검색 |
| `meeting_ingest.py` | 회의록 chunk 임베딩 및 Qdrant 적재 |
| `news.py` | 외부 뉴스 검색 |
| `schemas.py` | 요청/응답 모델 |
| `requirements.txt` | API/RAG 공통 의존성 |
| `requirements-vllm.txt` | vLLM 실행 의존성 |
| `requirements_core.txt` | `requirements.txt`를 참조하는 core 설치 파일 |

## API

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/health` | 서버 상태, 모델, Qdrant 설정 확인 |
| `POST` | `/generate-minutes` | 회의록 즉시 생성 |
| `POST` | `/generate-minutes/jobs` | 회의록 생성 job 생성 |
| `GET` | `/generate-minutes/jobs/{job_id}` | 회의록 생성 job 상태/결과 조회 |
| `POST` | `/generate-agendas` | 회의 안건 생성 |
| `POST` | `/generate-preparation` | 회의 준비자료 생성 |
| `POST` | `/chat` | RAG 기반 챗봇 답변 생성 |

## 실행 방법

API 서버만 실행:

```bash
cd ai/vllm
pip install -r requirements.txt
uvicorn core_server:app --host 0.0.0.0 --port 8504 --reload
```

vLLM 서버를 별도로 띄우는 경우 예시:

```bash
pip install -r requirements-vllm.txt
python -m vllm.entrypoints.openai.api_server \
  --model cyankiwi/gemma-4-12B-it-AWQ-INT4 \
  --host 0.0.0.0 \
  --port 8000
```

그 다음 core 서버의 `TEXT_VLLM_BASE_URL`을 vLLM OpenAI-compatible endpoint로 맞춥니다.

```text
TEXT_VLLM_BASE_URL=http://127.0.0.1:8000/v1
```

## 주요 환경변수

| 이름 | 기본값 | 설명 |
| --- | --- | --- |
| `TEXT_BACKEND` | `vllm` | `vllm` 또는 `llama_cpp` |
| `TEXT_MODEL_ID` | backend에 따라 결정 | 생성 모델 ID |
| `TEXT_VLLM_BASE_URL` | `http://127.0.0.1:8000/v1` | vLLM OpenAI-compatible endpoint |
| `TEXT_VLLM_API_KEY` | `EMPTY` | OpenAI-compatible API key |
| `TEXT_VLLM_TIMEOUT_SEC` | `300` | 생성 요청 timeout |
| `TEXT_VLLM_STARTUP_WAIT_SEC` | `900` | vLLM 준비 대기 시간 |
| `TEXT_GGUF_REPO` | `unsloth/gemma-4-12B-it-qat-GGUF` | llama.cpp backend용 repo |
| `TEXT_GGUF_FILENAME` | `*Q4*.gguf` | llama.cpp backend용 GGUF 파일 패턴 |
| `LLAMA_N_CTX` | `32768` | llama.cpp context size |
| `MAX_NEW_TOKENS` | `2048` | 생성 최대 토큰 |
| `PRELOAD_TEXT_MODEL` | `true` | 시작 시 텍스트 모델 선로딩 |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant 주소 |
| `QDRANT_API_KEY` | 없음 | Qdrant API key |
| `QDRANT_COLLECTION` | `mineru_pdf_chunks_ko_sroberta` | 기본 collection |
| `QDRANT_COLLECTION_PROJECT_MODE` | `true` | 프로젝트별 collection 사용 여부 |
| `QDRANT_COLLECTION_PREFIX` | `hpm_project` | 프로젝트별 collection prefix |
| `EMBEDDING_MODEL_ID` | `jhgan/ko-sroberta-multitask` | 임베딩 모델 |
| `CHAT_RAG_TOP_K` | `5` | 챗봇 검색 상위 문서 수 |
| `CHAT_RAG_MAX_CONTEXT_CHARS` | `6000` | 챗봇 context 최대 길이 |
| `COHERE_API_KEY` 또는 `CO_API_KEY` | 없음 | rerank 사용 시 필요 |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 없음 | 뉴스 검색 사용 시 필요 |

## .env 양식

`ai/vllm/.env` 예시입니다.

```dotenv
# Text generation backend: vllm 또는 llama_cpp
TEXT_BACKEND=vllm
TEXT_MODEL_ID=cyankiwi/gemma-4-12B-it-AWQ-INT4
MAX_NEW_TOKENS=2048
PRELOAD_TEXT_MODEL=true

# vLLM OpenAI-compatible endpoint
TEXT_VLLM_BASE_URL=http://127.0.0.1:8000/v1
TEXT_VLLM_API_KEY=EMPTY
TEXT_VLLM_TIMEOUT_SEC=300
TEXT_VLLM_STARTUP_WAIT_SEC=900
TEXT_VLLM_STARTUP_POLL_SEC=5

# llama.cpp backend를 사용할 때
TEXT_GGUF_REPO=unsloth/gemma-4-12B-it-qat-GGUF
TEXT_GGUF_FILENAME=*Q4*.gguf
LLAMA_N_CTX=32768
LLAMA_N_GPU_LAYERS=-1
LLAMA_N_THREADS=8
LLAMA_VERBOSE=false

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=mineru_pdf_chunks_ko_sroberta
QDRANT_COLLECTION_PROJECT_MODE=true
QDRANT_COLLECTION_PREFIX=hpm_project

# Embedding
EMBEDDING_MODEL_ID=jhgan/ko-sroberta-multitask
EMBEDDING_BATCH_SIZE=16
PRELOAD_EMBEDDING_MODEL=true

# RAG
CHAT_RAG_TOP_K=5
CHAT_RAG_MAX_CONTEXT_CHARS=6000
FEATURE_CHAT_DIR=
PIPELINE_TIMEOUT_SEC=2400

# Optional rerank/news providers
COHERE_API_KEY=
CO_API_KEY=
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
NAVER_NEWS_CLIENT_ID=
NAVER_NEWS_CLIENT_SECRET=

# Jobs
MINUTES_JOB_WORKERS=1

# Hugging Face
HF_TOKEN=
HF_HUB_ENABLE_HF_TRANSFER=1
```

## 요청 예시

회의록 생성:

```bash
curl -X POST "http://localhost:8504/generate-minutes" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "회의 transcript...",
    "meeting_id": "1",
    "project_id": "1",
    "title": "주간 회의"
  }'
```

챗봇:

```bash
curl -X POST "http://localhost:8504/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "지난 회의에서 정한 액션 아이템은?",
    "project_id": "1",
    "meeting_id": "1",
    "source_scope": "project"
  }'
```

## 백엔드 연동

Django 백엔드는 회의록, 준비자료, 챗봇 기능에서 이 서버를 호출합니다.

```text
RUNPOD_CORE_BASE_URL=http://localhost:8504
RAG_SERVER_URL=http://localhost:8504/chat
```

## 데이터 흐름

1. Django가 STT 결과 transcript를 `/generate-minutes` 또는 `/generate-minutes/jobs`로 전달합니다.
2. core 서버가 LLM으로 회의록과 todo list를 생성합니다.
3. 생성된 회의록은 `meeting_ingest.py`를 통해 Qdrant에 적재될 수 있습니다.
4. `/chat`은 Qdrant에서 프로젝트/회의 관련 chunk를 찾고, 검색 결과를 context로 답변합니다.
5. `/generate-preparation`은 이전 회의, 내부 문서, 외부 뉴스 등을 조합해 준비자료를 생성합니다.

## 주의사항

- vLLM 서버와 core 서버는 서로 다른 프로세스일 수 있습니다.
- `TEXT_VLLM_BASE_URL`이 잘못되면 LLM 생성 API가 실패합니다.
- Qdrant가 비어 있으면 RAG 답변 품질이 떨어집니다.
- 모델 캐시, `.env`, vector DB 저장소는 Git에 올리지 않습니다.
