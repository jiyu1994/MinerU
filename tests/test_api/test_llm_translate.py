import os
from openai import OpenAI

# --- Configuration ---
API_KEY = "apikey-dd675b2a3fcb4f1aa88b91503d87f730"
BASE_URL = "https://api.atlascloud.ai/v1"
MODEL = "google/gemini-3-pro-preview"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
response = client.chat.completions.create(
    model=MODEL,
    messages=[
    {
        "role": "user",
        "content": "hello"
    }
],
    max_tokens=64000,
    temperature=1
)
content = response.choices[0].message.content
print(content)