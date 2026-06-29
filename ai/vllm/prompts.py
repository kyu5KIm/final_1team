from __future__ import annotations

import json
from datetime import date
from typing import Any

from schemas import AgendaRequest, ChatRequest, MinutesRequest, PreparationRequest


def minutes_messages(req: MinutesRequest) -> list[dict[str, str]]:
    today = date.today().isoformat()
    prompt = f"""
[역할]
너는 회의를 화자별로 분석한 원본 데이터를 분석하여 회의록을 작성하고, 해야 할 일 즉 태스크를 추출하는 Jira AI야.
한눈에 읽어도 누구나 바로 알 수 있을 정도로 완벽한 정리를 해내지. 해당 내용들은 Jira 이슈에도 등록될 예정이야.
그러니 매우 깔끔하고 정확하게 추출해야 해. 중국어 일본어 절대 쓰지마.

[미션]
제공된 대화 텍스트를 분석하여 반드시 아래 JSON 형식으로만 응답해줘.
텍스트에 명시되지 않은 정보는 억지로 지어내지 말고 "미정" 또는 "없음"으로 처리해.
모든 내용은 반드시 100% 한국어(Korean)로만 작성해라. 중국어나 일본어는 절대 사용 금지.

[담당자 추출 규칙 - 매우 중요]
회의록은 "이름: 발언내용" 형식으로 구성되어 있어.
담당자를 결정할 때 아래 두 가지 패턴을 반드시 구분해:

패턴 1 - 본인이 직접 선언하는 경우 → 발언한 화자가 담당자
  예) "김규호: 저는 발표 자료 만들겠습니다" → assignee: 김규호
  예) "류지우: 저는 STT 테스트 해볼게요" → assignee: 류지우
  예) "박수영: 제가 디자인 맡을게요" → assignee: 박수영

패턴 2 - 리더가 다른 사람에게 지시하는 경우 → 지시받은 사람이 담당자
  예) "김지원: 규호님은 체크리스트 부탁드립니다" → assignee: 김규호
  예) "김지원: 민준님이 공고 수정해주세요" → assignee: 김민준

[날짜 기준]
- 오늘 날짜: {today}
- due_date는 회의 텍스트에 명확한 날짜가 있으면 그 날짜를 사용한다.
- "이번 주", "다음 주", "금요일까지"처럼 상대 일정이 있으면 오늘 날짜를 기준으로 YYYY-MM-DD 형식으로 계산한다.
- 마감 일정이 전혀 없으면 "미정"으로 둔다.

[회의 메타데이터]
- 회의 ID: {req.meeting_id or "미정"}
- 회의 제목: {req.title or "미정"}
- 회의 일시: {req.meeting_datetime or "미정"}
- 장소: {req.location or "미정"}

[출력 형식]
{{
  "summary": "회의 핵심 내용을 1~2문장으로 요약",
  "cotent": "회의록내용을 정리해줘. 누가 봐도 한눈에 이해할 정도로 써야해. 너무 간략하게 쓰면 이해하기 어렵다. 줄바꿈은 \\n으로 표현하고 JSON 문자열 안에서 실제 줄바꿈 금지. 형식: 큰 주제\\n1. 세부 내용\\n  - 더 구체적인 내용.",
  "todo_list": [
    {{
      "title": "해당 담당자가 해야 할 업무 내용(태스크 명)",
      "content": "해당 담당자가 해야 할 구체적인 업무 내용",
      "owner": "담당자 이름",
      "due_date": "마감 일정(YYYY-MM-DD 또는 미정)",
      "priority": "High|Medium|Low|Lowest"
    }}
  ]
}}

[프로젝트 누적 맥락]
{req.project_context or "없음"}

[회의 대본]
{req.text}
""".strip()
    return [
        {"role": "system", "content": "You are a helpful assistant. Always respond in valid JSON format only, with no extra text."},
        {"role": "user", "content": prompt},
    ]


def agenda_messages(req: AgendaRequest, *, retry: bool = False) -> list[dict[str, str]]:
    if retry:
        prompt = f'회의 제목 "{req.title}"만 근거로 회의 기초 안건 4개를 생성해줘. 출력은 {{"agendas":[{{"title":"...","content":"..."}}]}} JSON만 반환해.'
    else:
        prompt = f"""
회의 기초 안건을 생성해줘.

규칙:
- 회의 제목이 있으면 3~5개의 안건을 생성한다.
- 이전 회의 요약과 OCR 참고 텍스트가 있으면 반영한다.
- 입력에 없는 사람, 날짜, 회사명, 문서명은 지어내지 않는다.
- 반드시 한국어 JSON만 반환한다.

출력 형식:
{{"agendas": [{{"title": "안건명", "content": "논의할 내용"}}]}}

회의 제목: {req.title}
이전 회의 요약: {req.previous_summary}
OCR 참고 텍스트: {req.ocr_text}
""".strip()
    return [
        {"role": "system", "content": "Return valid Korean JSON only. Do not return an empty agendas array when a title is provided."},
        {"role": "user", "content": prompt},
    ]


