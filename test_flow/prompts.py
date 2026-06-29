from __future__ import annotations

import json
from datetime import date
from typing import Any

from schemas import AgendaRequest, ChatRequest, MinutesRequest, PreparationRequest


def minutes_messages(req: MinutesRequest) -> list[dict[str, str]]:
    today = date.today().isoformat()
    prompt = f"""
[역할]
당신은 한국어 회의록과 Jira 작업 항목을 작성하는 AI입니다.
제공된 STT 회의 transcript만 근거로 회의 요약, 회의록 본문, 실행 항목을 추출합니다.
중국어, 일본어, 의미 없는 외국어 표현은 사용하지 말고 모든 내용을 자연스러운 한국어로 작성합니다.

[핵심 규칙]
1. 입력에 없는 사실, 사람, 날짜, 회사명, 문서명은 만들지 않습니다.
2. 정보가 없으면 "미정" 또는 "없음"으로 표시합니다.
3. 실행 항목은 실제로 누군가가 하기로 한 업무만 추출합니다.
4. 발화가 "이름: 내용" 형식이면 그 이름을 우선 담당자로 봅니다.
5. 다른 사람이 특정 인물에게 지시한 경우에는 지시받은 사람을 담당자로 봅니다.
6. 마감일이 명확하면 YYYY-MM-DD로 작성합니다.
7. "이번 주", "다음 주", "금요일까지" 같은 상대 날짜는 오늘 날짜 {today}를 기준으로 계산합니다.
8. 확실한 마감일이 없으면 due_date는 "미정"으로 둡니다.
9. 반드시 JSON 객체 하나만 반환합니다.

[회의 메타데이터]
- 회의 ID: {req.meeting_id or "미정"}
- 프로젝트 ID: {req.project_id or "미정"}
- 회의 제목: {req.title or "미정"}
- 회의 일시: {req.meeting_datetime or "미정"}
- 장소: {req.location or "미정"}

[프로젝트 맥락]
{req.project_context or "없음"}

[출력 JSON 스키마]
{{
  "summary": "회의 핵심 내용을 1~2문장으로 요약",
  "content": "회의 흐름과 결정 사항을 한국어 회의록 본문으로 정리",
  "cotent": "content와 동일한 값. 기존 Django 오타 호환용",
  "todo_list": [
    {{
      "title": "업무 제목",
      "content": "구체적인 업무 내용",
      "owner": "담당자 이름 또는 미정",
      "due_date": "YYYY-MM-DD 또는 미정",
      "priority": "High|Medium|Low|Lowest"
    }}
  ],
  "minutes": {{
    "decisions": ["결정 사항"],
    "issues": ["논의된 이슈"],
    "next_steps": ["다음 단계"]
  }}
}}

[회의 transcript]
{req.text}
""".strip()
    return [
        {
            "role": "system",
            "content": "반드시 유효한 JSON 객체 하나만 반환하세요. 설명, 마크다운, 코드블록은 출력하지 마세요.",
        },
        {"role": "user", "content": prompt},
    ]


def agenda_messages(req: AgendaRequest, *, retry: bool = False) -> list[dict[str, str]]:
    if retry:
        prompt = f"""
회의 제목 "{req.title}"만 근거로 회의 기본 안건 4개를 생성하세요.
반드시 다음 JSON 형식만 반환하세요.
{{"agendas":[{{"title":"안건 제목","content":"논의할 내용"}}]}}
""".strip()
    else:
        prompt = f"""
[역할]
당신은 한국어 회의 안건을 작성하는 AI입니다.

[규칙]
1. 회의 제목, 이전 회의 요약, OCR 참고 텍스트를 근거로 3~5개의 구체적인 안건을 생성합니다.
2. 입력에 없는 사람, 날짜, 회사명, 문서명을 만들지 않습니다.
3. 안건은 회의에서 실제로 논의할 수 있는 행동 중심 문장으로 작성합니다.
4. 반드시 JSON 객체 하나만 반환합니다.

[출력 JSON 스키마]
{{"agendas":[{{"title":"안건 제목","content":"논의할 내용"}}]}}

[입력]
- 회의 제목: {req.title}
- 이전 회의 요약: {req.previous_summary or "없음"}
- OCR 참고 텍스트: {req.ocr_text or "없음"}
""".strip()
    return [
        {
            "role": "system",
            "content": "유효한 한국어 JSON만 반환하세요. 제목이 있으면 agendas를 빈 배열로 반환하지 마세요.",
        },
        {"role": "user", "content": prompt},
    ]


