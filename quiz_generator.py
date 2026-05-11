"""
quiz_generator.py - Quiz Generation Module
Uses the Groq API to generate 10 MCQ questions from a summary.
"""

import os
import json
import re
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

QUIZ_PROMPT_TEMPLATE = """Create exactly 10 multiple choice questions based on this text.

CRITICAL: Return ONLY a JSON array. No markdown. No code blocks. No explanations.
Start with [ and end with ]

Each question must be a JSON object with EXACTLY these fields:
- "question": string with the question text
- "options": object with keys "A", "B", "C", "D" (each is a string)
- "correct_answer": single letter "A" or "B" or "C" or "D"

Example format (10 items):
[{{"question": "What is...", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct_answer": "C"}}, ...]

TEXT:
{summary}"""


def generate_quiz(summary: str) -> list:
    """Call Groq API and return list of 10 MCQ question dicts."""

    print("[quiz_generator] Calling Groq API …")

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": QUIZ_PROMPT_TEMPLATE.format(summary=summary)
            }
        ],
        temperature=0.7,
        max_tokens=4000,  # Increased from 3000
    )

    raw = response.choices[0].message.content.strip()

    # ── DEBUG: print exactly what came back ──────────────────
    print("=" * 60)
    print("[quiz_generator] RAW RESPONSE FROM GROQ:")
    print(raw[:1500])
    print("=" * 60)

    questions = _parse_quiz_response(raw)
    print(f"[quiz_generator] Parsed {len(questions)} question(s).")
    return questions


def _parse_quiz_response(raw: str) -> list:
    """Robustly parse JSON from Groq response with aggressive cleaning."""

    print(f"[DEBUG] Raw response length: {len(raw)} chars")
    print(f"[DEBUG] First 500 chars: {raw[:500]}")

    # Step 1: strip markdown fences and extra whitespace
    raw = re.sub(r"```json", "", raw)
    raw = re.sub(r"```",     "", raw)
    raw = raw.strip()

    # Step 2: extract the JSON array between first [ and last ]
    start = raw.find("[")
    end   = raw.rfind("]")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            f"No JSON array found in response. Searched in:\n{raw[:500]}"
        )

    raw = raw[start : end + 1]
    print(f"[DEBUG] Extracted JSON array of {len(raw)} chars")

    # Step 3: Aggressive JSON cleaning
    # Remove escaped quotes that shouldn't be there (but preserve \" within strings is tricky)
    # First: normalize escaped quotes more carefully
    
    # Fix common Groq output issues:
    # 1. Clean up double-escaped quotes
    raw = raw.replace('\\"', '"')  # Convert \" to "
    raw = raw.replace("\\'", "'")  # Convert \' to '
    
    # 2. Fix common issues
    raw = re.sub(r",\s*]", "]", raw)           # Remove trailing commas before ]
    raw = re.sub(r",\s*}", "}", raw)           # Remove trailing commas before }
    raw = re.sub(r':\s*None', ': null', raw)   # Python None to JSON null
    raw = re.sub(r':\s*True', ': true', raw)   # Python True to JSON true
    raw = re.sub(r':\s*False', ': false', raw) # Python False to JSON false
    
    # 3. Remove stray text between commas and quotes/braces (like "or", "and")
    raw = re.sub(r',\s+(or|and|but)\s+', ', ', raw)
    
    # 4. Fix property names without quotes (but be careful with regex)
    # Match: comma, optional whitespace, word characters, colon
    raw = re.sub(r',\s*([a-zA-Z_][a-zA-Z0-9_]*):', r', "\1":', raw)

    print(f"[DEBUG] After cleaning: {raw[:300]}")

    # Step 4: parse
    try:
        questions = json.loads(raw)
        print(f"[SUCCESS] JSON parsed successfully")
    except json.JSONDecodeError as exc:
        print(f"[ERROR] JSON parse failed: {exc}")
        print(f"[ERROR] Error location around char {exc.pos}: ...{raw[max(0,exc.pos-50):exc.pos+50]}...")
        
        # Try recovery strategy 1: remove incomplete last item
        if raw.count("{") > raw.count("}"):
            last_complete = raw.rfind("},")
            if last_complete > 0:
                raw = raw[:last_complete+1] + "]"
                print(f"[INFO] Attempting recovery by truncating incomplete question")
                try:
                    questions = json.loads(raw)
                    print(f"[SUCCESS] Recovery worked!")
                except json.JSONDecodeError as exc2:
                    pass  # continue to next recovery attempt
        
        # Try recovery strategy 2: remove trailing incomplete object entirely
        if isinstance(questions, type(None)):
            bracket_idx = raw.rfind("}")
            if bracket_idx > 0:
                # Find the last complete object before current position
                depth = 0
                for i in range(bracket_idx, -1, -1):
                    if raw[i] == "}":
                        depth += 1
                    elif raw[i] == "{":
                        depth -= 1
                        if depth == 0:
                            # Found start of last complete object, but remove it
                            prev_comma = raw.rfind(",", 0, i)
                            if prev_comma > 0:
                                raw = raw[:prev_comma] + "]"
                                print(f"[INFO] Attempting recovery by removing last object")
                                try:
                                    questions = json.loads(raw)
                                    print(f"[SUCCESS] Recovery 2 worked!")
                                except json.JSONDecodeError:
                                    pass
                            break
        
        # If still failed, raise
        if isinstance(questions, type(None)):
            raise ValueError(
                f"JSON recovery failed: {exc}\nTried: {raw[-100:]}"
            ) from exc

    # Step 5: unwrap if needed
    if isinstance(questions, dict):
        for value in questions.values():
            if isinstance(value, list):
                questions = value
                break

    if not isinstance(questions, list):
        raise ValueError(f"Expected list, got {type(questions).__name__}: {questions}")
    
    if len(questions) == 0:
        raise ValueError("Questions list is empty")

    print(f"[DEBUG] Processing {len(questions)} questions")

    # Step 6: validate each question
    validated = []
    for idx, item in enumerate(questions):
        try:
            if not isinstance(item, dict):
                print(f"[SKIP] Q{idx}: not a dict (is {type(item).__name__})")
                continue
            
            q_text = item.get("question", "").strip()
            opts = item.get("options", {})
            ans = str(item.get("correct_answer", "")).upper().strip()
            
            if not q_text:
                print(f"[SKIP] Q{idx}: empty question text")
                continue
            
            if not isinstance(opts, dict) or len(opts) != 4:
                print(f"[SKIP] Q{idx}: options invalid (got {len(opts) if isinstance(opts, dict) else 'not-dict'})")
                continue
            
            if ans not in ["A", "B", "C", "D"]:
                print(f"[SKIP] Q{idx}: bad answer '{ans}'")
                continue
            
            # Valid question
            validated.append({
                "question": q_text,
                "options": {k: str(v).strip() for k, v in opts.items()},
                "correct_answer": ans,
                "type": "mcq"
            })
            print(f"[OK] Q{idx}: '{q_text[:40]}...'")
            
        except Exception as e:
            print(f"[ERROR] Q{idx}: {e}")
            continue

    if len(validated) == 0:
        # Debug: show structure of first question
        if questions and isinstance(questions[0], dict):
            print(f"\n[DEBUG] First question keys: {list(questions[0].keys())}")
            print(f"[DEBUG] First question: {questions[0]}\n")
        
        raise ValueError(
            f"No valid questions. Processed {len(questions)} items, validated 0."
        )

    print(f"\n[SUCCESS] Final: {len(validated)}/{len(questions)} questions validated\n")
    return validated