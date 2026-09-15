import os
import json
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from google import genai

app = FastAPI()

# 1. Gemini KI initialisieren (API-Key über Umgebungsvariable)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

LANG_NAMES = {
    "de": "Deutsch",
    "en": "Englisch",
    "es": "Spanisch",
    "fr": "Französisch"
}

def clean_json_response(raw_text: str) -> str:
    """Entfernt eventuelle Markdown-Codeblöcke aus der KI-Antwort."""
    text = (raw_text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text

# 2. Endpunkt: Einzelne Reimwörter finden (phonetisch sortiert)
@app.get("/api/rhyme")
def find_rhymes(
    word: str = Query(..., min_length=1),
    lang: str = Query("de")
):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt. Bitte trage GEMINI_API_KEY ein.", "categories": {}}

    language_name = LANG_NAMES.get(lang.lower(), "Deutsch")

    prompt = f"""
    Du bist ein phonetisches Reimlexikon für Lyrik, Gedichte und Songwriting in der Sprache: {language_name}.
    Finde hochwertige, treffende Reime auf das Wort: '{word}'.

    Unterteile die Treffer streng in 3 Kategorien:
    1. "exact": Exakte/reine Reime (Endkonsonanten und Vokal klingen gleich).
    2. "near": Unreine Reime / Assonanzen / Halbreime (klingen ähnlich, ideal für moderne Songs).
    3. "multisyllable": Mehrsilbige Reime / Doppelreime (mindestens 2 Silben reimen sich).

    Regeln:
    - Alle Reime müssen in der Sprache {language_name} sein.
    - Gib NUR ein valides JSON-Objekt ohne Erklärungen oder Markdown zurück.
    Format:
    {{
      "exact": ["Wort1", "Wort2", ...],
      "near": ["Wort1", "Wort2", ...],
      "multisyllable": ["Wort1", "Wort2", ...]
    }}
    Maximal 10 Wörter pro Kategorie.
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        json_str = clean_json_response(response.text)
        data = json.loads(json_str)
        return {"word": word, "lang": language_name, "categories": data}
    except Exception:
        return {
            "error": "Fehler beim Finden von Reimen.",
            "categories": {"exact": [], "near": [], "multisyllable": []}
        }

# 3. Endpunkt: Ganze Folgezeile dichten (Songwriting-Feature mit Füllwörtern)
@app.get("/api/generate-line")
def generate_rhyme_line(
    first_line: str = Query(..., min_length=2),
    keywords: Optional[str] = Query(None),
    lang: str = Query("de")
):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "lines": []}

    language_name = LANG_NAMES.get(lang.lower(), "Deutsch")

    prompt = f"""
    Du bist ein erfahrener Songwriter und Dichter in der Sprache: {language_name}.
    Der Nutzer hat folgende erste Zeile geschrieben:
    "{first_line}"

    Deine Aufgabe:
    Generiere 4 passende Folgezeilen, die sich sauber auf das letzte Wort der ersten Zeile reimen.
    Achte darauf, dass Versmaß, Rhythmus und Silbenzahl harmonisch zur ersten Zeile passen.
    """

    if keywords:
        prompt += f"\nIntegriere nach Möglichkeit folgende Wörter/Ideen: '{keywords}'."

    prompt += """
    Gib NUR ein valides JSON-Array mit genau 4 Strings zurück.
    Format:
    ["Zeile 1", "Zeile 2", "Zeile 3", "Zeile 4"]
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        json_str = clean_json_response(response.text)
        lines = json.loads(json_str)
        return {"first_line": first_line, "lines": lines}
    except Exception:
        return {"error": "Zeilengenerierung fehlgeschlagen.", "lines": []}

# 4. Statische HTML-Dateien ausliefern
app.mount("/", StaticFiles(directory="static", html=True), name="static")