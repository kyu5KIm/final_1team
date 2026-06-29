# Prompt Summary

실제 프롬프트는 [prompts.py](./prompts.py)에 있습니다. 기존 `ai/vllm` 흐름과 동일하게 `app.py`가 요청 객체를 받아 메시지를 만들고, `model_runtime.generate_json()`이 모델 응답을 JSON으로 파싱합니다.

## 회의록 생성

함수: `minutes_messages(req)`

입력에 포함되는 값:

- `text`: STT transcript
- `meeting_id`, `project_id`
- `title`, `meeting_datetime`, `location`
- `project_context`

강제 JSON key:

```json
{
  "summary": "",
  "content": "",
  "cotent": "",
  "todo_list": [],
  "minutes": {}
}
```

담당자, 마감일, 우선순위는 transcript에 근거가 있을 때만 추출합니다. `cotent`는 기존 Django 오타 호환용으로 유지합니다.

## 안건 생성

함수: `agenda_messages(req, retry=False)`

입력에 포함되는 값:

- `title`
- `previous_summary`
- `ocr_text`

강제 JSON key:

```json
{
  "agendas": [
    {
      "title": "",
      "content": ""
    }
  ]
}
```

제목이 있는데 `agendas`가 비어 있으면 `retry=True` 프롬프트로 한 번 더 요청합니다.

## 준비자료 생성

함수: `preparation_messages(req, selected_documents)`

입력에 포함되는 값:

- 회의 제목, ID, 일시, 장소
- 프로젝트 맥락
- OCR 참고 텍스트
- 참석자와 안건
- Qdrant에서 검색한 이전 회의록
- Qdrant에서 검색한 내부 문서
- 외부 뉴스 검색 결과

강제 JSON key:

```json
{
  "preparation_id": null,
  "meeting_id": "",
  "purpose": "",
  "project_status": "",
  "rule": "",
  "effect": "",
  "sources": []
}
```

프롬프트는 제공된 근거만 사용하도록 제한합니다. 근거가 부족한 항목은 `-`로 반환하게 했고, `app.py`의 `normalize_preparation_response()`가 최종 응답 형태를 보정합니다.

## 챗봇

함수: `chat_messages(req, context, sources)`

입력에 포함되는 값:

- 사용자 질문
- 최근 대화 이력
- Qdrant 검색 context
- 사용 가능한 출처 목록

강제 JSON key:

```json
{
  "answer": "",
  "citations": [],
  "used_context_ids": [],
  "confidence": "high|medium|low"
}
```

`used_context_ids`와 `citations`는 `app.py`의 `normalize_chat_sources()`에서 다시 검증합니다. 근거가 없거나 `confidence=low`이면 출처를 제거하고, 근거 없음 답변으로 처리합니다.

## OCR 프롬프트

위치: [model_runtime.py](./model_runtime.py)

이미지 OCR은 `gpt-4.1-mini` vision 호출 시 다음 의도를 사용합니다.

```text
이미지 안의 모든 읽을 수 있는 텍스트를 한국어 기준으로 정확히 추출하세요.
표는 행 단위로 보존하고, 설명 없이 추출 텍스트만 반환하세요.
```
