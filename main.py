import json
import os
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types

app = FastAPI(title="Reimfabrik Studio")

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
ai_client = genai.Client(api_key=API_KEY) if API_KEY else None

# Exakt das von Google geforderte Modell
MODEL_NAME = "gemini-2.0-flash"


def parse_ai_json(raw_text: str):
    """Bereinigt eventuelle Markdown-Fences, damit json.loads nie scheitert."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


@app.get("/api/rhyme")
def get_rhymes(word: str = Query(..., min_length=1), lang: str = "de"):
    if not ai_client:
        return {
            "error": "API-Schlüssel fehlt in Render.",
            "categories": {
                "exact": ["Fehler: Kein API-Key hinterlegt"],
                "near": [],
                "multisyllable": [],
            },
        }

    prompt = f"""
Du bist ein poetisches Reimlexikon für Songwriter.
Finde Reime zum Wort: "{word}".
Gib das Ergebnis ausschließlich als valides JSON in dieser Struktur aus:
{{
  "exact": ["Wort1", "Wort2", "Wort3", "Wort4"],
  "near": ["Wort1", "Wort2", "Wort3", "Wort4"],
  "multisyllable": ["Wortpaar 1", "Wortpaar 2"]
}}
"""
    try:
        response = ai_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )
        data = parse_ai_json(response.text)
        return {"word": word, "categories": data}
    except Exception as e:
        print(f"Fehler bei /api/rhyme: {e}")
        return {
            "error": str(e),
            "categories": {
                "exact": [f"Fehler: {str(e)}"],
                "near": [],
                "multisyllable": [],
            },
        }


@app.get("/api/rhyme-line")
def get_line_inspiration(line: str = Query(..., min_length=3), lang: str = "de"):
    if not ai_client:
        return {
            "error": "API-Schlüssel fehlt in Render.",
            "words": ["Fehler: Kein API-Key"],
            "lines": [],
        }

    prompt = f"""
Ein Songwriter schreibt folgende Zeile(n):
"{line}"
Analysiere Rhythmus, Versmaß, Tonfall und Endreim.
Gib das Ergebnis ausschließlich als valides JSON in dieser Struktur aus:
{{
  "context_rhymes": ["Wort1", "Wort2", "Wort3", "Wort4"],
  "suggested_lines": ["Passende Folgezeile 1", "Passende Folgezeile 2"]
}}
"""
    try:
        response = ai_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )
        data = parse_ai_json(response.text)
        return {
            "line": line,
            "words": data.get("context_rhymes", []),
            "lines": data.get("suggested_lines", []),
        }
    except Exception as e:
        print(f"Fehler bei /api/rhyme-line: {e}")
        return {"error": str(e), "words": [f"Fehler: {str(e)}"], "lines": []}


if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")