def preparation_messages(req: PreparationRequest, selected_documents: dict[str, Any]) -> list[dict[str, str]]:
    ocr_text = req.ocr_text.strip()
    if len(ocr_text) > 6000:
        ocr_text = f"{ocr_text[:6000]}\n...(OCR 텍스트 일부 생략)"
    prompt = f"""
당신은 프로젝트 문서 분석 및 회의 준비 자료 작성 전문가입니다.
제공된 근거를 바탕으로 회의 참석자가 바로 읽고 회의에 들어갈 수 있는 '회의 준비 자료'를 작성하십시오.

[핵심 규칙]
1. 제공된 자료([프로젝트 히스토리], [내부 문서], [외부 뉴스])에 명시된 내용만 사용합니다. 사실을 추정하거나 지어내지 마십시오.
2. 문서에서 확인되지 않거나 누락된 정보는 반드시 "-"로 표기합니다.
3. 주어진 [회의 주제], [프로젝트 누적 맥락], [OCR 참고 텍스트], [안건]과 직접 관련 없는 정보는 제외합니다.
4. 프로젝트 누적 맥락은 배경 판단용으로만 사용합니다. 입력 문장을 그대로 복사하지 말고, 이번 회의 준비에 필요한 현재 상태, 결정사항, 미완료 쟁점만 재구성합니다.
5. 이전회의록은 회의 주제, 안건, 프로젝트 맥락, OCR 참고 텍스트와 직접 관련된 경우에만 사용합니다. 관련 이전회의록이 없으면 "관련 이전 회의록 확인 불가"로 작성합니다.
6. 내부 문서는 정책, 절차, 요구사항, 제약조건, 기준을 확인하는 데 우선 사용합니다.
7. OCR 참고 텍스트는 사용자가 방금 업로드한 회의 관련 문서 내용으로 보고, 회의 목적과 안건 보강에 사용합니다.
8. 외부 뉴스는 항상 참고하여 회의 주제와 연결되는 최신 외부 동향, 시장 상황, 리스크를 반영합니다.
9. 이전회의록과 내부 문서의 내용이 충돌하면 어느 쪽이 맞는지 단정하지 말고 "-"로 표시합니다.
10. 모든 핵심 문장 끝에는 가능한 경우 [출처명] 형태로 출처를 붙입니다. 출처가 없으면 붙이지 않습니다.
11. 출력은 반드시 유효한 JSON 객체 하나만 반환합니다.
12. JSON 밖에는 코드블록, 설명 문장, 마크다운을 절대 출력하지 마십시오.
13. 최상위 key는 반드시 "preparation_id", "meeting_id", "purpose", "project_status", "rule", "effect", "sources" 일곱 개만 사용합니다.

[입력 데이터]
- 회의 주제: {req.title}
- 프로젝트 누적 맥락: {req.project_context or "없음"}
- OCR 참고 텍스트: {ocr_text or "없음"}
- 참석자: {json.dumps(req.participants, ensure_ascii=False)}
- 안건: {json.dumps(req.agendas, ensure_ascii=False)}
- 프로젝트 히스토리: {json.dumps(selected_documents.get("previous_meetings", []), ensure_ascii=False)}
- 내부 문서: {json.dumps(selected_documents.get("internal_documents", []), ensure_ascii=False)}
- 외부 뉴스: {json.dumps(selected_documents.get("external_news", []), ensure_ascii=False)}

[출력 형식]
반드시 아래 JSON 스키마만 반환하십시오.

{{
  "preparation_id": null,
  "meeting_id": "{req.meeting_id}",
  "purpose": "이번 회의에서 확정하거나 점검해야 할 목적을 2~3개로 정리",
  "project_status": "입력 맥락을 그대로 복사하지 말고 이번 회의 준비에 필요한 현재 진행 상태, 지난 결정사항, 미완료 쟁점을 재구성. 근거가 부족하면 -",
  "rule": "관련 내부문서 근거, 정책, 절차, 요구사항, 제약조건, 누락 항목을 정리",
  "effect": "회의 종료 후 기대 결과와 참석자가 회의 전 준비해야 할 항목을 정리",
  "sources": [
    {{
      "title": "참고 문서명",
      "document_id": 0
    }}
  ]
}}
""".strip()
    return [
        {
            "role": "system",
            "content": "Return exactly one valid JSON object and nothing else. "
            "Do not use markdown outside JSON. "
            "The JSON object must have exactly these top-level keys: "
            "preparation_id, meeting_id, purpose, project_status, rule, effect, sources. "
            "preparation_id must be null unless it is provided by the input. "
            "sources must be an array of objects with title and document_id; document_id may be null when the source has no backend document id. "
            "Use only the provided evidence. If evidence is missing, write '-'. "
            "Separate previous meeting context from internal document requirements. "
            "Prefer concrete decisions, todos, owners, dates, policy clauses, constraints, and open questions. "
            "Do not invent facts.",
        },
        {"role": "user", "content": prompt},
    ]


