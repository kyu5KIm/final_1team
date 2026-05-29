#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from rank_bm25 import BM25Okapi

from embedding_utils import DEFAULT_HF_EMBEDDING_MODEL, make_embedder

try:
    import cohere
except Exception:
    cohere = None


TOKEN_RE = re.compile(r"[가-힣]{2,}|[A-Za-z][A-Za-z0-9_-]+|\d+(?:\.\d+)?")


@dataclass
class CorpusRecord:
    chunk_id: str
    document: str
    metadata: dict[str, Any]


@dataclass
class SearchHit:
    rank: int
    chunk_id: str
    document: str
    metadata: dict[str, Any]
    source: str
    score: float
    dense_rank: int | None = None
    dense_score: float | None = None
    bm25_rank: int | None = None
    bm25_score: float | None = None
    rrf_rank: int | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None
    distance: float | None = None


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def parse_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hybrid RAG query over a ChromaDB collection.")
    parser.add_argument("--chroma-dir", type=Path, default=Path("chroma_db"))
    parser.add_argument("--collection", type=str, default="mineru_pdf_chunks_ko_sroberta")
    parser.add_argument("--embedding-provider", choices=["huggingface", "openai"], default="huggingface")
    parser.add_argument("--embedding-model", "--model", dest="embedding_model", default=DEFAULT_HF_EMBEDDING_MODEL)
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--answer-model", default=os.getenv("RAG_ANSWER_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--openai-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--hf-token-env", default="HF_TOKEN")
    parser.add_argument("--cohere-model", default=os.getenv("COHERE_RERANK_MODEL", "rerank-v3.5"))
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--dense-k", type=int, default=50)
    parser.add_argument("--dense-fetch-k", type=int, default=200)
    parser.add_argument("--bm25-k", type=int, default=50)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--rrf-top-k", type=int, default=50)
    parser.add_argument("--rerank-top-n", type=int, default=10)
    parser.add_argument("--max-tokens-per-doc", type=int, default=4096)
    parser.add_argument("--where-doc-id", default=None)
    parser.add_argument("--where-source-contains", default=None)
    parser.add_argument("--exclude-chunk-types", default="image_caption,chart_caption")
    parser.add_argument("--max-context-chars", type=int, default=9000)
    parser.add_argument("--preview-chars", type=int, default=700)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--skip-rerank", action="store_true")
    parser.add_argument("--no-answer", action="store_true")
    parser.add_argument("--hide-context", action="store_true")
    return parser.parse_args()


def make_openai_client(env_name: str) -> OpenAI:
    api_key = os.getenv(env_name)
    if not api_key:
        raise RuntimeError(f"Missing {env_name}. Put it in .env or export it.")
    return OpenAI(api_key=api_key)


def get_cohere_client() -> Any:
    api_key = os.getenv("COHERE_API_KEY") or os.getenv("CO_API_KEY")
    if not api_key:
        raise RuntimeError("Missing COHERE_API_KEY. Add it to .env or run with --skip-rerank.")
    if cohere is None:
        raise RuntimeError("cohere package is not installed. Run: python -m pip install cohere")
    if hasattr(cohere, "ClientV2"):
        return cohere.ClientV2(api_key=api_key)
    return cohere.Client(api_key)


def normalize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    out: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            stripped = value.strip()
            if (stripped.startswith("[") and stripped.endswith("]")) or (stripped.startswith("{") and stripped.endswith("}")):
                try:
                    out[key] = json.loads(stripped)
                    continue
                except Exception:
                    pass
        out[key] = value
    return out


def source_filename(meta: dict[str, Any]) -> str:
    name = str(meta.get("source_filename") or meta.get("source") or meta.get("file_name") or "unknown.pdf")
    return Path(name).name


def page_label(meta: dict[str, Any]) -> str:
    start = meta.get("page_start") or meta.get("page_no") or meta.get("page")
    end = meta.get("page_end") or start
    if start is None:
        return ""
    if end and end != start:
        return f"{start}-{end}"
    return str(start)


def source_label(meta: dict[str, Any], include_page: bool = True) -> str:
    filename = source_filename(meta)
    if include_page and page_label(meta):
        return f"{filename} p.{page_label(meta)}"
    return filename


