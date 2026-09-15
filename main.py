import os
import json
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from google import genai

app = FastAPI()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

LANG_NAMES = {
    "de": "Deutsch",
    "en": "Englisch",
    "es": "Spanisch",
    "fr": "Französisch"
}

def clean_json_response(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text

# 1. Einzelne Reimwörter
@app.get("/api/rhyme")
def find_rhymes(word: str = Query(..., min_length=1), lang: str = Query("de")):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "categories": {}}

    language_name = LANG_NAMES.get(lang.lower(), "Deutsch")

    prompt = f"""
    Du bist ein phonetisches Reimlexikon für die Sprache: {language_name}.
    Finde Reime auf das Wort: '{word}'.
    Kategorisiere streng in:
    1. "exact": Exakte/reine Reime.
    2. "near": Unreine Reime / Halbreime / Assonanzen.
    3. "multisyllable": Mehrsilbige Reime / Doppelreime.

    Antworte NUR mit validem JSON:
    {{
      "exact": ["Wort1", "Wort2"],
      "near": ["Wort1", "Wort2"],
      "multisyllable": ["Wort1", "Wort2"]
    }}
    """
    try:
        res = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        data = json.loads(clean_json_response(res.text))
        return {"word": word, "lang": language_name, "categories": data}
    except Exception:
        return {"error": "Fehler beim Abrufen der Reime.", "categories": {"exact": [], "near": [], "multisyllable": []}}

# 2. Der neue Gedicht- & Songtext-Konfigurator
@app.get("/api/generate-poem")
def generate_poem(
    theme: str = Query("Geburtstag"),
    details: Optional[str] = Query(None),
    keywords: Optional[str] = Query(None),
    first_line: Optional[str] = Query(None),
    lines_count: int = Query(4),
    lang: str = Query("de")
):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "poem_lines": []}

    language_name = LANG_NAMES.get(lang.lower(), "Deutsch")

    prompt = f"""
    Du bist ein professioneller Dichter, Lyriker und Songwriter in der Sprache: {language_name}.
    Schreibe ein wohlklingendes, rhythmisches Gedicht oder einen Liedvers mit GENAU {lines_count} Zeilen.

    Rahmenbedingungen:
    - Anlass / Thema: {theme}
    - Hintergrund-Details / Person: {details if details else "Keine spezifischen Details, passe es allgemein zum Thema an"}
    - Wörter, die unbedingt vorkommen müssen: {keywords if keywords else "Keine vorgegebenen Pflichtwörter"}
    """

    if first_line:
        prompt += f"""
    - Der Vers MUSS mit genau dieser ersten Zeile beginnen:
      "{first_line}"
    - Alle folgenden Zeilen müssen sich inhaltlich, stilistisch und rhythmisch perfekt daran anschließen!
    """

    prompt += f"""
    Wichtige Kriterien:
    - Perfektes Versmaß, flüssiger Lesefluss und saubere Reime (z. B. Paarreim AABB oder Kreuzreim ABAB).
    - Kein holpriger Satzbau, sondern poetisch und treffend.
    - Gib NUR ein valides JSON-Array zurück, das die einzelnen Zeilen als Strings enthält.
    
    Beispiel-Format bei 4 Zeilen:
    ["Zeile 1", "Zeile 2", "Zeile 3", "Zeile 4"]
    """

    try:
        res = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        lines = json.loads(clean_json_response(res.text))
        return {"theme": theme, "poem_lines": lines}
    except Exception:
        return {"error": "Konnte das Gedicht nicht generieren.", "poem_lines": []}

app.mount("/", StaticFiles(directory="static", html=True), name="static")