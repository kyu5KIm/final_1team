# Parsed/Internal Docs Service

프로젝트 내부 문서를 파싱하고 RAG 검색에 사용할 수 있도록 Qdrant에 적재하는 FastAPI 서버입니다. PDF/DOCX/TXT 업로드를 받아 텍스트 추출, 청킹, 임베딩, 벡터 DB upsert를 수행합니다.

## 역할

- 내부 문서 업로드 처리
- PDF/DOCX/TXT 파일 검증
- MinerU 기반 PDF 파싱
- chunk 생성
- 임베딩 생성
- Qdrant collection upsert
- 프로젝트 단위 collection 분리 지원
- 긴 ingest 작업을 위한 비동기 job API 제공

## 주요 파일

| 파일 | 설명 |
| --- | --- |
| `parsed_server.py` | FastAPI 앱, health check, embedding preload |
| `config.py` | MinerU, Qdrant, embedding, chunk 관련 환경 설정 |
| `document_ingest.py` | 업로드 문서 ingest 파이프라인 |
| `model_runtime.py` | 임베딩 모델 로딩/실행 |
| `internal_docs/routes.py` | `/internal-docs/*` API 라우터 |
| `internal_docs/service.py` | 업로드 문서 저장, 변환, ingest orchestration |
| `internal_docs/pdf_parser.py` | MinerU PDF 파싱 스크립트 |
| `internal_docs/chunker.py` | 파싱 결과 chunk 생성 스크립트 |
| `internal_docs/index_qdrant.py` | Qdrant 색인 관련 스크립트 |
| `requirements.txt` | parsed 서버 의존성 |
| `runpod_start_parsed.sh` | RunPod용 실행 스크립트 |

## API

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/health` | 서버 상태, 임베딩 모델, Qdrant 설정 확인 |
| `POST` | `/internal-docs/ingest` | 문서를 즉시 ingest |
| `POST` | `/internal-docs/ingest/jobs` | ingest job 생성 |
| `GET` | `/internal-docs/ingest/jobs/{job_id}` | ingest job 상태/결과 조회 |

## 지원 파일

```text
.pdf
.docx
.txt
```

DOCX는 PDF로 변환 후 MinerU 파이프라인을 타는 구조입니다. 서버 환경에 LibreOffice가 필요할 수 있습니다.

## 실행 방법

```bash
cd ai/parsed
pip install -r requirements.txt
uvicorn parsed_server:app --host 0.0.0.0 --port 8503 --reload
```

RunPod 스크립트:

```bash
cd ai/parsed
bash runpod_start_parsed.sh
```

현재 스크립트는 `8501` 포트를 사용합니다. OCR 서버와 같이 띄울 경우 포트 충돌을 피해서 조정해야 합니다.

## 주요 환경변수

| 이름 | 기본값 | 설명 |
| --- | --- | --- |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant 주소 |
| `QDRANT_API_KEY` | 없음 | Qdrant API key |
| `QDRANT_COLLECTION` | `mineru_pdf_chunks_ko_sroberta` | 기본 collection |
| `QDRANT_COLLECTION_PROJECT_MODE` | `true` | 프로젝트별 collection 사용 여부 |
| `QDRANT_COLLECTION_PREFIX` | `hpm_project` | 프로젝트별 collection prefix |
| `EMBEDDING_PROVIDER` | `huggingface` | 임베딩 제공자 |
| `EMBEDDING_MODEL_ID` | `jhgan/ko-sroberta-multitask` | 임베딩 모델 |
| `EMBEDDING_DEVICE` | `auto` | 임베딩 실행 device |
| `PRELOAD_EMBEDDING_MODEL` | `true` | 시작 시 임베딩 모델 선로딩 |
| `CHUNK_SIZE` | `650` | chunk token 크기 |
| `CHUNK_OVERLAP` | `100` | chunk overlap |
| `CHUNK_VERSION` | `mineru_v3_650` | chunk 버전 태그 |
| `MINERU_BACKEND` | `hybrid-auto-engine` | MinerU backend |
| `MINERU_METHOD` | `auto` | MinerU parsing method |
| `MINERU_LANG` | `korean` | 문서 언어 |
| `MINERU_TIMEOUT_SEC` | `1800` | MinerU timeout |
| `INTERNAL_DOCS_JOB_WORKERS` | `1` | ingest job worker 수 |

## .env 양식

`ai/parsed/.env` 예시입니다.

```dotenv
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
PRELOAD_EMBEDDING_MODEL=true

# Chunking
CHUNK_SIZE=650
CHUNK_OVERLAP=100
CHUNK_VERSION=mineru_v3_650
CHUNK_ENCODING=cl100k_base
CHUNK_MIN_CHARS=30
CHUNK_MAX_TABLE_TOKENS=500

# MinerU parser
MINERU_BACKEND=hybrid-auto-engine
MINERU_METHOD=auto
MINERU_LANG=korean
MINERU_FORMULA=true
MINERU_TABLE=true
MINERU_TIMEOUT_SEC=1800
PIPELINE_TIMEOUT_SEC=2400

# Optional path override
PARSER_SCRIPT_PATH=
CHUNK_SCRIPT_PATH=
LIBREOFFICE_BIN=

# Job worker
INTERNAL_DOCS_JOB_WORKERS=1

# Hugging Face
HF_TOKEN=
HF_HUB_ENABLE_HF_TRANSFER=1
```

## 요청 예시

```bash
curl -X POST "http://localhost:8503/internal-docs/ingest/jobs" \
  -F "files=@manual.pdf" \
  -F "project_id=1" \
  -F 'metadata={"source":"document_upload"}'
```

상태 조회:

```bash
curl "http://localhost:8503/internal-docs/ingest/jobs/{job_id}"
```

## Qdrant collection 규칙

`QDRANT_COLLECTION_PROJECT_MODE=true`이면 프로젝트 ID를 기준으로 collection 이름을 만듭니다.

```text
hpm_project_<project_id>
```

프로젝트 ID가 없거나 project mode가 꺼져 있으면 `QDRANT_COLLECTION`을 사용합니다.

## 백엔드 연동

Django 문서 업로드 API는 `RUNPOD_PARSED_BASE_URL`을 통해 이 서버의 `/internal-docs/ingest/jobs`를 호출합니다.

```text
RUNPOD_PARSED_BASE_URL=http://localhost:8503
```

## 주의사항

- MinerU와 임베딩 모델은 설치/로딩 시간이 길 수 있습니다.
- PDF 파싱은 GPU와 시스템 패키지 의존성이 큽니다.
- DOCX 처리는 LibreOffice 또는 `LIBREOFFICE_BIN` 설정이 필요할 수 있습니다.
- Qdrant가 꺼져 있으면 ingest는 실패합니다.
- 파싱 결과물, 임베딩 캐시, `.env`는 Git에 올리지 않습니다.
