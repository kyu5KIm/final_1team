import os
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv


load_dotenv()

QDRANT_COLLECTION = "mineru_pdf_chunks_ko_sroberta"

qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)
embed_model = SentenceTransformer("jhgan/ko-sroberta-multitask")

def search_docs(question: str, limit: int = 3) -> str:
    query_vector = embed_model.encode(question).tolist()
    results = qdrant_client.search(
        collection_name = QDRANT_COLLECTION,
        query_vector = query_vector,
        limit = limit,
        with_payload = True
    )
    return "\n\n".join([r.payload["document"] for r in results])