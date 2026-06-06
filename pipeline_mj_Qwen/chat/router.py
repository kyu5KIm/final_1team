# chat/router.py
from __future__ import annotations
import time
import os
import re
import sys
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter
from pydantic import BaseModel
from rank_bm25 import BM25Okapi

from rag.embeddings import make_embedder
from rag.naver_news import NewsItem, news_context, news_source_references, search_naver_news
from rag.qdrant_store import config_from_env, make_client, scroll_records, search_points
from llm import call_llm

load_dotenv()

router = APIRouter()

# ── 토크나이저 ───────────────────────────────────────────
TOKEN_RE = re.compile(r"[가-힣]{2,}|[A-Za-z][A-Za-z0-9_-]+|\d+(?:\.\d+)?")

def tokenize(text: str) -> list[str]:
    tokens = []
    for token in TOKEN_RE.findall((text or "").lower()):
        tokens.append(token)
        if re.fullmatch(r"[가-힣]{3,}", token):
            tokens.extend(token[i:i+2] for i in range(len(token) - 1))
    return tokens


# ── 서버 시작 시 1회 초기화 ─────────────────────────────
embedder = make_embedder(provider="huggingface", model="jhgan/ko-sroberta-multitask")
qdrant_cfg = config_from_env()
qdrant_client = make_client(qdrant_cfg)
collection = qdrant_cfg.collection

print("[초기화] Qdrant 코퍼스 로딩 중...")
records = list(scroll_records(qdrant_client, collection))
corpus_texts = [r.document for r in records]
bm25 = BM25Okapi([tokenize(r.document) for r in records])
print(f"[초기화] 완료 - {len(records)}개 청크 로드")


# ── 검색 함수들 ──────────────────────────────────────────
def dense_search(query_vector: list[float], limit: int = 20) -> list[dict]:
    points = search_points(qdrant_client, collection, query_vector, limit=limit)
    hits = []
    for rank, point in enumerate(points, 1):
        payload = getattr(point, "payload", {}) or {}
        hits.append({
            "rank": rank,
            "chunk_id": str(payload.get("chunk_id", "")),
            "document": str(payload.get("document", "")),
            "metadata": payload.get("metadata", {}),
            "dense_score": float(getattr(point, "score", 0.0)),
            "source": "dense",
        })
    return hits


def bm25_search(query: str, limit: int = 20) -> list[dict]:
    scores = bm25.get_scores(tokenize(query))
    ranked = sorted(range(len(records)), key=lambda i: float(scores[i]), reverse=True)[:limit]
    hits = []
    for rank, idx in enumerate(ranked, 1):
        r = records[idx]
        hits.append({
            "rank": rank,
            "chunk_id": r.chunk_id,
            "document": r.document,
            "metadata": r.metadata,
            "bm25_score": float(scores[idx]),
            "source": "bm25",
        })
    return hits


def rrf_fuse(dense_hits: list[dict], bm25_hits: list[dict], rrf_k: int = 60, top_k: int = 10) -> list[dict]:
    scores: dict[str, float] = {}
    by_id: dict[str, dict] = {}

    for hit in dense_hits:
        cid = hit["chunk_id"]
        by_id[cid] = hit
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + hit["rank"])

    for hit in bm25_hits:
        cid = hit["chunk_id"]
        by_id.setdefault(cid, hit)
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + hit["rank"])

    fused = []
    for rank, cid in enumerate(sorted(scores, key=scores.get, reverse=True)[:top_k], 1):
        base = by_id[cid]
        fused.append({**base, "rank": rank, "rrf_score": scores[cid], "source": "rrf"})
    return fused


def cohere_rerank(query: str, candidates: list[dict], top_n: int = 3) -> list[dict]:
    try:
        import cohere
        api_key = os.getenv("COHERE_API_KEY")
        co = cohere.ClientV2(api_key=api_key) if hasattr(cohere, "ClientV2") else cohere.Client(api_key)
        docs = [f"source: {c['metadata'].get('source_filename','')}\ntext: {c['document'][:4096]}" for c in candidates]
        response = co.rerank(model="rerank-v3.5", query=query, documents=docs, top_n=min(top_n, len(docs)))
        results = getattr(response, "results", [])
        reranked = []
        for rank, item in enumerate(results, 1):
            idx = int(getattr(item, "index", 0))
            score = float(getattr(item, "relevance_score", 0.0))
            reranked.append({**candidates[idx], "rank": rank, "rerank_score": score, "source": "rerank"})
        return reranked
    except Exception as e:
        print(f"[WARN] Cohere rerank 실패, RRF 결과 사용: {e}")
        return candidates[:top_n]


