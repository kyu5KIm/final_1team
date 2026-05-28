from __future__ import annotations

import importlib.util
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import chromadb
from openai import OpenAI
from rank_bm25 import BM25Okapi

from embedding_utils import DEFAULT_HF_EMBEDDING_MODEL, make_embedder


@dataclass
class RagSettings:
    chroma_dir: Path = Path("chroma_db")
    collection: str = "mineru_pdf_chunks_ko_sroberta"
    embedding_provider: str = "huggingface"
    embedding_model: str = DEFAULT_HF_EMBEDDING_MODEL
    dimensions: int | None = None
    device: str = "auto"
    answer_model: str = os.getenv("RAG_ANSWER_MODEL", "gpt-4.1-mini")
    openai_api_key_env: str = "OPENAI_API_KEY"
    hf_token_env: str = "HF_TOKEN"
    cohere_model: str = os.getenv("COHERE_RERANK_MODEL", "rerank-multilingual-v3.0")
    top_k: int = 5
    dense_k: int = 50
    dense_fetch_k: int = 200
    bm25_k: int = 50
    rrf_k: int = 60
    rrf_top_k: int = 50
    rerank_top_n: int = 10
    max_tokens_per_doc: int = 4096
    where_doc_id: str | None = None
    where_source_contains: str | None = None
    exclude_chunk_types: str = "image_caption,chart_caption"
    max_context_chars: int = 9000
    temperature: float = 0.0
    skip_rerank: bool = False


def load_query_module() -> ModuleType:
    module_path = Path(__file__).resolve().parent.parent / "04_query_chroma_openai.py"
    spec = importlib.util.spec_from_file_location("query_chroma_api", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_openai_client(env_name: str) -> OpenAI:
    api_key = os.getenv(env_name)
    if not api_key:
        raise RuntimeError(f"Missing {env_name}. Put it in .env or export it.")
    return OpenAI(api_key=api_key)


class RagService:
    def __init__(self, settings: RagSettings | None = None) -> None:
        self.settings = settings or RagSettings()
        self.query_module: ModuleType | None = None
        self.embedder: Any = None
        self.collection: Any = None
        self.records: list[Any] = []
        self.bm25: BM25Okapi | None = None
        self.answer_client: OpenAI | None = None
        self.loaded = False

    def load(self) -> None:
        if self.loaded:
            return

        self.query_module = load_query_module()
        self.embedder = make_embedder(
            provider=self.settings.embedding_provider,
            model=self.settings.embedding_model,
            dimensions=self.settings.dimensions,
            device=self.settings.device,
            openai_api_key_env=self.settings.openai_api_key_env,
            hf_token_env=self.settings.hf_token_env,
        )

        chroma_client = chromadb.PersistentClient(path=str(self.settings.chroma_dir))
        self.collection = chroma_client.get_collection(name=self.settings.collection)
        self.records = self.query_module.load_corpus(self.collection)
        self.bm25 = BM25Okapi(
            [self.query_module.tokenize(self.query_module.retrieval_text(record)) for record in self.records]
        )
        self.answer_client = make_openai_client(self.settings.openai_api_key_env)
        self.loaded = True

    def _request_args(self, question: str) -> Any:
        if self.query_module is None:
            raise RuntimeError("RagService is not loaded.")

        return self.query_module.argparse.Namespace(
            query=question,
            chroma_dir=self.settings.chroma_dir,
            collection=self.settings.collection,
            embedding_provider=self.settings.embedding_provider,
            embedding_model=self.settings.embedding_model,
            dimensions=self.settings.dimensions,
            device=self.settings.device,
            answer_model=self.settings.answer_model,
            openai_api_key_env=self.settings.openai_api_key_env,
            hf_token_env=self.settings.hf_token_env,
            cohere_model=self.settings.cohere_model,
            top_k=self.settings.top_k,
            dense_k=self.settings.dense_k,
            dense_fetch_k=self.settings.dense_fetch_k,
            bm25_k=self.settings.bm25_k,
            rrf_k=self.settings.rrf_k,
            rrf_top_k=self.settings.rrf_top_k,
            rerank_top_n=self.settings.rerank_top_n,
            max_tokens_per_doc=self.settings.max_tokens_per_doc,
            where_doc_id=self.settings.where_doc_id,
            where_source_contains=self.settings.where_source_contains,
            exclude_chunk_types=self.settings.exclude_chunk_types,
            max_context_chars=self.settings.max_context_chars,
            preview_chars=700,
            temperature=self.settings.temperature,
            skip_rerank=self.settings.skip_rerank,
            no_answer=False,
            hide_context=True,
        )

    def ask(self, question: str) -> dict[str, Any]:
        if not self.loaded:
            raise RuntimeError("RagService is not loaded.")
        if self.query_module is None or self.bm25 is None or self.answer_client is None:
            raise RuntimeError("RagService is missing required runtime objects.")

        question = question.strip()
        if not question:
            raise ValueError("question is empty")

        started = time.perf_counter()
        args = self._request_args(question)
        hits = self.query_module.retrieve(args, self.embedder, self.collection, self.records, self.bm25)
        answer = self.query_module.generate_answer(
            self.answer_client,
            self.settings.answer_model,
            question,
            hits,
            self.settings.max_context_chars,
            self.settings.temperature,
        )
        elapsed = time.perf_counter() - started
        sources = self.query_module.answer_source_references(hits)

        return {
            "answer": answer,
            "sources": sources,
            "elapsed_sec": round(elapsed, 3),
        }
