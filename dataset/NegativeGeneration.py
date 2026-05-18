import json
import os
from typing import List

from pydantic import BaseModel
from vllm import LLM, SamplingParams
from vllm.sampling_params import StructuredOutputsParams

INPUT_FILE = '/gpfs/scrubbed/raosa/results/processed_train.jsonl'
OUTPUT_FILE = '/gpfs/scrubbed/raosa/results/hard_negatives.jsonl'
CHUNK_SIZE = 1000  # Reduced from 5000 so you don't lose as much on a node crash

class NegativeGeneration(BaseModel):
    hard_negatives : List[str]

SYSTEM_PROMPT = """
You are an expert mathematical editor.

Task:
Given a string with "input_statement", "hypotheses", "conclusions", "normalized_form", "subject"), generate exactly 3 "hard_negatives" — statements that closely mimic the visual and syntactic structure of the "input_statement" but are strictly mathematically false or semantically different.

Guidelines for Hard Negatives (This is not an exhaustive list of guidelines):
1. Subtle Omission: If it would create a mathematically different statement then omit a property that is a prerequisite for the conclusion, or remove a specific conclusion 
2. Commutative Flip: If it would create a mathematically different statement then reverse the order of a product that is not commutable in a way that is plausible but strictly breaks the equality.
3. Negation: If a negation would create a mathematically different statement, then negate an assumption or conclusion to fundamentally alter the semantic meaning of the statement.

Validity: 
- Every variable used in the conclusion must be defined in the hypotheses. Every operator must act on the correct type of object.
- The statement must be read as a valid, grammatically correct mathematical sentence, even though the underlying claim is false.
- It cannot simply be a "weaker" true statement. If the original theorem guarantees x > 0, generating a negative that says x \ge 0 is invalid because it is still a true mathematical statement. Do not merely omit a conclusion or weaken an inequality without introducing a strict contradiction or a false mathematical guarantee.

Style Constraints:
- Preserve the original LaTeX formatting style, notation, and complexity.
- The visual "weight" of each equation must match the original theorem exactly.
"""

if __name__ == '__main__':
    DATA = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        DATA = [json.loads(line) for line in f]

    start_index = 0
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as f:
            start_index = sum(1 for _ in f)

    if start_index >= len(DATA):
        print("Job already completed! Output file matches input file length.")
        exit(0)
        
    print(f"Resuming from index {start_index} / {len(DATA)}")

    sampling_params = SamplingParams(
        temperature=0.7, top_p=0.8, top_k=20, min_p=0.0,
        presence_penalty=1.5, repetition_penalty=1.0,
        max_tokens=2000, stop=["<|im_end|>"],
        structured_outputs=StructuredOutputsParams(
            json=NegativeGeneration.model_json_schema()
        )
    )

    llm = LLM(
        model="Qwen/Qwen3.5-9B",
        max_num_seqs=512,
        enforce_eager=True,
        max_model_len=4096,
        trust_remote_code=True
    )

    for i in range(start_index, len(DATA), CHUNK_SIZE):
        batch = DATA[i: i + CHUNK_SIZE]
        
        prompts = []
        valid_indices = []

        for idx, d in enumerate(batch):
            entry = d.get("deconstruction")
            if entry and entry.get("input_statement") and isinstance(entry["input_statement"], str):
                content = {
                    "input_statement": entry.get("input_statement"),
                    "hypotheses": entry.get("hypotheses"),
                    "conclusions": entry.get("conclusions"),
                    "normalized_form": entry.get("normalized_form"),
                }
                e_json = json.dumps(content, ensure_ascii=True)
                prompt_str = f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\n{e_json}<|im_end|>\n<|im_start|>assistant\n"
                
                prompts.append(prompt_str)
                valid_indices.append(idx)

        batch_results = [None] * len(batch)

        if prompts:
            try:
                batch_outputs = llm.generate(prompts, sampling_params, use_tqdm=True)
                for v_idx, out in zip(valid_indices, batch_outputs):
                    batch_results[v_idx] = out
            except Exception as batch_error:
                print(f"Batch {i} failed. Switching to Surgical Mode. Error: {batch_error}")
                for v_idx, p_str in zip(valid_indices, prompts):
                    try:
                        single_out = llm.generate([p_str], sampling_params, use_tqdm=False)
                        batch_results[v_idx] = single_out[0]
                    except Exception as single_error:
                        print(f"Tombstone written for row {i + v_idx} due to error: {single_error}")

        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            for j, d in enumerate(batch):
                out = batch_results[j]
                
                if "hard_negatives" not in d:
                    d["hard_negatives"] = {}
                
                if out is not None:
                    raw_string = out.outputs[0].text
                    try:
                        parsed_output = json.loads(raw_string)
                        d["hard_negatives"]["nl"] = parsed_output.get("hard_negatives", [])
                    except Exception:
                        d["hard_negatives"]["nl"] = None
                else:
                    d["hard_negatives"]["nl"] = None
                

                clean_json_str = json.dumps(d, ensure_ascii=False, default=str).encode('utf-8', 'replace').decode('utf-8')
                f.write(clean_json_str + "\n")
                
            f.flush()
