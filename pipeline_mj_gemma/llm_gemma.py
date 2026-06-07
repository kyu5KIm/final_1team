import os
from dotenv import load_dotenv
from llama_cpp import Llama

load_dotenv()

MODEL_PATH = os.getenv("GEMMA_MODEL_PATH", "/workspace/gemma-4-12B-it-qat.gguf")

print(f"[LLM-Gemma] 모델 로딩 중: {MODEL_PATH}")

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=4096,
    n_gpu_layers=-1,   
    verbose=False,
)

print("[LLM-Gemma] 로딩 완료")


def call_llm(prompt: str) -> str:
    messages = [
        {
            "role": "system",
            "content": "반드시 한국어로만 답해라. 생각 과정은 출력하지 말고 최종 답변만 출력해라.",
        },
        {"role": "user", "content": prompt},
    ]
    response = llm.create_chat_completion(
        messages=messages,
        max_tokens=1024,
        temperature=0.0,
    )
    return response["choices"][0]["message"]["content"].strip()