def preparation_messages(req: PreparationRequest, selected_documents: dict[str, Any]) -> list[dict[str, str]]:
    ocr_text = req.ocr_text.strip()
    if len(ocr_text) > 6000:
        ocr_text = f"{ocr_text[:6000]}\n...(OCR 텍스트 일부 생략)"

    prompt = f"""
당신은 회의 준비자료 작성 전문가입니다.
제공된 근거만 사용해서 회의 참석자가 바로 읽고 회의에 들어갈 수 있는 준비자료를 작성하세요.

[작성 규칙]
1. 입력 데이터에 없는 사실을 추정하지 마세요.
2. 근거가 부족한 항목은 "-"라고 쓰세요.
3. OCR 참고 텍스트는 사용자가 방금 올린 회의 관련 문서로 보고 회의 목적과 안건 보강에 사용하세요.
4. 이전 회의록은 현재 회의 주제와 직접 관련될 때만 사용하세요.
5. 내부 문서에서는 정책, 절차, 요구사항, 제약조건, 누락 항목을 우선 반영하세요.
6. JSON 밖에는 설명, 코드블록, 마크다운을 절대 출력하지 마세요.
7. 문자열 안의 줄바꿈은 실제 줄바꿈이 아니라 "\\n"으로 이스케이프하세요.
8. 최상위 key는 반드시 preparation_id, meeting_id, purpose, project_status, rule, effect, sources 만 사용하세요.

[입력 데이터]
- 회의 주제: {req.title}
- 프로젝트 맥락: {req.project_context or "없음"}
- OCR 참고 텍스트: {ocr_text or "없음"}
- 참석자: {json.dumps(req.participants, ensure_ascii=False)}
- 안건: {json.dumps(req.agendas, ensure_ascii=False)}
- 이전 회의록: {json.dumps(selected_documents.get("previous_meetings", []), ensure_ascii=False)}
- 내부 문서: {json.dumps(selected_documents.get("internal_documents", []), ensure_ascii=False)}
- 외부 뉴스: {json.dumps(selected_documents.get("external_news", []), ensure_ascii=False)}

[출력 형식]
아래 스키마와 같은 유효한 JSON 객체 하나만 반환하세요.

{{
  "preparation_id": null,
  "meeting_id": "{req.meeting_id}",
  "purpose": "이번 회의에서 논의하거나 결정해야 할 목적을 2~3문장으로 정리",
  "project_status": "현재 진행 상태, 미결 사항, 결정 필요 사항을 근거 기반으로 정리",
  "rule": "관련 규정, 절차, 제약사항, 누락 항목을 정리",
  "effect": "회의 종료 후 기대 결과와 참석자가 준비해야 할 항목을 정리",
  "sources": [
    {{
      "title": "참고 문서명",
      "document_id": 0
    }}
  ]
}}
""".strip()

    return [
        {
            "role": "system",
            "content": (
                "Return exactly one valid JSON object and nothing else. "
                "Do not use markdown outside JSON. "
                "The JSON object must have exactly these top-level keys: "
                "preparation_id, meeting_id, purpose, project_status, rule, effect, sources. "
                "preparation_id must be null unless it is provided by the input. "
                "sources must be an array of objects with title and document_id; document_id may be null when the source has no backend document id. "
                "Use only the provided evidence. If evidence is missing, write '-'. "
                "Escape newlines inside string values as \\n. "
                "Do not invent facts."
            ),
        },
        {"role": "user", "content": prompt},
    ]


def legacy_preparation_messages(req: PreparationRequest) -> list[dict[str, str]]:
    selected = {
        "previous_meetings": [],
        "internal_documents": [],
        "external_news": [],
    }
    return preparation_messages(req, selected)


# def chat_messages(req: ChatRequest, context: str, sources: list[str]) -> list[dict[str, str]]:
#     history = "\n".join(f"{item.get('role', 'user')}: {item.get('content', '')}" for item in req.history[-8:])
#     prompt = f"""
# 질문에 답해줘.

# 규칙:
# - 반드시 [Qdrant 컨텍스트]에 있는 내용만 사용한다.
# - 컨텍스트에 없으면 "제공된 자료에서 확인할 수 없습니다."라고 답한다.
# - citations에는 실제로 사용한 출처만 sources에서 그대로 복사한다.
# - JSON만 반환한다.

# 출력 형식:
# {{"answer": "답변", "citations": ["출처"]}}