def build_context(hits: list[dict], max_chars: int = 9000) -> str:
    parts = []
    used = 0
    for hit in hits:
        text = " ".join(hit["document"].split())
        source = hit["metadata"].get("source_filename", "문서")
        page = hit["metadata"].get("page_start", "")
        label = f"{source} p.{page}" if page else source
        block = f"[{hit['rank']}] 출처: {label}\n{text}"
        if used + len(block) > max_chars:
            block = block[:max(0, max_chars - used)]
        if block:
            parts.append(block)
            used += len(block) + 2
        if used >= max_chars:
            break
    return "\n\n".join(parts)


NEWS_KEYWORDS = ("뉴스", "최근", "최신", "오늘", "어제", "요즘", "시사", "속보", "동향", "보도", "기사")

def is_news_query(question: str) -> bool:
    return any(kw in question for kw in NEWS_KEYWORDS)

def is_confident(hits: list[dict], threshold: float = 0.35) -> bool:
    if not hits:
        return False
    return max((h.get("dense_score", 0.0) for h in hits), default=0.0) >= threshold


# ── 요청/응답 형식 ────────────────────────────────────────
class ChatInput(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    used_news: bool
    elapsed: dict


# ── fn5: 챗봇 엔드포인트 ─────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatInput):
    total_start = time.perf_counter()
    query = body.question

    # 1. 임베딩
    t = time.perf_counter()
    query_vector = embedder.embed_query(query)
    embed_sec = time.perf_counter() - t

    # 2. Dense + BM25 검색
    t = time.perf_counter()
    dense_hits = dense_search(query_vector, limit=20)
    bm25_hits = bm25_search(query, limit=20)
    search_sec = time.perf_counter() - t

    # 3. RRF 융합
    rrf_hits = rrf_fuse(dense_hits, bm25_hits, top_k=10)

    # 4. Cohere Rerank
    t = time.perf_counter()
    final_hits = cohere_rerank(query, rrf_hits, top_n=3)
    rerank_sec = time.perf_counter() - t

    # 5. 뉴스 fallback
    news_items: list[NewsItem] = []
    use_news = is_news_query(query) or not is_confident(final_hits)
    if use_news:
        try:
            news_items = search_naver_news(query, display=3)
        except Exception as e:
            print(f"[WARN] 뉴스 검색 실패: {e}")

    # 6. LLM 호출
    if news_items:
        context = news_context(news_items, max_chars=1500)
        sources = news_source_references(news_items)
        prompt = f"""너는 한국어 RAG 챗봇이다. 반드시 한국어로만 답해라. 생각 과정은 출력하지 말고 최종 답변만 출력해라.
아래 뉴스 근거만 사용해서 답해줘. 근거에 없으면 모른다고 해.
[뉴스 근거]
{context}
질문: {query}
답변:"""
    else:
        context = build_context(final_hits)
        sources = [
            f"[{h['rank']}] {h['metadata'].get('source_filename','문서')} p.{h['metadata'].get('page_start','')}"
            for h in final_hits
        ]
        prompt = f"""너는 한국어 RAG 챗봇이다. 반드시 한국어로만 답해라. 생각 과정은 출력하지 말고 최종 답변만 출력해라.
아래 내부문서 근거만 사용해서 답해줘. 근거에 없으면 모른다고 해.
[내부문서 근거]
{context}
질문: {query}
답변:"""

    t = time.perf_counter()
    answer = call_llm(prompt)
    llm_sec = time.perf_counter() - t

    total_sec = time.perf_counter() - total_start

    print(
        f"[시간] 총={total_sec:.2f}초 "
        f"임베딩={embed_sec:.2f}초 "
        f"검색={search_sec:.2f}초 "
        f"rerank={rerank_sec:.2f}초 "
        f"LLM={llm_sec:.2f}초"
    )

    return ChatResponse(
        answer=answer,
        sources=sources,
        used_news=bool(news_items),
        elapsed={
            "total": round(total_sec, 2),
            "embed": round(embed_sec, 2),
            "search": round(search_sec, 2),
            "rerank": round(rerank_sec, 2),
            "llm": round(llm_sec, 2),
        }
)