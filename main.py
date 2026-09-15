import os
import json
import re
import time
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

def call_gemini(prompt: str):
    # Nutzt primär das von Google verlangte gemini-3.6-flash
    models = ['gemini-3.6-flash', 'gemini-2.5-flash']
    for model_name in models:
        try:
            return ai_client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e):
                time.sleep(1)
                continue
            if "404" in str(e) or "NOT_FOUND" in str(e):
                continue
            raise e
    raise Exception("KI-Dienst momentan überlastet. Bitte gleich nochmal probieren.")

# 1. API: Einzelne Reimwörter
@app.get("/api/rhyme")
def find_rhymes(
    word: str = Query(..., min_length=1),
    theme: Optional[str] = Query(None),
    lang: str = Query("de")
):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "categories": {}}

    language_name = LANG_NAMES.get(lang.lower(), "Deutsch")
    prompt = f"""
    Finde hochwertige Reime auf das Wort '{word}' in der Sprache: {language_name}.
    Kategorisiere in: "exact", "near", "multisyllable".
    """
    if theme:
        prompt += f"\nKontext/Thema: {theme}."

    prompt += """
    Gib NUR folgendes JSON zurück:
    {
      "exact": ["Wort1", "Wort2"],
      "near": ["Wort1", "Wort2"],
      "multisyllable": ["Wort1", "Wort2"]
    }
    Maximal 10 Wörter je Kategorie.
    """
    try:
        response = call_gemini(prompt)
        data = extract_json_data(response.text)
        return {"word": word, "lang": language_name, "categories": data or {}}
    except Exception as e:
        return {"error": str(e), "categories": {"exact": [], "near": [], "multisyllable": []}}

# 2. API: Gedicht
@app.get("/api/generate-poem")
def generate_poem(
    theme: str = Query("Geburtstag"),
    poem_style: str = Query("Klassischer Paarreim (AABB)"),
    details: Optional[str] = Query(None),
    keywords: Optional[str] = Query(None),
    exclude_words: Optional[str] = Query(None),
    lines_count: int = Query(4),
    lang: str = Query("de")
):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "poem_lines": []}

    language_name = LANG_NAMES.get(lang.lower(), "Deutsch")

    prompt = f"""
    Schreibe ein Gedicht in {language_name}.
    Thema: {theme}
    Gedichtform: {poem_style}
    Details: {details or 'Allgemein passend'}
    Pflichtwörter: {keywords or 'Keine'}
    """
    if exclude_words:
        prompt += f"\nTabus (Nicht verwenden): {exclude_words}"

    prompt += f"""
    Länge: {lines_count} Zeilen. (Bei Haiku/Elfchen feste Formregeln beachten).
    Antworte AUSSCHLIESSLICH als JSON-Array von Strings:
    ["Zeile 1", "Zeile 2", "Zeile 3"]
    """

    try:
        response = call_gemini(prompt)
        data = extract_json_data(response.text)
        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    data = val
                    break
        if isinstance(data, list):
            return {"theme": theme, "poem_lines": [str(x) for x in data]}
        return {"error": "Formatfehler", "poem_lines": []}
    except Exception as e:
        return {"error": str(e), "poem_lines": []}

# 3. API: Song-Studio
class SongRequest(BaseModel):
    task: str 
    vibe: str
    existing_text: Optional[str] = None
    details: Optional[str] = None
    keywords: Optional[str] = None
    exclude_words: Optional[str] = None
    lang: Optional[str] = "de"

@app.post("/api/generate-song")
def generate_song(req: SongRequest):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "result": None}

    language_name = LANG_NAMES.get((req.lang or "de").lower(), "Deutsch")

    prompt = f"""
    Du bist ein Songwriter. Schreibe Songtexte strikt in {language_name}.
    Übersetze Eingaben bei Bedarf sinngemäß in die Zielsprache.
    
    Musikalischer Vibe: {req.vibe}
    Aufgabe: {req.task}
    Details / Story: {req.details or 'Frei passend'}
    Pflichtwörter: {req.keywords or 'Keine'}
    """
    if req.exclude_words:
        prompt += f"\nTabus (Darf nicht vorkommen): {req.exclude_words}"
    if req.existing_text:
        prompt += f"\nVorhandener Nutzertext zur Weiterentwicklung:\n\"\"\"{req.existing_text}\"\"\""

    prompt += """
    Antworte AUSSCHLIESSLICH als JSON-Objekt (fülle nur relevante Felder):
    {
      "hookline": "Prägnante Hookline/Slogan",
      "verses": [
        ["Zeile 1", "Zeile 2", "Zeile 3", "Zeile 4"]
      ],
      "chorus": [
        "Zeile 1", "Zeile 2", "Zeile 3", "Zeile 4"
      ],
      "bridge": [
        "Zeile 1", "Zeile 2"
      ]
    }
    """

    try:
        response = call_gemini(prompt)
        data = extract_json_data(response.text)
        return {"result": data}
    except Exception as e:
        return {"error": str(e), "result": None}

# 4. API: Song verfeinern
class RefineRequest(BaseModel):
    current_song: dict
    instruction: str
    exclude_words: Optional[str] = None
    lang: Optional[str] = "de"

@app.post("/api/refine-song")
def refine_song(req: RefineRequest):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "result": None}

    language_name = LANG_NAMES.get((req.lang or "de").lower(), "Deutsch")

    prompt = f"""
    Überarbeite den Songtext in {language_name}.
    Bisheriger Text:
    {json.dumps(req.current_song, ensure_ascii=False)}
    
    Änderungswunsch:
    "{req.instruction}"
    """
    if req.exclude_words:
        prompt += f"\nTabus: {req.exclude_words}"

    prompt += """
    Behalte exakt das JSON-Format bei:
    {
      "hookline": "...",
      "verses": [["..."]],
      "chorus": ["..."],
      "bridge": ["..."]
    }
    """
    try:
        response = call_gemini(prompt)
        data = extract_json_data(response.text)
        return {"result": data}
    except Exception as e:
        return {"error": str(e), "result": None}

app.mount("/", StaticFiles(directory="static", html=True), name="static")