"""LLM utility — shared function for calling the Nvidia API."""

import re

import openai
import httpx

from src.config import DEEPINFRA_API_KEY, MODEL_NAME

# Deepseek thinking models prepend a <think>...</think> block to responses.
# Strip it so downstream parsers receive only the actual content.
_THINK_TAG_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def get_client() -> openai.Client:
    """Return a configured OpenAI client for DeepInfra API."""
    return openai.Client(
        api_key=DEEPINFRA_API_KEY,
        base_url="https://api.deepinfra.com/v1/openai",
        timeout=httpx.Timeout(600.0, connect=10.0),
    )


import time

def _execute_with_retries(func, *args, **kwargs):
    """Execute a function with exponential backoff and interactive fallback on failure."""
    max_attempts = 5
    base_wait = 2.0
    
    while True:
        for attempt in range(1, max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # If it's the last attempt of this cycle, break out to prompt the user
                if attempt == max_attempts:
                    print(f"\n❌ [LLM Error]: API call failed after {max_attempts} attempts. Last error: {e}")
                    break
                
                wait_time = base_wait * (2 ** (attempt - 1))
                print(f"⚠️  [LLM Error]: {e}. Retrying in {wait_time}s (Attempt {attempt}/{max_attempts})...")
                time.sleep(wait_time)
        
        # Interactive fallback
        user_input = input("\n🛑 API Server is busy or unreachable. Press Enter to retry another 5 times, or type 'exit' to abort: ").strip().lower()
        if user_input == 'exit':
            raise RuntimeError("Pipeline run aborted by user due to LLM API failure.")


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> str:
    """Call the Nvidia API and return the text response.

    Raises ValueError if the response is empty.
    """
    client = get_client()

    def _do_call():
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=16384,
            # Deepseek-specific: enable thinking mode.
            # Remove extra_body if switching to a non-Deepseek model.
            extra_body={"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}},
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty response")
        return _THINK_TAG_RE.sub("", content).strip()

    return _execute_with_retries(_do_call)


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> str:
    """Call the Nvidia API requesting JSON output.

    Returns raw JSON string. Caller is responsible for parsing.

    Note: We intentionally omit response_format={"type": "json_object"}
    because Deepseek thinking mode is incompatible with it (the model
    echoes the format spec instead of generating content). JSON output
    is enforced via the system prompt instead.
    """
    client = get_client()

    def _do_call():
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=16384,
            # Deepseek-specific: enable thinking mode.
            # Remove extra_body if switching to a non-Deepseek model.
            extra_body={"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}},
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned an empty JSON response")
        content = _THINK_TAG_RE.sub("", content).strip()
        # Strip markdown code fences if the model wraps JSON in ```json ... ```
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*\n?", "", content)
            content = re.sub(r"\n?```\s*$", "", content)
        return content.strip()

    return _execute_with_retries(_do_call)