# [대화 이력]
# {history}

# [사용 가능한 출처]
# {json.dumps(sources, ensure_ascii=False)}

# [Qdrant 컨텍스트]
# {context}

# [질문]
# {req.question}
# """.strip()
#     return [
#         {"role": "system", "content": "You answer Korean meeting questions using only the provided Qdrant context. Return valid JSON only."},
#         {"role": "user", "content": prompt},
#     ]


def chat_messages(
    req: ChatRequest,
    context: str,
    sources: list[str],
) -> list[dict[str, str]]:
    history = "\n".join(f"{item.get('role', 'user')}: {item.get('content', '')}" for item in req.history[-8:])
    source_refs = "\n".join(str(source) for source in sources)
    prompt = f"""
질문:
{req.question}

[대화 이력]
{history or "(없음)"}

[내부문서 근거]
{context or "(없음)"}

[사용 가능한 출처]
{source_refs or "(없음)"}

위 근거만 사용해서 한국어로 답변해줘.
""".strip()
    return [
        {
            "role": "system",
            "content": """
너는 한국어 RAG 챗봇이다.
제공된 프로젝트 내부자료 근거 안에서만 답한다.

확인되지 않은 내용은 추측하지 말고, 모르면 모른다고 답한다.
본문에는 URL을 직접 쓰지 않는다.
본문에서 출처가 필요한 문장 끝에는 [1], [2]처럼 번호만 붙인다.
답변 맨 아래에만 '출처:' 섹션을 만들고 전체 출처 목록을 표시한다.
근거가 부족해서 답할 수 없으면 "제공된 자료에서 확인할 수 없습니다."라고 답하고, 출처 섹션을 만들지 않는다.
citations에는 실제 답변에 사용한 출처만 [사용 가능한 출처]에서 그대로 복사한다.
used_context_ids에는 실제로 사용한 [내부문서 근거] 블록 번호만 숫자로 넣는다.
confidence는 근거가 충분하면 "high", 일부만 확인되면 "medium", 확인 불가이면 "low"로 둔다.

답변 작성 규칙:
- 내부자료 근거를 기준으로 답한다.
- 조항, 수치, 조건, 절차가 있으면 빠뜨리지 않는다.
- 출처 섹션에는 '[번호] 문서명 p.페이지' 형식으로 표시한다.
- 출처가 없으면 [번호]를 명시하지 않는다.

반드시 유효한 JSON 하나만 반환한다.
출력 형식은 {"answer": "답변 본문과 필요한 경우 출처 섹션", "citations": ["실제로 사용한 출처"], "used_context_ids": [1], "confidence": "high|medium|low"} 이다.
""".strip(),
        },
        {"role": "user", "content": prompt},
    ]


def chat_messages(
    req: ChatRequest,
    context: str,
    sources: list[str],
) -> list[dict[str, str]]:
    history = "\n".join(f"{item.get('role', 'user')}: {item.get('content', '')}" for item in req.history[-8:])
    source_refs = "\n".join(str(source) for source in sources)
    prompt = f"""
질문:
{req.question}

[대화 이력]
{history or "(없음)"}

[내부문서 근거]
{context or "(없음)"}

[사용 가능한 출처]
{source_refs or "(없음)"}

위 근거만 사용해서 한국어로 답변하세요.
""".strip()
    return [
        {
            "role": "system",
            "content": """
너는 한국어 RAG 챗봇이다.
제공된 프로젝트 내부자료 근거 안에서만 답한다.

확인되지 않은 내용은 추정하지 않는다.
근거가 부족해서 답할 수 없으면 "관련 문서에서 확인할 수 있는 내용이 없습니다."라고 답하고, 출처 섹션을 만들지 않는다.
파일명이나 문서 존재 여부를 묻는 질문은 [내부문서 근거]의 "출처:" 줄과 [사용 가능한 출처]의 파일명을 근거로 답한다.
본문에는 URL을 직접 적지 않는다.
본문에서 출처가 필요한 문장 끝에는 [1], [2]처럼 번호만 붙인다.
답변 마지막에만 "출처:" 섹션을 만들고 실제 사용한 출처 목록을 표시한다.
citations에는 실제 답변에 사용한 출처만 [사용 가능한 출처]에서 그대로 복사한다.
used_context_ids에는 실제로 사용한 [내부문서 근거] 블록 번호만 숫자로 넣는다.
confidence는 근거가 충분하면 "high", 일부만 확인되면 "medium", 확인 불가이면 "low"로 둔다.

반드시 유효한 JSON 하나만 반환한다.
출력 형식은 {"answer": "답변 본문과 필요한 경우 출처 섹션", "citations": ["실제로 사용한 출처"], "used_context_ids": [1], "confidence": "high|medium|low"} 이다.
""".strip(),
        },
        {"role": "user", "content": prompt},
    ]
