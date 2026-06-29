# test_flow API Spec

## 공통 응답

동기 생성 API는 기존 `ai/vllm` 형식을 유지합니다.

```json
{
  "result": {},
  "elapsed_sec": 1.23,
  "model": "gpt-4.1-mini"
}
```

비동기 job API는 다음 형태를 사용합니다.

```json
{
  "job_id": "uuid",
  "type": "ocr",
  "status": "queued",
  "step": "queued",
  "result": null,
  "error": null
}
```

## GET /health

서버 설정과 모델 상태를 확인합니다.

## POST /generate-minutes

회의 transcript를 회의록 JSON으로 생성하고 Qdrant에 회의록 chunk를 적재합니다.

요청:

```json
{
  "text": "[00:00] 류재현: 오늘 진행 상황 공유하겠습니다.",
  "meeting_id": "1",
  "project_id": "10",
  "title": "주간 회의",
  "meeting_datetime": "2026-06-27T10:00:00",
  "location": "회의실 A",
  "project_context": "프로젝트 설명"
}
```

응답 `result`:

```json
{
  "summary": "회의 요약",
  "content": "회의록 본문",
  "cotent": "회의록 본문",
  "todo_list": [
    {
      "title": "작업명",
      "content": "작업 내용",
      "owner": "담당자",
      "due_date": "2026-06-30",
      "priority": "High"
    }
  ],
  "minutes": {
    "decisions": [],
    "issues": [],
    "next_steps": []
  },
  "qdrant_ingest": {
    "upserted_points": 3,
    "qdrant_collection": "hpm_project_openai_10"
  }
}
```

`cotent`는 기존 Django 오타 호환을 위해 유지합니다.

## POST /generate-minutes/jobs

`/generate-minutes`와 같은 요청 body를 받고 비동기로 실행합니다.

상태 조회:

```text
GET /generate-minutes/jobs/{job_id}
```

## POST /generate-agendas

요청:

```json
{
  "title": "주간 회의",
  "previous_summary": "지난 회의 요약",
  "ocr_text": "첨부 자료 OCR 텍스트"
}
```

응답 `result`:

```json
{
  "agendas": [
    {
      "title": "진행 상황 점검",
      "content": "지난 주 작업 결과와 미완료 항목을 확인합니다."
    }
  ]
}
```

## POST /generate-preparation

Qdrant에서 이전 회의록/내부 문서를 검색하고, Naver 뉴스 검색 결과를 함께 넣어 회의 준비자료를 생성합니다.

요청:

```json
{
  "title": "주간 회의",
  "preparation_id": null,
  "meeting_id": "1",
  "project_id": "10",
  "meeting_datetime": "2026-06-27T10:00:00",
  "location": "회의실 A",
  "project_context": "프로젝트 맥락",
  "ocr_text": "업로드 자료 OCR 텍스트",
  "participants": [{"name": "류재현", "work": "PM"}],
  "agendas": ["진행 상황 공유"],
  "max_previous_meetings": 5
}
```

응답 `result`:

```json
{
  "preparation_id": null,
  "meeting_id": 1,
  "purpose": "회의 목적",
  "project_status": "현재 상태",
  "rule": "관련 규정 또는 제약",
  "effect": "기대 효과",
  "sources": [
    {
      "title": "참고 문서",
      "document_id": 3
    }
  ],
  "text": "마크다운 형태 준비자료"
}
```

## POST /chat

프로젝트 문서와 회의록 기반 RAG 챗봇입니다.

요청:

```json
{
  "question": "최근 회의에서 결정된 작업은 뭐야?",
  "context": "",
  "history": [],
  "sources": [],
  "project_id": "10",
  "meeting_id": "1",
  "source_scope": "project",
  "source_types": [],
  "max_previous_meetings": 5,
  "min_relevance_score": null
}
```

응답 `result`:

```json
{
  "answer": "답변 본문",
  "citations": ["[1] 회의록 / 주간 회의"],
  "used_context_ids": [1],
  "confidence": "medium",
  "rag_hit_count": 3,
  "rag_collection": "hpm_project_openai_10",
  "rag_used": true
}
```

## STT

동기:

```text
POST /stt
POST /transcribe
```

비동기:

```text
POST /stt/jobs
GET  /stt/jobs/{job_id}
POST /transcribe/jobs
GET  /transcribe/jobs/{job_id}
```

`multipart/form-data`:

| field | type | 설명 |
| --- | --- | --- |
| `file` | file | 음성 파일 |
| `language` | string | 기본 `ko` |
| `diarize` | bool | 기본 `true` |
| `participants` | string | 쉼표 구분 참석자명, 선택 |

## OCR

동기:

```text
POST /ocr
```

비동기:

```text
POST /ocr/jobs
GET  /ocr/jobs/{job_id}
```

`multipart/form-data`:

| field | type | 설명 |
| --- | --- | --- |
| `file` | file | 이미지, PDF, DOCX, TXT |

PDF는 텍스트 추출을 먼저 시도하고, 스캔 PDF는 페이지 이미지를 렌더링해 vision OCR을 호출합니다.

## Internal Docs

문서 ingest:

```text
POST /internal-docs/ingest
POST /internal-docs/ingest/jobs
GET  /internal-docs/ingest/jobs/{job_id}
```

`multipart/form-data`:

| field | type | 설명 |
| --- | --- | --- |
| `files` | file[] | PDF, DOCX, TXT |
| `project_id` | string | 프로젝트 ID |
| `metadata` | JSON string | Django 문서 메타데이터 |
| `collection` | string | 선택, Qdrant collection 강제 지정 |

문서 parser는 로컬 방식입니다. PDF는 `PyMuPDF`로 텍스트를 추출하고, 표는 `pdfplumber`로 추출합니다. 텍스트 추출이 실패한 스캔 PDF는 `gpt-4.1-mini` OCR fallback을 사용합니다. Chunking과 Qdrant payload는 기존 `Hierarchical Parent-Child` 구조를 유지합니다.
