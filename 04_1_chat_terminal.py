#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
from pathlib import Path
from types import ModuleType

import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from rank_bm25 import BM25Okapi

from embedding_utils import DEFAULT_HF_EMBEDDING_MODEL, make_embedder


def load_query_module() -> ModuleType:
    module_path = Path(__file__).with_name("04_query_chroma_openai.py")
    spec = importlib.util.spec_from_file_location("query_chroma", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive terminal chatbot over ChromaDB.")
    parser.add_argument("--chroma-dir", type=Path, default=Path("chroma_db"))
    parser.add_argument("--collection", default="mineru_pdf_chunks_ko_sroberta")
    parser.add_argument("--embedding-provider", choices=["huggingface", "openai"], default="huggingface")
    parser.add_argument("--embedding-model", "--model", dest="embedding_model", default=DEFAULT_HF_EMBEDDING_MODEL)
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--answer-model", default=os.getenv("RAG_ANSWER_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--openai-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--hf-token-env", default="HF_TOKEN")
    parser.add_argument("--cohere-model", default=os.getenv("COHERE_RERANK_MODEL", "rerank-v3.5"))
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
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--skip-rerank", action="store_true")
    return parser.parse_args()


def make_openai_client(env_name: str) -> OpenAI:
    api_key = os.getenv(env_name)
    if not api_key:
        raise RuntimeError(f"Missing {env_name}. Put it in .env or export it.")
    return OpenAI(api_key=api_key)


def main() -> int:
    configure_output_encoding()
    load_dotenv()
    args = parse_args()
    query_module = load_query_module()

    print("[초기화] 임베딩 모델 로드 중...")
    embedder = make_embedder(
        provider=args.embedding_provider,
        model=args.embedding_model,
        dimensions=args.dimensions,
        device=args.device,
        openai_api_key_env=args.openai_api_key_env,
        hf_token_env=args.hf_token_env,
    )
    print(f"[임베딩] provider={embedder.provider} model={embedder.model} device={embedder.device or 'remote/api'} dims={embedder.dimensions or 'model default'}")

    chroma_client = chromadb.PersistentClient(path=str(args.chroma_dir))
    collection = chroma_client.get_collection(name=args.collection)
    records = query_module.load_corpus(collection)
    bm25 = BM25Okapi([query_module.tokenize(query_module.retrieval_text(record)) for record in records])
    answer_client = make_openai_client(args.openai_api_key_env)

    print("[준비 완료] 질문을 입력하세요. 종료: exit, quit, q")
    while True:
        try:
            query = input("\n질문> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not query:
            continue
        if query.lower() in {"exit", "quit", "q"}:
            break

        start = time.perf_counter()
        args.query = query
        try:
            hits = query_module.retrieve(args, embedder, collection, records, bm25)
            answer = query_module.generate_answer(
                answer_client,
                args.answer_model,
                query,
                hits,
                args.max_context_chars,
                args.temperature,
            )
            elapsed = time.perf_counter() - start
            print("\n[답변]")
            print(answer)
            print(f"\n[답변 시간] {elapsed:.2f}초")
        except Exception as exc:
            elapsed = time.perf_counter() - start
            print(f"[ERROR] {exc}")
            print(f"[소요 시간] {elapsed:.2f}초")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
