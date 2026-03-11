import os
import csv
import time
import re
from openai import OpenAI
from openai import RateLimitError, APITimeoutError, APIError


results = {}
log_output_dir = "dataset/logs"
translations_output_dir = "dataset/translations"
think_output = False

# Model Variables 
base_url = "https://api.tokenfactory.us-central1.nebius.com/v1/"
model = "deepseek-ai/DeepSeek-R1-0528-fast"
model_safe = model.replace("/", "-")
api_env = "NEBIUS_APIKEY"
prompt = "Take this theorem about free groups and restate it in terms of fundamental groups in algebraic topology. Make necessary assumptions to make the statement true. State the new theorem in as concise a form as possible. This means including assumptions within the theorem statement. Do not include additional explanation or text. {}."

# Token Counters
total_prompt_tokens = 0
total_completion_tokens = 0

# Read Theorems from .txt file
theorems = []
with open("dataset\\theorems.txt", "r", encoding="utf-8") as f:
    theorems = [line.strip() for line in f if line.strip()]

# Open API client connection and send a request (message) for each theorem
client = OpenAI(
    base_url = base_url,
    api_key= os.environ.get(api_env)
)


for i, theorem in enumerate(theorems):
    formatted_prompt = prompt.format(theorem)
    try:
        response = client.chat.completions.create(
            model= model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": formatted_prompt
                        }
                    ]
                }
            ]
        )
    except RateLimitError:
        results[theorem] = "RATE_LIMIT_ERROR"
    except APITimeoutError:
        results[theorem] = "TIMEOUT_ERROR"
    except APIError as e:
        results[theorem] = "API_ERROR" 
    else:
         translation = response.choices[0].message.content
         if not think_output:
            translation = re.sub(r'<think>.*?</think>', '', translation, flags=re.DOTALL).strip()
         results[theorem] = translation
         print(f"Translated Theorem {i+1}")
         total_prompt_tokens += response.usage.prompt_tokens
         total_completion_tokens += response.usage.completion_tokens
  


# Write dict of results {Orignal -> Translation} to CSV
field_names = ["ORIGINAL", "TRANSLATED"]
time_stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
with open(f"{translations_output_dir}/theorem_translations_{time_stamp}_{len(theorems)}_{model_safe}_v1.csv", mode="w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=field_names)
    writer.writeheader()
    for original, translated in results.items():
         writer.writerow({"ORIGINAL": original, "TRANSLATED": translated})

# Write a simple log file for later references
with open(f"{log_output_dir}/run_log_{time_stamp}_{model_safe}_v1.txt", "w") as log:
    log.write(f"Model: {model}\n")
    log.write(f"Theorem count: {len(theorems)}\n")
    log.write(f"Prompt tokens: {total_prompt_tokens}\n")
    log.write(f"Completion tokens: {total_completion_tokens}\n")
    log.write(f"Total tokens: {total_prompt_tokens + total_completion_tokens}\n")