def source_matches(meta: dict[str, Any], source_contains: str | None) -> bool:
    return not source_contains or source_contains.lower() in source_filename(meta).lower()


def chunk_type_allowed(meta: dict[str, Any], excluded_types: set[str]) -> bool:
    return str(meta.get("chunk_type") or meta.get("block_type") or "") not in excluded_types


def normalize_context_text(text: str) -> str:
    return " ".join((text or "").split())


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_RE.findall((text or "").lower()):
        tokens.append(token)
        if re.fullmatch(r"[가-힣]{3,}", token):
            tokens.extend(token[i : i + 2] for i in range(len(token) - 1))
            if len(token) >= 5:
                tokens.extend(token[i : i + 3] for i in range(len(token) - 2))
    return tokens


def retrieval_text(record: CorpusRecord) -> str:
    meta = record.metadata
    parts = [source_filename(meta), page_label(meta), str(meta.get("chunk_type") or "")]
    heading = meta.get("heading") or meta.get("article_title")
    if heading:
        parts.append(str(heading))
    return " | ".join(part for part in parts if part) + "\n" + record.document


def load_corpus(collection: Any, batch_size: int = 1000) -> list[CorpusRecord]:
    total = collection.count()
    records: list[CorpusRecord] = []
    for offset in range(0, total, batch_size):
        batch = collection.get(limit=batch_size, offset=offset, include=["documents", "metadatas"])
        ids = batch.get("ids") or []
        docs = batch.get("documents") or []
        metas = batch.get("metadatas") or []
        for i, chunk_id in enumerate(ids):
            records.append(
                CorpusRecord(
                    chunk_id=str(chunk_id),
                    document=str(docs[i] if i < len(docs) and docs[i] is not None else ""),
                    metadata=normalize_metadata(metas[i] if i < len(metas) else {}),
                )
            )
    if not records:
        raise RuntimeError("No documents found in Chroma collection. Run 03_0_index_chroma_openai.py first.")
    return records


def distance_to_similarity(distance: float | None) -> float:
    if distance is None:
        return 0.0
    if 0 <= distance <= 2.5:
        return max(0.0, min(1.0, 1.0 - distance / 2.0))
    return 1.0 / (1.0 + distance)


def dense_search(collection: Any, query_embedding: list[float], args: argparse.Namespace, excluded_types: set[str]) -> list[SearchHit]:
    where = {"doc_id": args.where_doc_id} if args.where_doc_id else None
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=max(args.dense_fetch_k, args.dense_k),
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    ids = result.get("ids", [[]])[0]
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    hits: list[SearchHit] = []
    for chunk_id, doc, meta, distance in zip(ids, docs, metas, distances):
        clean_meta = normalize_metadata(meta)
        if not source_matches(clean_meta, args.where_source_contains):
            continue
        if not chunk_type_allowed(clean_meta, excluded_types):
            continue
        rank = len(hits) + 1
        dist = float(distance) if distance is not None else None
        score = distance_to_similarity(dist)
        hits.append(SearchHit(rank, str(chunk_id), str(doc or ""), clean_meta, "dense", score, dense_rank=rank, dense_score=score, distance=dist))
        if len(hits) >= args.dense_k:
            break
    return hits


def bm25_search(records: list[CorpusRecord], bm25: BM25Okapi, query: str, args: argparse.Namespace, excluded_types: set[str]) -> list[SearchHit]:
    scores = bm25.get_scores(tokenize(query))
    candidate_indices = [
        i
        for i, record in enumerate(records)
        if source_matches(record.metadata, args.where_source_contains)
        and chunk_type_allowed(record.metadata, excluded_types)
        and (not args.where_doc_id or record.metadata.get("doc_id") == args.where_doc_id)
    ]
    candidate_indices.sort(key=lambda i: float(scores[i]), reverse=True)
    hits: list[SearchHit] = []
    for i in candidate_indices[: args.bm25_k]:
        record = records[i]
        rank = len(hits) + 1
        score = float(scores[i])
        hits.append(SearchHit(rank, record.chunk_id, record.document, record.metadata, "bm25", score, bm25_rank=rank, bm25_score=score))
    return hits


