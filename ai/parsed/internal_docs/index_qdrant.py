#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG chunks -> Hugging Face or OpenAI embeddings -> Qdrant collection.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from qdrant_client import models
from tqdm import tqdm

try:
    from .rag.embeddings import DEFAULT_HF_EMBEDDING_MODEL, make_embedder
    from .rag.qdrant_store import (
        config_from_env,
        count_points,
        ensure_collection,
        existing_chunk_ids,
        make_client,
        qdrant_point_id,
    )
except ImportError:
    from rag.embeddings import DEFAULT_HF_EMBEDDING_MODEL, make_embedder
    from rag.qdrant_store import (
        config_from_env,
        count_points,
        ensure_collection,
        existing_chunk_ids,
        make_client,
        qdrant_point_id,
    )


SCALAR_TYPES = (str, int, float, bool)


@dataclass
class ChunkRecord:
    chunk_id: str
    text: str
    metadata: dict[str, Any]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Embed RAG chunks and upsert them into Qdrant.")
    p.add_argument("--input", type=Path, default=Path("chunks/chunks_mineru_v1.jsonl"))
    p.add_argument("--qdrant-url", default=None)
    p.add_argument("--qdrant-api-key", default=None)
    p.add_argument("--collection", type=str, default=None)
    p.add_argument("--prefer-grpc", action="store_true")
    p.add_argument("--manifest", type=Path, default=None)

    p.add_argument("--embedding-provider", choices=["huggingface", "openai"], default="huggingface")
    p.add_argument("--model", type=str, default=DEFAULT_HF_EMBEDDING_MODEL)
    p.add_argument("--dimensions", type=int, default=None)
    p.add_argument("--openai-api-key-env", type=str, default="OPENAI_API_KEY")
    p.add_argument("--hf-token-env", type=str, default="HF_TOKEN")
    p.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")

    p.add_argument("--embed-batch-size", type=int, default=64)
    p.add_argument("--upsert-batch-size", type=int, default=256)
    p.add_argument("--max-retries", type=int, default=6)
    p.add_argument("--retry-base-seconds", type=float, default=2.0)

    p.add_argument("--start-index", type=int, default=0)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--where-doc-id", type=str, default=None)
    p.add_argument("--where-source-contains", type=str, default=None)

    p.add_argument("--skip-existing", dest="skip_existing", action="store_true", default=True)
    p.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    p.add_argument("--reset", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--strict", action="store_true")
    return p.parse_args()


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def stable_chunk_id(text: str, metadata: dict[str, Any], fallback_index: int) -> str:
    doc_id = metadata.get("doc_id") or "unknown_doc"
    text_hash = sha1(text.encode("utf-8")).hexdigest()[:12]
    return f"{doc_id}::chunk_auto_{fallback_index:06d}_{text_hash}"


def normalize_text(text: Any) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def load_chunks(path: Path, strict: bool = False) -> list[ChunkRecord]:
    if not path.exists():
        raise FileNotFoundError(f"Chunk input not found: {path}")

    rows: list[ChunkRecord] = []
    seen_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                if strict:
                    raise
                print(f"[WARN] Skip malformed JSON line {line_no}: {exc}", file=sys.stderr)
                continue
            if not isinstance(obj, dict):
                if strict:
                    raise ValueError(f"Line {line_no} is not a JSON object")
                continue

            text = normalize_text(obj.get("text"))
            if not text:
                if strict:
                    raise ValueError(f"Line {line_no} has empty text")
                continue

            metadata = obj.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            else:
                metadata = dict(metadata)
            parent_id = obj.get("parent_id")
            parent_text = obj.get("parent_text")
            if parent_id not in (None, ""):
                metadata.setdefault("parent_id", str(parent_id))
            if parent_text not in (None, ""):
                metadata.setdefault("parent_text", str(parent_text))

            chunk_id = obj.get("chunk_id")
            if not isinstance(chunk_id, str) or not chunk_id.strip():
                chunk_id = stable_chunk_id(text, metadata, fallback_index=line_no)
            chunk_id = chunk_id.strip()
            if chunk_id in seen_ids:
                suffix = sha1(f"{chunk_id}:{line_no}:{text}".encode("utf-8")).hexdigest()[:8]
                chunk_id = f"{chunk_id}::dup_{suffix}"
            seen_ids.add(chunk_id)
            rows.append(ChunkRecord(chunk_id=chunk_id, text=text, metadata=metadata))
    return rows


def filter_chunks(rows: list[ChunkRecord], args: argparse.Namespace) -> list[ChunkRecord]:
    out = rows
    if args.where_doc_id:
        out = [r for r in out if str(r.metadata.get("doc_id")) == args.where_doc_id]
    if args.where_source_contains:
        needle = args.where_source_contains
        out = [r for r in out if needle in str(r.metadata.get("source_filename") or "")]
    if args.start_index:
        out = out[args.start_index :]
    if args.limit is not None:
        out = out[: args.limit]
    return out


def sanitize_payload_value(value: Any) -> Any:
    if value is None or isinstance(value, SCALAR_TYPES):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        return [sanitize_payload_value(item) for item in value if item is not None]
    if isinstance(value, dict):
        return {str(k): sanitize_payload_value(v) for k, v in value.items() if v is not None and str(k)}
    return str(value)


def sanitize_metadata(metadata: dict[str, Any], chunk: ChunkRecord, args: argparse.Namespace) -> dict[str, Any]:
    clean = {str(k): sanitize_payload_value(v) for k, v in metadata.items() if v is not None and str(k)}
    clean["chunk_id"] = chunk.chunk_id
    clean["text_sha1"] = sha1(chunk.text.encode("utf-8")).hexdigest()
    clean["indexed_at"] = utc_now()
    clean["embedding_provider"] = args.embedding_provider
    clean["embedding_model"] = args.model
    if args.dimensions is not None:
        clean["embedding_dimensions"] = args.dimensions
    clean.setdefault("doc_id", str(metadata.get("doc_id") or ""))
    clean.setdefault("source_filename", str(metadata.get("source_filename") or ""))
    clean.setdefault("chunk_type", str(metadata.get("chunk_type") or "unknown"))
    if metadata.get("parent_id") not in (None, ""):
        clean.setdefault("parent_id", str(metadata.get("parent_id")))
    if metadata.get("parent_text") not in (None, ""):
        clean.setdefault("parent_text", str(metadata.get("parent_text")))
    return clean


def batched(items: list[Any], batch_size: int) -> Iterable[list[Any]]:
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def embed_texts(embedder: Any, texts: list[str], max_retries: int, retry_base_seconds: float) -> list[list[float]]:
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            embeddings = embedder.embed_texts(texts)
            if len(embeddings) != len(texts):
                raise RuntimeError(f"Embedding count mismatch: got {len(embeddings)}, expected {len(texts)}")
            return embeddings
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            sleep_s = min(retry_base_seconds * (2 ** (attempt - 1)), 60.0)
            print(f"[WARN] Embedding request failed on attempt {attempt}/{max_retries}: {exc}")
            print(f"       retrying in {sleep_s:.1f}s...")
            time.sleep(sleep_s)
    raise RuntimeError(f"Embedding request failed after {max_retries} attempts: {last_exc}")


def upsert_records(client: Any, collection: str, chunks: list[ChunkRecord], embeddings: list[list[float]], args: argparse.Namespace) -> int:
    points = []
    for chunk, embedding in zip(chunks, embeddings):
        metadata = sanitize_metadata(chunk.metadata, chunk, args)
        points.append(
            models.PointStruct(
                id=qdrant_point_id(chunk.chunk_id),
                vector=embedding,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "document": chunk.text,
                    "parent_id": metadata.get("parent_id"),
                    "parent_text": metadata.get("parent_text"),
                    "metadata": metadata,
                },
            )
        )
    for batch in batched(points, args.upsert_batch_size):
        client.upsert(collection_name=collection, points=batch, wait=True)
    return len(points)


