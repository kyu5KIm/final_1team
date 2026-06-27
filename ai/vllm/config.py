from __future__ import annotations

import os
import importlib.util
import re
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent


def load_env_files() -> None:
    candidates = [
        APP_DIR / ".env",
        ROOT_DIR / ".env",
        Path("/workspace/final_1team/runpod/.env"),
        Path("/workspace/final_1team/.env"),
        Path("/workspace/runpod/.env"),
        Path("/workspace/.env"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_files()

if os.getenv("CO_API_KEY") and not os.getenv("COHERE_API_KEY"):
    os.environ["COHERE_API_KEY"] = os.getenv("CO_API_KEY", "")
elif os.getenv("COHERE_API_KEY") and not os.getenv("CO_API_KEY"):
    os.environ["CO_API_KEY"] = os.getenv("COHERE_API_KEY", "")

if os.getenv("HF_HUB_ENABLE_HF_TRANSFER") == "1" and importlib.util.find_spec("hf_transfer") is None:
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"


TEXT_BACKEND = os.getenv("TEXT_BACKEND", "vllm")
TEXT_GGUF_REPO = os.getenv("TEXT_GGUF_REPO", "unsloth/gemma-4-12B-it-qat-GGUF")
TEXT_GGUF_FILENAME = os.getenv("TEXT_GGUF_FILENAME", "*Q4*.gguf")
DEFAULT_TEXT_MODEL_ID = TEXT_GGUF_REPO if TEXT_BACKEND == "llama_cpp" else "cyankiwi/gemma-4-12B-it-AWQ-INT4"
TEXT_MODEL_ID = os.getenv("TEXT_MODEL_ID") or os.getenv("RAG_ANSWER_MODEL") or DEFAULT_TEXT_MODEL_ID
TEXT_VLLM_BASE_URL = os.getenv("TEXT_VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
TEXT_VLLM_API_KEY = os.getenv("TEXT_VLLM_API_KEY", "EMPTY")
TEXT_VLLM_TIMEOUT_SEC = float(os.getenv("TEXT_VLLM_TIMEOUT_SEC", "300"))
TEXT_VLLM_STARTUP_WAIT_SEC = float(os.getenv("TEXT_VLLM_STARTUP_WAIT_SEC", "900"))
TEXT_VLLM_STARTUP_POLL_SEC = float(os.getenv("TEXT_VLLM_STARTUP_POLL_SEC", "5"))
OCR_MODEL_ID = os.getenv("OCR_MODEL_ID", "Qwen/Qwen2.5-VL-3B-Instruct")
STT_MODEL_ID = os.getenv("STT_MODEL_ID", "large-v3")
STT_DEVICE = os.getenv("STT_DEVICE", "cuda")
STT_COMPUTE_TYPE = os.getenv("STT_COMPUTE_TYPE", "float16")
STT_BATCH_SIZE = int(os.getenv("STT_BATCH_SIZE", "16"))
STT_PRELOAD_MODEL = os.getenv("STT_PRELOAD_MODEL", "false").lower() == "true"
STT_ENABLE_ALIGN = os.getenv("STT_ENABLE_ALIGN", "true").lower() == "true"
STT_ENABLE_DIARIZE = os.getenv("STT_ENABLE_DIARIZE", "false").lower() == "true"

LLAMA_N_CTX = int(os.getenv("LLAMA_N_CTX", "32768"))
LLAMA_N_GPU_LAYERS = int(os.getenv("LLAMA_N_GPU_LAYERS", "-1"))
LLAMA_N_THREADS = int(os.getenv("LLAMA_N_THREADS", "8"))
LLAMA_VERBOSE = os.getenv("LLAMA_VERBOSE", "false").lower() == "true"

LOAD_IN_4BIT = os.getenv("LOAD_IN_4BIT", "true").lower() == "true"
TORCH_DTYPE = os.getenv("TORCH_DTYPE", "auto")
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "2048"))
PRELOAD_TEXT_MODEL = os.getenv("PRELOAD_TEXT_MODEL", "true").lower() == "true"
PRELOAD_OCR_MODEL = os.getenv("PRELOAD_OCR_MODEL", "false").lower() == "true"

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "mineru_pdf_chunks_ko_sroberta")
QDRANT_COLLECTION_PROJECT_MODE = os.getenv("QDRANT_COLLECTION_PROJECT_MODE", "true").lower() == "true"
QDRANT_COLLECTION_PREFIX = os.getenv("QDRANT_COLLECTION_PREFIX", "hpm_project")
EMBEDDING_MODEL_ID = os.getenv("EMBEDDING_MODEL_ID", "jhgan/ko-sroberta-multitask")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
PRELOAD_EMBEDDING_MODEL = os.getenv("PRELOAD_EMBEDDING_MODEL", "true").lower() == "true"

CHAT_RAG_TOP_K = int(os.getenv("CHAT_RAG_TOP_K", "5"))
CHAT_RAG_MAX_CONTEXT_CHARS = int(os.getenv("CHAT_RAG_MAX_CONTEXT_CHARS", "6000"))
PIPELINE_TIMEOUT_SEC = int(os.getenv("PIPELINE_TIMEOUT_SEC", "2400"))


def feature_chat_dir_is_valid(path: Path) -> bool:
    return (
        (
            (path / "rag_search.py").exists()
            or (path / "04_query_qdrant_openai.py").exists()
        )
        and (path / "rag").exists()
    )


def default_feature_chat_dir() -> Path:
    candidates = [
        APP_DIR / "feature_chat",
        ROOT_DIR / "final_1team-feature-chat",
        ROOT_DIR / "runpod" / "feature_chat",
        Path("/workspace/runpod/feature_chat"),
        Path("/workspace/final_1team/runpod/feature_chat"),
        Path("/workspace/final_1team-feature-chat"),
        Path("/workspace/feature_chat"),
    ]
    for path in candidates:
        if feature_chat_dir_is_valid(path):
            return path
    return candidates[0]


def resolve_feature_chat_dir() -> Path:
    configured = os.getenv("FEATURE_CHAT_DIR")
    if configured:
        path = Path(configured)
        if feature_chat_dir_is_valid(path):
            return path
    return default_feature_chat_dir()


FEATURE_CHAT_DIR = resolve_feature_chat_dir()


def qdrant_collection_for_project(project_id: str | int | None) -> str:
    text = str(project_id or "").strip()
    if not QDRANT_COLLECTION_PROJECT_MODE or not text:
        return QDRANT_COLLECTION
    safe_project_id = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")
    if not safe_project_id:
        return QDRANT_COLLECTION
    safe_prefix = re.sub(r"[^A-Za-z0-9_-]+", "_", QDRANT_COLLECTION_PREFIX).strip("_")
    return f"{safe_prefix or 'project'}_{safe_project_id}"
