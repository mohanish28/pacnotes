"""Sends the transcript to Gemini, using meeting-notes-prompt.md as the system prompt."""
from pathlib import Path

from google import genai
from google.genai import types

# meeting-notes-prompt.md lives at the project root, one level above this package.
PROMPT_PATH = Path(__file__).resolve().parent.parent / "meeting-notes-prompt.md"


def enhance_notes(transcript: str, api_key: str, model: str) -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"Missing prompt file: {PROMPT_PATH}")
    system_instruction = PROMPT_PATH.read_text(encoding="utf-8")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=transcript,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")
    return response.text
