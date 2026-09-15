import os
import json
import re
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai
from google.genai import types

app = FastAPI()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

LANG_NAMES = {
    "de": "Deutsch",
    "en": "Englisch",
    "es": "Spanisch",
    "fr": "Französisch"
}

def extract_json_data(text: str):
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned.strip())
    except Exception:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return None

@app.get("/api/rhyme")
def find_rhymes(word: str = Query(..., min_length=1), lang: str = Query("de")):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "categories": {}}

    language_name = LANG_NAMES.get(lang.lower(), "Deutsch")
    prompt = f"""
    Finde hochwertige Reime auf das Wort '{word}' in der Sprache: {language_name}.
    Kategorisiere in: "exact", "near", "multisyllable".
    Gib NUR folgendes JSON zurück:
    {{
      "exact": ["Wort1", "Wort2"],
      "near": ["Wort1", "Wort2"],
      "multisyllable": ["Wort1", "Wort2"]
    }}
    """
    try:
        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = extract_json_data(response.text)
        return {"word": word, "lang": language_name, "categories": data or {}}
    except Exception as e:
        return {"error": str(e), "categories": {"exact": [], "near": [], "multisyllable": []}}

@app.get("/api/generate-poem")
def generate_poem(
    theme: str = Query("Freies Thema"),
    poem_style: str = Query("Songtext (Strophen + Refrain + Hook)"),
    details: Optional[str] = Query(None),
    keywords: Optional[str] = Query(None),
    exclude_words: Optional[str] = Query(None),
    first_line: Optional[str] = Query(None),
    lines_count: int = Query(8),
    lang: str = Query("de")
):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "result": None}

    language_name = LANG_NAMES.get(lang.lower(), "Deutsch")

    prompt = f"""
    Du bist Songwriter und Lyriker in {language_name}.
    Erstelle ein stimmiges Werk:
    - Thema/Vibe: {theme}
    - Form/Stil: {poem_style}
    - Hintergrund/Details: {details or 'Frei passend'}
    - Pflichtwörter: {keywords or 'Keine'}
    """
    if exclude_words:
        prompt += f"\n- TABUS / VERBOTEN (DARF NICHT VORKOMMEN): {exclude_words}. Verwende keine dieser Wörter oder Motive!"
    if first_line:
        prompt += f"\n- Erste Zeile MUSS lauten: '{first_line}'."

    prompt += """
    Antworte AUSSCHLIESSLICH als valides JSON-Objekt:
    {
      "hookline": "Prägnante Hookline/Slogan",
      "verses": [
        ["Zeile 1", "Zeile 2", "Zeile 3", "Zeile 4"],
        ["Zeile 1", "Zeile 2", "Zeile 3", "Zeile 4"]
      ],
      "chorus": [
        "Zeile 1", "Zeile 2", "Zeile 3", "Zeile 4"
      ]
    }
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = extract_json_data(response.text)
        return {"theme": theme, "result": data}
    except Exception as e:
        return {"error": f"Serverfehler: {str(e)}", "result": None}

class RefineRequest(BaseModel):
    current_song: dict
    instruction: str
    exclude_words: Optional[str] = None
    lang: Optional[str] = "de"

@app.post("/api/refine-poem")
def refine_poem(req: RefineRequest):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "result": None}

    language_name = LANG_NAMES.get(req.lang.lower(), "Deutsch")

    prompt = f"""
    Du bist Songwriter in {language_name}.
    Überarbeite den folgenden bestehenden Text anhand des Nutzerfeedbacks.
    
    Aktueller Stand:
    {json.dumps(req.current_song, ensure_ascii=False)}
    
    Änderungswunsch des Nutzers:
    "{req.instruction}"
    """
    if req.exclude_words:
        prompt += f"\nZUSÄTZLICHE TABUS (Darf keinesfalls vorkommen): {req.exclude_words}"

    prompt += """
    Behalte die JSON-Struktur exakt bei:
    {
      "hookline": "...",
      "verses": [["..."]],
      "chorus": ["..."]
    }
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = extract_json_data(response.text)
        return {"result": data}
    except Exception as e:
        return {"error": f"Serverfehler: {str(e)}", "result": None}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