def count_by_metadata(rows: list[ChunkRecord], field: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = row.metadata.get(field)
        if isinstance(value, list):
            for item in value:
                counter[str(item)] += 1
        elif value not in (None, ""):
            counter[str(value)] += 1
        else:
            counter["unknown"] += 1
    return dict(counter.most_common())


def write_manifest(
    path: Path,
    args: argparse.Namespace,
    qdrant_url: str,
    collection: str,
    source_count: int,
    selected_count: int,
    skipped_count: int,
    indexed_count: int,
    collection_count: int | None,
    rows: list[ChunkRecord],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_at": utc_now(),
        "input": str(args.input),
        "qdrant_url": qdrant_url,
        "collection": collection,
        "embedding_provider": args.embedding_provider,
        "model": args.model,
        "dimensions": args.dimensions,
        "device": args.device,
        "source_chunk_count": source_count,
        "selected_chunk_count": selected_count,
        "skipped_existing_count": skipped_count,
        "indexed_count": indexed_count,
        "collection_count_after": collection_count,
        "skip_existing": args.skip_existing,
        "chunk_type_counts": count_by_metadata(rows, "chunk_type"),
        "doc_counts": count_by_metadata(rows, "doc_id"),
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    load_dotenv()
    args = parse_args()
    config = config_from_env(args.qdrant_url, args.qdrant_api_key, args.collection, args.prefer_grpc)
    manifest_path = args.manifest or Path("qdrant_index_manifest.json")

    all_rows = load_chunks(args.input, strict=args.strict)
    selected = filter_chunks(all_rows, args)

    print(f"[INFO] input chunks      : {args.input}")
    print(f"[INFO] loaded chunks     : {len(all_rows)}")
    print(f"[INFO] selected chunks   : {len(selected)}")
    print(f"[INFO] qdrant url        : {config.url}")
    print(f"[INFO] collection        : {config.collection}")
    print(f"[INFO] embedding provider: {args.embedding_provider}")
    print(f"[INFO] embedding model   : {args.model}")
    print(f"[INFO] skip existing     : {args.skip_existing}")

    if not selected:
        print("[INFO] No chunks selected. Nothing to index.")
        return 0
    if args.dry_run:
        print("[DRY RUN] No embedding or Qdrant calls made.")
        return 0

    embedder = make_embedder(
        provider=args.embedding_provider,
        model=args.model,
        dimensions=args.dimensions,
        device=args.device,
        openai_api_key_env=args.openai_api_key_env,
        hf_token_env=args.hf_token_env,
    )
    if not embedder.dimensions:
        sample = embedder.embed_query(selected[0].text)
        embedder.dimensions = len(sample)
    args.dimensions = int(embedder.dimensions)
    print(f"[INFO] resolved device   : {embedder.device or 'remote/api'}")
    print(f"[INFO] embedding dims    : {embedder.dimensions}")

    client = make_client(config)
    ensure_collection(client, config.collection, int(embedder.dimensions), reset=args.reset)

    to_index: list[ChunkRecord] = []
    skipped_existing = 0
    if args.skip_existing and not args.reset:
        for batch in tqdm(list(batched(selected, 1000)), desc="Checking existing Qdrant IDs"):
            existing = existing_chunk_ids(client, config.collection, [row.chunk_id for row in batch])
            for row in batch:
                if row.chunk_id in existing:
                    skipped_existing += 1
                else:
                    to_index.append(row)
    else:
        to_index = selected

    print(f"[INFO] to index          : {len(to_index)}")
    print(f"[INFO] skipped existing  : {skipped_existing}")

    indexed_count = 0
    for batch in tqdm(list(batched(to_index, args.embed_batch_size)), desc="Embedding + indexing"):
        embeddings = embed_texts(embedder, [row.text for row in batch], args.max_retries, args.retry_base_seconds)
        indexed_count += upsert_records(client, config.collection, batch, embeddings, args)

    try:
        collection_count = count_points(client, config.collection)
    except Exception:
        collection_count = None

    write_manifest(
        manifest_path,
        args,
        config.url,
        config.collection,
        len(all_rows),
        len(selected),
        skipped_existing,
        indexed_count,
        collection_count,
        selected,
    )

    print("[DONE]")
    print(f"  indexed          : {indexed_count}")
    print(f"  skipped_existing : {skipped_existing}")
    print(f"  collection_count : {collection_count}")
    print(f"  collection       : {config.collection}")
    print(f"  manifest         : {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
