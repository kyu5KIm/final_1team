# llm.py
import os
import torch
from dotenv import load_dotenv
from transformers import AutoModelForCausalLM, AutoTokenizer

load_dotenv()

MODEL_NAME = os.getenv("RAG_ANSWER_MODEL", "Qwen/Qwen2.5-7B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")

print(f"[LLM] 모델 로딩 중: {MODEL_NAME}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, token=HF_TOKEN, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    token=HF_TOKEN,
    trust_remote_code=True,
    device_map="auto",
    torch_dtype=torch.bfloat16
)
model.eval()
print(f"[LLM] 로딩 완료")

def call_llm(prompt: str) -> str:
    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
        enable_thinking=False  # ← Qwen3 thinking 모드 끄기
    )
    inputs = {k: v.to(model.device) for k, v in inputs.items()}

    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=1024,
            do_sample=False,
            eos_token_id=tokenizer.eos_token_id,
        )

    input_length = inputs["input_ids"].shape[-1]
    generated = outputs[0][input_length:]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()