def rrf_fuse(dense_hits: list[SearchHit], bm25_hits: list[SearchHit], rrf_k: int, top_k: int) -> list[SearchHit]:
    by_id: dict[str, SearchHit] = {}
    scores: dict[str, float] = {}
    dense_by_id = {hit.chunk_id: hit for hit in dense_hits}
    bm25_by_id = {hit.chunk_id: hit for hit in bm25_hits}
    for hit in dense_hits:
        by_id[hit.chunk_id] = hit
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (rrf_k + hit.rank)
    for hit in bm25_hits:
        by_id.setdefault(hit.chunk_id, hit)
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (rrf_k + hit.rank)

    fused: list[SearchHit] = []
    for chunk_id in sorted(scores, key=scores.get, reverse=True)[:top_k]:
        base = by_id[chunk_id]
        dense = dense_by_id.get(chunk_id)
        bm25 = bm25_by_id.get(chunk_id)
        rank = len(fused) + 1
        fused.append(
            SearchHit(
                rank=rank,
                chunk_id=base.chunk_id,
                document=base.document,
                metadata=base.metadata,
                source="rrf",
                score=float(scores[chunk_id]),
                dense_rank=dense.dense_rank if dense else None,
                dense_score=dense.dense_score if dense else None,
                bm25_rank=bm25.bm25_rank if bm25 else None,
                bm25_score=bm25.bm25_score if bm25 else None,
                rrf_rank=rank,
                rrf_score=float(scores[chunk_id]),
                distance=dense.distance if dense else None,
            )
        )
    return fused


def format_for_cohere(hit: SearchHit, max_chars: int = 12000) -> str:
    return f"source: {source_label(hit.metadata)}\ntext: {normalize_context_text(hit.document)[:max_chars]}"


def cohere_rerank(co_client: Any, query: str, candidates: list[SearchHit], args: argparse.Namespace) -> list[SearchHit]:
    if not candidates:
        return []
    docs = [format_for_cohere(hit) for hit in candidates]
    top_n = min(args.rerank_top_n, len(docs))
    try:
        response = co_client.rerank(
            model=args.cohere_model,
            query=query,
            documents=docs,
            top_n=top_n,
            max_tokens_per_doc=args.max_tokens_per_doc,
        )
    except TypeError:
        response = co_client.rerank(model=args.cohere_model, query=query, documents=docs, top_n=top_n)

    results = getattr(response, "results", None)
    if results is None and isinstance(response, dict):
        results = response.get("results", [])
    reranked: list[SearchHit] = []
    for item in results or []:
        idx = getattr(item, "index", None)
        score = getattr(item, "relevance_score", None)
        if idx is None and isinstance(item, dict):
            idx = item.get("index")
            score = item.get("relevance_score")
        if idx is None:
            continue
        base = candidates[int(idx)]
        rank = len(reranked) + 1
        reranked.append(
            SearchHit(
                rank=rank,
                chunk_id=base.chunk_id,
                document=base.document,
                metadata=base.metadata,
                source="rerank",
                score=float(score or 0.0),
                dense_rank=base.dense_rank,
                dense_score=base.dense_score,
                bm25_rank=base.bm25_rank,
                bm25_score=base.bm25_score,
                rrf_rank=base.rrf_rank,
                rrf_score=base.rrf_score,
                rerank_score=float(score or 0.0),
                distance=base.distance,
            )
        )
    return reranked


