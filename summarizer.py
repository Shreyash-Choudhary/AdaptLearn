"""
summarizer.py - Summarisation using Groq API instead of local BART model.
No heavy model download needed — uses the same Groq API already in your project.
"""

import os
from groq import Groq

# Initialise Groq client (same API key used for quiz generation)
_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MAX_INPUT_CHARS = 8000  # Groq can handle much more than local BART


def summarize_text(text: str) -> str:
    """
    Summarise the provided text using Groq API (llama3-8b-8192).
    Falls back to truncation if text is very long.
    """
    text = " ".join(text.split())  # clean whitespace

    # Truncate if extremely long to stay within token limits
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]

    print("[summarizer] Calling Groq API for summarisation …")

    response = _client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert academic summariser. "
                    "Create clear, concise summaries that capture all key concepts, "
                    "definitions, and important points from the text."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Please summarise the following text in 150-250 words. "
                    f"Focus on the main concepts, key facts, and important details "
                    f"that would be useful for generating quiz questions.\n\n"
                    f"TEXT:\n{text}"
                )
            }
        ],
        temperature=0.3,   # low temperature = consistent, factual summary
        max_tokens=500,
    )

    summary = response.choices[0].message.content.strip()
    print(f"[summarizer] Summary generated ({len(summary)} chars).")
    return summary