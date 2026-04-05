"""LLM utility — shared function for calling the Gemini API."""

from google import genai

from src.config import GEMINI_API_KEY, MODEL_NAME


def get_client() -> genai.Client:
    """Return a configured Gemini client."""
    return genai.Client(api_key=GEMINI_API_KEY)


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> str:
    """Call the Gemini API and return the text response.

    Raises ValueError if the response is empty.
    """
    client = get_client()
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
        ),
    )
    text = response.text
    if not text:
        raise ValueError("LLM returned an empty response")
    return text.strip()


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> str:
    """Call the Gemini API requesting JSON output.

    Returns raw JSON string. Caller is responsible for parsing.
    """
    client = get_client()
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    text = response.text
    if not text:
        raise ValueError("LLM returned an empty JSON response")
    return text.strip()