def preparation_messages(req: PreparationRequest, selected_documents: dict[str, Any]) -> list[dict[str, str]]:
    ocr_text = req.ocr_text.strip()
    if len(ocr_text) > 6000:
        ocr_text = f"{ocr_text[:6000]}\n...(OCR 텍스트 일부 생략)"

    prompt = f"""
[역할]
당신은 프로젝트 문서, 이전 회의록, 외부 뉴스, OCR 참고자료를 근거로 회의 준비자료를 작성하는 AI입니다.
회의 참석자가 바로 읽고 회의에 들어갈 수 있도록 핵심 목적, 현재 상태, 규정/제약, 기대 효과를 정리합니다.

[근거 사용 규칙]
1. 제공된 근거만 사용합니다. 사실을 추정하거나 만들어내지 않습니다.
2. 근거가 부족한 항목은 "-"로 작성합니다.
3. 프로젝트 맥락은 배경 판단용으로만 사용하고 그대로 복사하지 않습니다.
4. 이전 회의록은 현재 회의 주제, 안건, 프로젝트 맥락과 직접 관련될 때만 사용합니다.
5. 내부 문서의 정책, 절차, 요구사항, 제약 조건, 미완료 항목을 우선 반영합니다.
6. OCR 참고 텍스트는 방금 업로드된 회의 관련 자료로 보고 안건 보강에 사용합니다.
7. 외부 뉴스는 회의 주제와 연결되는 최신 동향, 시장 상황, 리스크가 있을 때만 반영합니다.
8. 모든 문자열 내부 줄바꿈은 "\\n"으로 이스케이프합니다.
9. 반드시 JSON 객체 하나만 반환합니다.

[입력]
- 회의 제목: {req.title}
- 회의 ID: {req.meeting_id or "미정"}
- 프로젝트 ID: {req.project_id or "미정"}
- 회의 일시: {req.meeting_datetime or "미정"}
- 장소: {req.location or "미정"}
- 프로젝트 맥락: {req.project_context or "없음"}
- OCR 참고 텍스트: {ocr_text or "없음"}
- 참석자: {json.dumps(req.participants, ensure_ascii=False)}
- 안건: {json.dumps(req.agendas, ensure_ascii=False)}
- 이전 회의록: {json.dumps(selected_documents.get("previous_meetings", []), ensure_ascii=False)}
- 내부 문서: {json.dumps(selected_documents.get("internal_documents", []), ensure_ascii=False)}
- 외부 뉴스: {json.dumps(selected_documents.get("external_news", []), ensure_ascii=False)}

[출력 JSON 스키마]
{{
  "preparation_id": null,
  "meeting_id": "{req.meeting_id}",
  "purpose": "이번 회의에서 논의하거나 결정해야 할 목적을 2~3문장으로 정리",
  "project_status": "현재 진행 상태, 미결 사항, 결정 필요 사항을 근거 기반으로 정리",
  "rule": "관련 규정, 절차, 제약사항, 누락 항목을 정리",
  "effect": "회의 이후 기대 결과와 참석자가 준비해야 할 항목을 정리",
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
                "반드시 유효한 JSON 객체 하나만 반환하세요. "
                "최상위 키는 preparation_id, meeting_id, purpose, project_status, rule, effect, sources만 사용하세요. "
                "preparation_id는 입력에 없으면 null입니다. "
                "sources는 title과 document_id를 가진 객체 배열입니다. "
                "근거가 없으면 '-'로 작성하고 사실을 만들지 마세요."
            ),
        },
        {"role": "user", "content": prompt},
    ]


def legacy_preparation_messages(req: PreparationRequest) -> list[dict[str, str]]:
    return preparation_messages(
        req,
        {
            "previous_meetings": [],
            "internal_documents": [],
            "external_news": [],
        },
    )


def chat_messages(
    req: ChatRequest,
    context: str,
    sources: list[str],
) -> list[dict[str, str]]:
    history = "\n".join(f"{item.get('role', 'user')}: {item.get('content', '')}" for item in req.history[-8:])
    source_refs = "\n".join(str(source) for source in sources)
    prompt = f"""
