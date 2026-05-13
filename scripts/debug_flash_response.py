"""Quick diagnostic: inspect raw Deepseek V4 Flash response structure."""

import json
import os

# Load env
from dotenv import load_dotenv
load_dotenv()

from src.llm import get_client
from src.config import MODEL_NAME

client = get_client()

print(f"Model: {MODEL_NAME}")
print("=" * 60)

# Test WITHOUT response_format — rely on prompt for JSON
response = client.chat.completions.create(
    model=MODEL_NAME,
    messages=[
        {"role": "system", "content": "You are a JSON generator. Return ONLY a valid JSON array, no other text."},
        {"role": "user", "content": 'Return a JSON array with one object: {"name": "test", "value": 42}'}
    ],
    temperature=0.2,
    max_tokens=4096,
    extra_body={"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}},
)

choice = response.choices[0]
print(f"finish_reason: {choice.finish_reason}")
print()

# Check reasoning content (in model_extra for Deepseek)
extras = getattr(choice.message, "model_extra", {}) or {}
reasoning = extras.get("reasoning_content", "")
if reasoning:
    print("--- Reasoning content (truncated) ---")
    print(reasoning[:300])
    print()

print("--- Raw content ---")
print(repr(choice.message.content))
print()

# Try to parse the content
import re
content = choice.message.content or ""
# Strip think tags
content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL).strip()
# Strip code fences
if content.startswith("```"):
    content = re.sub(r"^```(?:json)?\s*\n?", "", content)
    content = re.sub(r"\n?```\s*$", "", content)
content = content.strip()

print("--- Cleaned content ---")
print(content)

try:
    parsed = json.loads(content)
    print(f"\n✅ Successfully parsed JSON: {parsed}")
except json.JSONDecodeError as e:
    print(f"\n❌ JSON parse failed: {e}")
