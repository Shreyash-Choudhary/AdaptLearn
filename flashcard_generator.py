"""
flashcard_generator.py — Generate flashcards from document summary using Groq API.
Each flashcard has a front (concept/question) and back (answer/explanation).
"""

import os
import json
import re
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

FLASHCARD_PROMPT = """Create exactly 10 flashcards from the text below.

CRITICAL: Return ONLY a JSON array. No markdown. No code blocks. No preamble.
Start with [ and end with ]

Each flashcard must have EXACTLY these fields:
- "front": a short question, term, or concept (max 15 words)
- "back": a clear explanation or answer (1-3 sentences)
- "category": one of "Definition", "Concept", "Formula", "Fact", "Application"
- "hint": a one-word memory hint

Example:
[{{"front": "What is photosynthesis?", "back": "The process by which plants convert sunlight, CO2 and water into glucose and oxygen.", "category": "Definition", "hint": "sunlight"}}]

TEXT:
{summary}"""


def generate_flashcards(summary: str) -> list:
    """Generate 10 flashcards from a summary. Returns list of dicts."""
    print("[flashcard_generator] Calling Groq API for flashcards…")

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": FLASHCARD_PROMPT.format(summary=summary)}],
        temperature=0.6,
        max_tokens=3000,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()

    start = raw.find("[")
    end   = raw.rfind("]")
    if start == -1 or end == -1:
        print("[flashcard_generator] No JSON array found, returning empty list")
        return []

    raw = raw[start:end + 1]
    raw = re.sub(r",\s*]", "]", raw)
    raw = re.sub(r",\s*}", "}", raw)

    try:
        cards = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[flashcard_generator] JSON parse error: {e}")
        return []

    validated = []
    for c in cards:
        if not isinstance(c, dict):
            continue
        front = c.get("front", "").strip()
        back  = c.get("back", "").strip()
        if not front or not back:
            continue
        validated.append({
            "front":    front,
            "back":     back,
            "category": c.get("category", "Concept"),
            "hint":     c.get("hint", ""),
        })

    print(f"[flashcard_generator] Generated {len(validated)} flashcards")
    return validated