[질문]
{req.question}

[대화 이력]
{history or "(없음)"}

[내부 문서 근거]
{context or "(없음)"}

[사용 가능한 출처]
{source_refs or "(없음)"}

위 근거만 사용해서 한국어로 답변하세요.
""".strip()
    return [
        {
            "role": "system",
            "content": (
                "당신은 한국어 RAG 챗봇입니다. 제공된 프로젝트 내부 자료 근거 안에서만 답변하세요. "
                "확인되지 않은 내용은 추정하지 마세요. 답할 근거가 부족하면 "
                "\"관련 문서에서 확인할 수 있는 내용이 없습니다.\"라고 답하세요. "
                "본문에서 출처가 필요한 문장 끝에는 [1], [2]처럼 번호만 붙이세요. "
                "answer 마지막에만 '출처:' 섹션을 만들고 실제 사용한 출처만 적으세요. "
                "citations에는 실제 답변에 사용한 출처를 [사용 가능한 출처]에서 그대로 복사하세요. "
                "used_context_ids에는 실제로 사용한 [내부 문서 근거] 블록 번호만 숫자로 넣으세요. "
                "confidence는 근거가 충분하면 high, 일부만 확인되면 medium, 확인이 어려우면 low입니다. "
                "반드시 다음 스키마의 유효한 JSON 객체 하나만 반환하세요: "
                "{\"answer\":\"답변\", \"citations\":[\"출처\"], \"used_context_ids\":[1], \"confidence\":\"high|medium|low\"}"
            ),
        },
        {"role": "user", "content": prompt},
    ]


def _recent_chat_history(req: ChatRequest, limit: int = 8) -> str:
    lines = []
    for item in req.history[-limit:]:
        role = str(item.get("role") or "user")
        content = str(item.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def chat_intent_messages(req: ChatRequest) -> list[dict[str, str]]:
    history = _recent_chat_history(req, limit=6)
    prompt = f"""
[사용자 질문]
{req.question}

[최근 대화]
{history or "(없음)"}

[분류 기준]
1. document_question:
   - 사용자가 프로젝트, 회의, 회의록, 업로드 문서, 내부 문서, 이전 회의, Jira 업무, 결정사항, 담당자, 마감일, 계약/정책/요구사항처럼 현재 서비스 안의 자료를 근거로 묻는 경우
   - "문서에 따르면", "회의에서", "프로젝트에서", "업로드한 파일", "이전 회의", "근거", "출처", "결정된 것", "해야 할 일" 같은 표현이 있으면 강하게 document_question
   - 파일명, 보고서명, PDF명, 문서 제목처럼 보이는 고유명과 함께 "내용", "요약", "정리", "찾아줘", "알려줘"가 나오면 document_question
   - 프로젝트 ID가 있는 채팅에서 "해외동향", "2024-1호", "D.gov", "보고서", "PDF"처럼 업로드 문서 제목/호수/자료명으로 보이는 표현은 일반 지식보다 문서 질문으로 우선 판단한다
2. general_chat:
   - 인사, 잡담, 일반 지식, 글쓰기 도움, 문장 다듬기, 번역, 아이디어 제안, 방법 설명, 사용자가 직접 제공한 텍스트 처리
   - 내부 자료를 봐야만 답할 수 있는 질문이 아니면 기본적으로 general_chat으로 분류한다
3. ambiguous:
   - "요약해줘", "정리해줘", "어떻게 됐어?", "내용 알려줘"처럼 현재 문서/프로젝트를 가리키는지 일반 요청인지 불명확한 경우
   - 프로젝트 ID가 있고 검색하면 문서 근거가 나올 수 있지만 확신이 낮은 짧은 주제어 질문

[정책]
- 블랙리스트 방식으로 판단한다. 명확하게 내부 문서/프로젝트/회의 근거가 필요한 질문만 document_question으로 보낸다.
- 일반 대화는 막지 않는다.
- 문서 기반 질문을 general_chat으로 보내서 프로젝트 내부 사실을 추측하게 만들면 안 된다.

