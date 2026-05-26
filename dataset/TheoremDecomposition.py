from vllm import LLM, SamplingParams
from vllm.sampling_params import StructuredOutputsParams
from pydantic import BaseModel
from typing import List
import json, os

INPUT_FILE = 'PATH'
OUTPUT_FILE = 'PATH'
CHUNK_SIZE = 5000

class TheoremDeconstruction(BaseModel):
    input_statement: str
    hypotheses: List[str]
    conclusions: List[str]
    normalized_form: str

SYSTEM_PROMPT = """
You are a mathematical statement parser.

Task:
Given a single research-level mathematical statement (theorem, lemma, proposition, corollary, claim, definition-like implication, or assertion), decompose it into:
1. hypotheses/assumptions
2. conclusions
Also rewrite the theorem in normalized_form which must be a single string of the form:
  "If [H1] and [H2] and ... then [C]."
"""

if __name__ == '__main__':
    DATA = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        DATA = json.load(f)

    MAX_ITEMS = len(DATA)

    sampling_params = SamplingParams(
        temperature=0.7, top_p=0.8, top_k=20, min_p=0.0,
        presence_penalty=1.5, repetition_penalty=1.0,
        max_tokens=2000, stop=["<|im_end|>"],
        structured_outputs=StructuredOutputsParams(
            json=TheoremDeconstruction.model_json_schema()
        )
    )

    llm = LLM(
        model="Qwen/Qwen3.5-9B",
        max_num_seqs=512,
        enforce_eager=True,
        max_model_len=4096,
        trust_remote_code=True
    )

    start_index = 0
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as f:
            start_index = sum(1 for _ in f)

    for i in range(start_index, MAX_ITEMS, CHUNK_SIZE):
        batch = DATA[i: i + CHUNK_SIZE]

        valid_batch = [d for d in batch if d["metadata"]['kind'] == "theorem"]

        if not valid_batch:
            continue

        theorems = [d["views"]["nl_informal"] for d in valid_batch]
        prompts = [f"<|im_start|>system\n" + SYSTEM_PROMPT + "<|im_end|>\n<|im_start|>user\n" + t + "<|im_end|>\n<|im_start|>assistant\n" for t in theorems]

        outputs = llm.generate(prompts, sampling_params)

        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            for d, output in zip(valid_batch, outputs):
                raw_string = output.outputs[0].text
                try:
                    d["deconstruction"] = json.loads(raw_string)
                except Exception:
                    d["deconstruction"] = None
                f.write(json.dumps(d) + "\n")
            f.flush()