def fmt_score(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def build_context(hits: list[SearchHit], max_chars: int) -> str:
    parts: list[str] = []
    used = 0
    for hit in hits:
        text = normalize_context_text(hit.document)
        if not text:
            continue
        block = f"[{hit.rank}] 출처: {source_label(hit.metadata)}\n{text}"
        if used + len(block) > max_chars:
            block = block[: max(0, max_chars - used)].rstrip()
        if block:
            parts.append(block)
            used += len(block) + 2
        if used >= max_chars:
            break
    return "\n\n".join(parts)


def unique_source_filenames(hits: list[SearchHit]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for hit in hits:
        name = source_filename(hit.metadata)
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def answer_source_references(hits: list[SearchHit]) -> list[str]:
    references: list[str] = []
    seen: set[tuple[str, str]] = set()
    for hit in hits:
        filename = source_filename(hit.metadata)
        page = page_label(hit.metadata)
        key = (filename, page)
        if key in seen:
            continue
        seen.add(key)
        page_text = f"{page}page" if page else "page unknown"
        references.append(f"[{len(references) + 1}] {filename} {page_text}")
    return references


def generate_answer(client: OpenAI, model: str, query: str, hits: list[SearchHit], max_context_chars: int, temperature: float) -> str:
    context = build_context(hits, max_context_chars)
    if not context:
        return "검색된 근거가 없어 답변할 수 없습니다."
    source_refs = "\n".join(answer_source_references(hits))
    system_prompt = (
        "너는 한국어 RAG 챗봇이다. 제공된 근거 안에서만 답변한다. "
        "근거에서 확인되지 않는 내용은 모른다고 말한다. "
        "답변 끝에 '출처:'를 쓰고, 각 출처를 '[1] 파일명.pdf 10page \n' 형식으로 적는다. "
        "출처에는 파일명과 페이지 외에 경로, 청크 번호, 점수는 쓰지 않는다."
        "근거가 확인되지 않는 내용의 출처는 명시하지 않는다."
    )
    user_prompt = (
        f"질문:\n{query}\n\n"
        f"검색 근거:\n{context}\n\n"
        f"사용 가능한 출처 표기:\n{source_refs}\n\n"
        "위 근거만 사용해서 한국어로 답변해줘."
    )
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
    )
    return response.choices[0].message.content or ""


def print_hits(hits: list[SearchHit], preview_chars: int, hide_context: bool) -> None:
    print("\n[최종 검색 결과]")
    if not hits:
        print("검색 결과가 없습니다.")
        return
    for hit in hits:
        print("=" * 100)
        print(
            f"[{hit.rank}] {source_label(hit.metadata)} "
            f"rerank={fmt_score(hit.rerank_score)} rrf={fmt_score(hit.rrf_score)} "
            f"dense={fmt_score(hit.dense_score)} bm25={fmt_score(hit.bm25_score)}"
        )
        print(f"id={hit.chunk_id}")
        if not hide_context:
            print("-" * 100)
            print(normalize_context_text(hit.document)[:preview_chars])


def retrieve(args: argparse.Namespace, embedder: Any, collection: Any, records: list[CorpusRecord], bm25: BM25Okapi) -> list[SearchHit]:
    excluded_types = parse_csv(args.exclude_chunk_types)
    query_embedding = embedder.embed_query(args.query)
    dense_hits = dense_search(collection, query_embedding, args, excluded_types)
    bm25_hits = bm25_search(records, bm25, args.query, args, excluded_types)
    rrf_hits = rrf_fuse(dense_hits, bm25_hits, args.rrf_k, args.rrf_top_k)
    if not args.skip_rerank:
        co_client = get_cohere_client()
        final_candidates = cohere_rerank(co_client, args.query, rrf_hits, args)
    else:
        final_candidates = rrf_hits
    return final_candidates[: args.top_k]


def main() -> int:
    configure_output_encoding()
    load_dotenv()
    args = parse_args()

    embedder = make_embedder(
        provider=args.embedding_provider,
        model=args.embedding_model,
        dimensions=args.dimensions,
        device=args.device,
        openai_api_key_env=args.openai_api_key_env,
        hf_token_env=args.hf_token_env,
    )
    chroma_client = chromadb.PersistentClient(path=str(args.chroma_dir))
    collection = chroma_client.get_collection(name=args.collection)
    records = load_corpus(collection)
    bm25 = BM25Okapi([tokenize(retrieval_text(record)) for record in records])

    print("[검색 파이프라인] Dense + BM25 -> RRF -> " + ("Rerank" if not args.skip_rerank else "RRF final"))
    print(f"[임베딩] provider={embedder.provider} model={embedder.model} device={embedder.device or 'remote/api'} dims={embedder.dimensions or 'model default'}")

    final_hits = retrieve(args, embedder, collection, records, bm25)
    if not args.no_answer:
        answer_client = make_openai_client(args.openai_api_key_env)
        print("\n[답변]")
        print(generate_answer(answer_client, args.answer_model, args.query, final_hits, args.max_context_chars, args.temperature))

    print_hits(final_hits, args.preview_chars, args.hide_context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