[출력 JSON]
{{
  "intent": "document_question|general_chat|ambiguous",
  "confidence": "high|medium|low",
  "reason": "짧은 한국어 이유"
}}
""".strip()
    return [
        {
            "role": "system",
            "content": (
                "너는 챗봇 라우팅을 위한 의도 분류기다. "
                "반드시 유효한 JSON 객체 하나만 반환한다. 설명, 마크다운, 코드블록은 출력하지 않는다."
            ),
        },
        {"role": "user", "content": prompt},
    ]


def general_chat_messages(req: ChatRequest) -> list[dict[str, str]]:
    history = _recent_chat_history(req, limit=8)
    prompt = f"""
[사용자 질문]
{req.question}

[최근 대화]
{history or "(없음)"}

[답변 원칙]
- 자연스럽고 도움이 되는 한국어로 답한다.
- 일반 대화, 글쓰기, 설명, 아이디어 제안, 문장 다듬기, 번역 요청은 일반 ChatGPT처럼 답한다.
- 프로젝트 내부 문서, 회의록, 업로드 파일, Jira 업무, 특정 담당자/마감일/결정사항처럼 내부 근거가 필요한 사실은 추측하지 않는다.
- 내부 자료를 봐야만 알 수 있는 질문이면 "관련 문서에서 확인할 수 있는 내용이 없습니다."라고 답한다.
- 출처가 없으므로 citations는 빈 배열로 둔다.

[출력 JSON]
{{
  "answer": "답변 본문",
  "citations": [],
  "used_context_ids": [],
  "confidence": "high|medium|low",
  "intent": "general_chat"
}}
""".strip()
    return [
        {
            "role": "system",
            "content": (
                "너는 HPM 서비스의 일반 대화 챗봇이다. "
                "내부 문서를 본 것처럼 말하지 말고, 일반 대화는 친절하고 간결하게 답한다. "
                "반드시 유효한 JSON 객체 하나만 반환한다."
            ),
        },
        {"role": "user", "content": prompt},
    ]


def chat_messages(
    req: ChatRequest,
    context: str,
    sources: list[str],
) -> list[dict[str, str]]:
    history = _recent_chat_history(req, limit=8)
    source_refs = "\n".join(str(source) for source in sources)
    prompt = f"""
[사용자 질문]
{req.question}

[최근 대화]
{history or "(없음)"}

[문서 근거]
{context or "(없음)"}

[사용 가능한 출처]
{source_refs or "(없음)"}

[답변 원칙]
- 반드시 [문서 근거]에 있는 내용만 사용한다.
- 문서 근거에서 확인되지 않는 내용은 추측하지 않는다.
- 근거가 부족하면 "관련 문서에서 확인할 수 있는 내용이 없습니다."라고 답한다.
- 사용자가 "업로드한 문서 내용", "이 문서 내용", "문서 요약"처럼 넓게 물었고 [문서 근거]가 제공되어 있으면, 검색된 근거 기준으로 핵심 내용을 요약한다.
- 문서가 여러 개로 보이면 "검색된 문서 기준"이라고 전제하고, 특정 문서명이 필요하다고만 답하며 내용을 비워두지 않는다.
- 답변에 사용한 문장 끝에는 필요한 경우 [1], [2]처럼 근거 번호만 붙인다.
- citations에는 실제 사용한 출처만 [사용 가능한 출처]에서 그대로 복사한다.
- used_context_ids에는 실제 사용한 [문서 근거] 번호만 숫자로 넣는다.

[출력 JSON]
{{
  "answer": "답변 본문",
  "citations": ["출처"],
  "used_context_ids": [1],
  "confidence": "high|medium|low",
  "intent": "document_question"
}}
""".strip()
    return [
        {
            "role": "system",
            "content": (
                "너는 HPM 서비스의 문서 기반 RAG 챗봇이다. "
                "화이트리스트처럼 모든 일반 대화를 거부하지 않는다. 하지만 이 프롬프트에 들어온 요청은 문서 기반 답변 단계다. "
                "따라서 문서 근거 밖의 내부 사실은 절대 만들지 않는다. "
                "반드시 유효한 JSON 객체 하나만 반환한다."
            ),
        },
        {"role": "user", "content": prompt},
    ]
