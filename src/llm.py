"""LLM utility — shared function for calling the Gemini API."""

from google import genai

from src.config import GEMINI_API_KEY, MODEL_NAME


def get_client() -> genai.Client:
    """Return a configured Gemini client."""
    return genai.Client(api_key=GEMINI_API_KEY)


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
    """Call the Gemini API and return the text response.

    Raises ValueError if the response is empty.
    """
    client = get_client()

    def _do_call():
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
            ),
        )
        if not response.text:
            raise ValueError("LLM returned an empty response")
        return response.text.strip()

    return _execute_with_retries(_do_call)


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> str:
    """Call the Gemini API requesting JSON output.

    Returns raw JSON string. Caller is responsible for parsing.
    """
    client = get_client()

    def _do_call():
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        if not response.text:
            raise ValueError("LLM returned an empty JSON response")
        return response.text.strip()

    return _execute_with_retries(_do_call)
