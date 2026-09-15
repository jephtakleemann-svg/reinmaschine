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

# 1. API: Einzelne Reimwörter mit optionalem Thema
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
        prompt += f"\nBevorzuge Wörter, die thematisch zu '{theme}' passen oder eine poetische Verbindung dazu haben."

    prompt += """
    Gib NUR folgendes JSON-Format zurück:
    {
      "exact": ["Wort1", "Wort2"],
      "near": ["Wort1", "Wort2"],
      "multisyllable": ["Wort1", "Wort2"]
    }
    Maximal 10 Wörter je Kategorie.
    """
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = extract_json_data(response.text)
        return {"word": word, "lang": language_name, "categories": data or {}}
    except Exception as e:
        return {"error": str(e), "categories": {"exact": [], "near": [], "multisyllable": []}}

# 2. API: Klassisches Gedicht
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
    Du bist ein Meister der Lyrik. Schreibe ein Gedicht in der Sprache: {language_name}.
    Thema: {theme}
    Gedichtform: {poem_style}
    Details: {details or 'Allgemein passend'}
    Pflichtwörter: {keywords or 'Keine'}
    """
    if exclude_words:
        prompt += f"\nVERBOTENE WÖRTER/THEMEN (Darf absolut nicht vorkommen): {exclude_words}"

    prompt += f"""
    Länge: {lines_count} Zeilen. (Bei festen Formen wie Haiku oder Elfchen halte strikt deren feste Zeilen- und Silbenstruktur ein).
    Antworte AUSSCHLIESSLICH als valides JSON-Array von Strings:
    ["Zeile 1", "Zeile 2", "Zeile 3"]
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
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
        return {"error": f"Serverfehler: {str(e)}", "poem_lines": []}

# 3. API: Song-Studio (Modular)
class SongRequest(BaseModel):
    task: str  # full_song, hook_only, verses_from_hook, bridge_only, chorus_only
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
    Du bist ein erfahrener Songwriter. Schreibe Songtexte strikt in {language_name}.
    Übersetze Gedanken bei Bedarf ins {language_name}e.
    
    Musikalischer Vibe: {req.vibe}
    Aufgabe: {req.task}
    Details / Story: {req.details or 'Frei passend'}
    Pflichtwörter: {req.keywords or 'Keine'}
    """
    if req.exclude_words:
        prompt += f"\nTABUS (Nicht verwenden): {req.exclude_words}"
    if req.existing_text:
        prompt += f"\nBereits existierendes Textmaterial des Nutzers:\n\"\"\"{req.existing_text}\"\"\"\nBaue darauf auf oder ergänze es passend zur Aufgabe!"

    prompt += """
    Antworte AUSSCHLIESSLICH als JSON-Objekt in dieser Struktur (fülle nur die Felder, die zur Aufgabe passen):
    {
      "hookline": "Prägnante Hookline/Slogan (oder leer lassen)",
      "verses": [
        ["Zeile 1", "Zeile 2", "Zeile 3", "Zeile 4"]
      ],
      "chorus": [
        "Zeile 1", "Zeile 2", "Zeile 3", "Zeile 4"
      ],
      "bridge": [
        "Zeile 1 Bridge", "Zeile 2 Bridge"
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
        return {"result": data}
    except Exception as e:
        return {"error": f"Serverfehler: {str(e)}", "result": None}

# 4. API: Song interaktiv verfeinern
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
    Du bist Songwriter. Überarbeite den bestehenden Text auf {language_name}.
    Aktueller Stand:
    {json.dumps(req.current_song, ensure_ascii=False)}
    
    Änderungswunsch:
    "{req.instruction}"
    """
    if req.exclude_words:
        prompt += f"\nTabus: {req.exclude_words}"

    prompt += """
    Behalte die JSON-Struktur exakt bei:
    {
      "hookline": "...",
      "verses": [["..."]],
      "chorus": ["..."],
      "bridge": ["..."]
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
