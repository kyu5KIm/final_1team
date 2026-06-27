from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from config import (
    CHUNK_ENCODING,
    CHUNK_MAX_TABLE_TOKENS,
    CHUNK_MIN_CHARS,
    CHUNK_OVERLAP,
    CHUNK_SCRIPT_PATH,
    CHUNK_SIZE,
    CHUNK_VERSION,
    MINERU_BACKEND,
    MINERU_FORMULA,
    MINERU_LANG,
    MINERU_METHOD,
    MINERU_TABLE,
    MINERU_TIMEOUT_SEC,
    PARSER_SCRIPT_PATH,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_URL,
    qdrant_collection_for_project,
)
from model_runtime import embed_texts, load_embedding_model


def load_script_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load script module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def clean_text(text: str) -> str:
    text = re.sub(r"\x00", "", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_parser(input_dir: Path, output_dir: Path, require_cuda: bool = True) -> dict[str, Any]:
    if not PARSER_SCRIPT_PATH.exists():
        raise RuntimeError(f"Parser script was not found: {PARSER_SCRIPT_PATH}")
    started = time.perf_counter()
    parser_module = load_script_module(PARSER_SCRIPT_PATH, "ocr_parse_pdfs_module")
    args = parser_module.argparse.Namespace(
        input_dir=input_dir,
        output_dir=output_dir,
        work_dir=None,
        backend=MINERU_BACKEND,
        method=MINERU_METHOD,
        lang=MINERU_LANG,
        recursive=True,
        start_index=0,
        limit=None,
        only=None,
        force=True,
        auto_fallback=True,
        keep_work=False,
        keep_raw=False,
        timeout=MINERU_TIMEOUT_SEC,
        cuda="0",
        require_cuda=require_cuda,
        formula=MINERU_FORMULA,
        table=MINERU_TABLE,
        api_url=None,
        disable_repeated_margin_clean=False,
        enable_ocr_corrections=True,
        secondary_text=True,
        quality_report=True,
    )

    try:
        parser_module.check_mineru_cli()
        parser_module.check_cuda_requirement(args)
        dirs = parser_module.ensure_output_dirs(output_dir.resolve())
        work_dir = parser_module.select_work_dir(args.work_dir)
        pdfs = parser_module.find_pdfs(
            input_dir.resolve(),
            recursive=args.recursive,
            only=args.only,
            start_index=args.start_index,
            limit=args.limit,
        )
        manifest_path = dirs["manifests"] / "parse_manifest.jsonl"
        registry_path = dirs["manifests"] / "document_registry.jsonl"
        records = []
        success = skipped = failed = 0
        for pdf_path in pdfs:
            record = parser_module.process_pdf(pdf_path, dirs, work_dir, args)
            parser_module.append_jsonl(manifest_path, record)
            registry_record = {
                "doc_id": record.get("doc_id"),
                "source_pdf": record.get("source_pdf"),
                "source_filename": record.get("source_filename"),
                "source_sha256": record.get("source_sha256"),
                "status": record.get("status"),
                "content_list_path": record.get("content_list_path"),
                "markdown_path": record.get("markdown_path"),
                "secondary_text_path": record.get("secondary_text_path"),
                "quality_report_path": record.get("quality_report_path"),
                "created_at": record.get("finished_at"),
            }
            parser_module.append_jsonl(registry_path, registry_record)
            records.append(record)
            status = record.get("status")
            if status == "success":
                success += 1
            elif status == "skipped":
                skipped += 1
            else:
                failed += 1

        total_blocks = parser_module.rebuild_all_blocks(dirs["json"])
        if pdfs and total_blocks == 0:
            failed_reasons = [
                {
                    "file": record.get("source_filename"),
                    "status": record.get("status"),
                    "reason": record.get("reason"),
                }
                for record in records[:5]
            ]
            raise RuntimeError(
                "MinerU parser produced no blocks: "
                f"pdf_count={len(pdfs)} success={success} failed={failed} "
                f"reasons={json.dumps(failed_reasons, ensure_ascii=False)}"
            )
    except Exception as exc:
        raise RuntimeError(f"MinerU parser failed: {exc}") from exc

    return {
        "mode": "direct_import",
        "script": str(PARSER_SCRIPT_PATH),
        "elapsed_sec": round(time.perf_counter() - started, 3),
        "pdf_count": len(pdfs),
        "success": success,
        "skipped": skipped,
        "failed": failed,
        "blocks": total_blocks,
        "all_blocks_path": str(dirs["json"] / "all_blocks.jsonl"),
        "records": records,
    }


def run_chunker(parsed_dir: Path, pdf_dir: Path, chunks_dir: Path) -> dict[str, Any]:
    input_path = parsed_dir / "json" / "all_blocks.jsonl"
    output_path = chunks_dir / "chunks_mineru_v1.jsonl"
    manifest_path = chunks_dir / "chunk_manifest.json"
    if not input_path.exists():
        raise RuntimeError(f"MinerU all_blocks.jsonl was not found: {input_path}")
    if not CHUNK_SCRIPT_PATH.exists():
        raise RuntimeError(f"Chunk script was not found: {CHUNK_SCRIPT_PATH}")
    started = time.perf_counter()
    chunk_module = load_script_module(CHUNK_SCRIPT_PATH, "ocr_make_chunks_module")
    args = chunk_module.argparse.Namespace(
        input=input_path,
        pdf_dir=pdf_dir,
        output=output_path,
        manifest=manifest_path,
        chunk_size=CHUNK_SIZE,
        overlap=CHUNK_OVERLAP,
        encoding=CHUNK_ENCODING,
        chunk_version=CHUNK_VERSION,
        min_chars=CHUNK_MIN_CHARS,
        max_table_tokens=CHUNK_MAX_TABLE_TOKENS,
        strict=False,
    )
    if args.overlap >= args.chunk_size:
        raise RuntimeError("Chunking failed: overlap must be smaller than chunk size")
    rows = chunk_module.read_jsonl(args.input, args.strict)
    filename_by_sha = chunk_module.pdf_hash_map(args.pdf_dir)
    tokenizer = chunk_module.Tokenizer(args.encoding)
    chunks = chunk_module.build_chunks(rows, tokenizer, args, filename_by_sha)
    chunk_module.write_jsonl(args.output, chunks)
    chunk_module.write_manifest(args.manifest, args, chunks, tokenizer)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    return {
        "mode": "direct_import",
        "script": str(CHUNK_SCRIPT_PATH),
        "output": str(output_path),
        "manifest": manifest,
        "elapsed_sec": round(time.perf_counter() - started, 3),
        "blocks": len(rows),
        "chunks": len(chunks),
    }


def read_chunks_jsonl(path: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, 1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise RuntimeError(f"Invalid chunk JSON at line {line_no}")
            chunk_id = str(obj.get("chunk_id") or "")
            text = clean_text(str(obj.get("text") or obj.get("document") or ""))
            metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
            if chunk_id and text:
                chunk: dict[str, Any] = {"chunk_id": chunk_id, "document": text, "metadata": metadata}
                parent_text = clean_text(str(obj.get("parent_text") or ""))
                parent_id = str(obj.get("parent_id") or metadata.get("parent_id") or "").strip()
                if parent_text:
                    chunk["parent_text"] = parent_text
                if parent_id:
                    chunk["parent_id"] = parent_id
                chunks.append(chunk)
    return chunks


def make_text_chunks(text: str, metadata: dict[str, Any], *, chunk_size: int | None = None, overlap: int | None = None) -> list[dict[str, Any]]:
    text = clean_text(text)
    if not text:
        return []

    chunk_size = chunk_size or CHUNK_SIZE
    overlap = min(overlap if overlap is not None else CHUNK_OVERLAP, max(0, chunk_size - 1))
    chunk_version = f"text_v1_{chunk_size}"
    source = str(metadata.get("source_path") or metadata.get("title") or metadata.get("source_filename") or "text")
    doc_ref = str(metadata.get("document_id") or metadata.get("doc_id") or hashlib.sha1(source.encode("utf-8")).hexdigest()[:12])

    try:
        tokenizer_module = load_script_module(CHUNK_SCRIPT_PATH, "ocr_text_chunk_module")
        tokenizer = tokenizer_module.Tokenizer(CHUNK_ENCODING)
    except Exception:
        tokenizer = None

    def token_count(value: str) -> int:
        if tokenizer is not None:
            return int(tokenizer.count(value))
        return max(1, len(value) // 2)

    def split_long(value: str) -> list[str]:
        if tokenizer is not None:
            return tokenizer.split(value, chunk_size, overlap)
        max_chars = max(1, chunk_size * 2)
        overlap_chars = max(0, overlap * 2)
        pieces: list[str] = []
        start = 0
        while start < len(value):
            end = min(len(value), start + max_chars)
            piece = value[start:end].strip()
            if piece:
                pieces.append(piece)
            if end >= len(value):
                break
            start = max(0, end - overlap_chars)
        return pieces

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    groups: list[str] = []
    current = ""
    for paragraph in paragraphs or [text]:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if token_count(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            groups.extend(split_long(current))
        current = paragraph
    if current:
        groups.extend(split_long(current))

    chunks: list[dict[str, Any]] = []
    total = len(groups)
    for index, chunk_text in enumerate(groups):
        digest = hashlib.sha1(f"{doc_ref}:{index}:{chunk_text}".encode("utf-8")).hexdigest()[:10]
        chunk_id = f"document_{doc_ref}::text_chunk_{index:07d}_{digest}"
        parent_id = f"document_{doc_ref}::parent_text_{index:07d}_{digest}"
        parent_title = str(metadata.get("title") or metadata.get("source_filename") or "text")
        chunk_metadata = {
            **metadata,
            "chunk_id": chunk_id,
            "chunk_version": chunk_version,
            "chunk_type": "text",
            "parent_id": parent_id,
            "parent_type": "text",
            "parent_title": parent_title,
            "parent_page_start": 1,
            "parent_page_end": 1,
            "parent_token_count": token_count(chunk_text),
            "parent_char_count": len(chunk_text),
            "child_index": 1,
            "child_count": 1,
            "child_token_count": token_count(chunk_text),
            "child_char_count": len(chunk_text),
            "page": 1,
            "page_start": 1,
            "page_end": 1,
            "chunk_index": index,
            "chunk_index_in_group": index + 1,
            "chunk_count_in_group": total,
            "chunk_seq_global": index + 1,
            "token_count": token_count(chunk_text),
            "char_count": len(chunk_text),
            "parser": "text",
        }
        chunks.append(
            {
                "chunk_id": chunk_id,
                "parent_id": parent_id,
                "parent_text": chunk_text,
                "document": chunk_text,
                "metadata": chunk_metadata,
            }
        )
    return chunks


def qdrant_point_id(chunk_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"hpm-mineru:{chunk_id}"))


def ensure_payload_indexes(client: Any, collection_name: str) -> None:
    from qdrant_client import models

    for field_name in [
        "metadata.source_type",
        "metadata.project_id",
        "metadata.document_id",
        "metadata.doc_id",
        "metadata.parent_id",
    ]:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:
            message = str(exc).lower()
            if "already exists" not in message and "already has" not in message:
                raise


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _canonical_chunk_payload(chunk: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    chunk_metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    combined_metadata = {
        **metadata,
        **chunk_metadata,
        "chunk_id": chunk["chunk_id"],
        "parser": chunk_metadata.get("parser") or metadata.get("parser") or "mineru",
    }
    parent_id = _first_value(chunk, "parent_id") or _first_value(combined_metadata, "parent_id")
    parent_text = _first_value(chunk, "parent_text") or _first_value(combined_metadata, "parent_text")
    if parent_id is not None:
        combined_metadata.setdefault("parent_id", parent_id)
    if parent_text is not None:
        combined_metadata.setdefault("parent_text", parent_text)

    page = _int_or_none(
        _first_value(combined_metadata, "page", "page_no", "page_number", "page_start")
    )
    chunk_index = _int_or_none(_first_value(combined_metadata, "chunk_index"))
    if chunk_index is None:
        sequence = _int_or_none(_first_value(combined_metadata, "chunk_seq_global"))
        group_index = _int_or_none(_first_value(combined_metadata, "chunk_index_in_group"))
        if sequence is not None:
            chunk_index = max(0, sequence - 1)
        elif group_index is not None:
            chunk_index = max(0, group_index - 1)

    title = _first_value(combined_metadata, "title", "source_filename", "file_name")
    source_path = _first_value(
        combined_metadata,
        "source_path",
        "document_path",
        "s3_uri",
        "s3_url",
        "storage_key",
        "source_pdf",
    )

    canonical = {
        "doc_id": _first_value(combined_metadata, "doc_id"),
        "document_id": _first_value(combined_metadata, "document_id"),
        "project_id": _first_value(combined_metadata, "project_id"),
        "title": title,
        "page": page,
        "chunk_index": chunk_index,
        "source_path": source_path,
        "source_sha256": _first_value(combined_metadata, "source_sha256"),
        "source_type": _first_value(combined_metadata, "source_type", "document_type", "doc_type"),
        "viewer_type": _first_value(combined_metadata, "viewer_type"),
        "viewer_id": _first_value(combined_metadata, "viewer_id", "document_id"),
        "parent_id": _first_value(combined_metadata, "parent_id"),
    }
    for key, value in canonical.items():
        if value is not None:
            combined_metadata.setdefault(key, value)

    payload = {
        "chunk_id": chunk["chunk_id"],
        "document": chunk["document"],
        "content": chunk["document"],
        "metadata": combined_metadata,
    }
    if parent_id is not None:
        payload["parent_id"] = parent_id
    if parent_text is not None:
        payload["parent_text"] = parent_text
    payload.update({key: value for key, value in canonical.items() if value is not None})
    return payload


def upsert_chunks_to_qdrant(
    chunks: list[dict[str, Any]],
    metadata: dict[str, Any],
    qdrant_url: str | None = None,
    qdrant_api_key: str | None = None,
    collection: str | None = None,
) -> int:
    if not chunks:
        return 0
    from qdrant_client import QdrantClient, models

    bundle = load_embedding_model()
    vectors = embed_texts([chunk["document"] for chunk in chunks])
    client = QdrantClient(url=qdrant_url or QDRANT_URL, api_key=qdrant_api_key if qdrant_api_key is not None else QDRANT_API_KEY)
    collection_name = collection or qdrant_collection_for_project(metadata.get("project_id"))
    try:
        exists = bool(client.collection_exists(collection_name))
    except AttributeError:
        exists = collection_name in {item.name for item in client.get_collections().collections}
    if not exists:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=bundle.dimensions, distance=models.Distance.COSINE),
        )
    ensure_payload_indexes(client, collection_name)
    points = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        points.append(
            models.PointStruct(
                id=qdrant_point_id(chunk["chunk_id"]),
                vector=vector,
                payload=_canonical_chunk_payload(chunk, metadata),
            )
        )
    client.upsert(collection_name=collection_name, points=points)
    return len(points)


def ingest_pdf_chunks(
    pdf_dir: Path,
    parsed_dir: Path,
    chunks_dir: Path,
    metadata: dict[str, Any],
    *,
    require_cuda: bool = True,
    qdrant_url: str | None = None,
    qdrant_api_key: str | None = None,
    collection: str | None = None,
) -> dict[str, Any]:
    parser_info = run_parser(pdf_dir, parsed_dir, require_cuda=require_cuda)
    chunker_info = run_chunker(parsed_dir, pdf_dir, chunks_dir)
    chunks = read_chunks_jsonl(Path(str(chunker_info["output"])))
    upserted = upsert_chunks_to_qdrant(chunks, metadata, qdrant_url=qdrant_url, qdrant_api_key=qdrant_api_key, collection=collection)
    return {"parser": parser_info, "chunker": chunker_info, "chunks": chunks, "upserted": upserted}
