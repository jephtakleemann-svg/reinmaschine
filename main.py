import os
import json
import re
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types

app = FastAPI()

# Gemini API initialisieren
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

LANG_NAMES = {
    "de": "Deutsch",
    "en": "Englisch",
    "es": "Spanisch",
    "fr": "Französisch"
}

def extract_json_data(text: str):
    """Extrahiert zuverlässig das JSON, falls die KI noch Text darum herum baut."""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned.strip())
    except Exception:
        match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return None

# 1. API: Einzelne Reimwörter finden
@app.get("/api/rhyme")
def find_rhymes(word: str = Query(..., min_length=1), lang: str = Query("de")):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "categories": {}}

    language_name = LANG_NAMES.get(lang.lower(), "Deutsch")
    prompt = f"""
    Finde hochwertige Reime auf das Wort '{word}' in der Sprache: {language_name}.
    Kategorisiere in:
    "exact" (reine Reime),
    "near" (unreine Reime/Assonanzen),
    "multisyllable" (mehrsilbige Reime).

    Gib NUR folgendes JSON zurück:
    {{
      "exact": ["Wort1", "Wort2"],
      "near": ["Wort1", "Wort2"],
      "multisyllable": ["Wort1", "Wort2"]
    }}
    Maximal 10 Wörter je Kategorie.
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = extract_json_data(response.text)
        if not data:
            data = {"exact": [], "near": [], "multisyllable": []}
        return {"word": word, "lang": language_name, "categories": data}
    except Exception as e:
        return {"error": str(e), "categories": {"exact": [], "near": [], "multisyllable": []}}

# 2. API: Gedichte & literarische Formen generieren
@app.get("/api/generate-poem")
def generate_poem(
    theme: str = Query("Geburtstag"),
    poem_style: str = Query("Klassischer Paarreim"),
    details: Optional[str] = Query(None),
    keywords: Optional[str] = Query(None),
    first_line: Optional[str] = Query(None),
    lines_count: int = Query(4),
    lang: str = Query("de")
):
    if not ai_client:
        return {"error": "API-Schlüssel nicht hinterlegt.", "poem_lines": []}

    language_name = LANG_NAMES.get(lang.lower(), "Deutsch")

    prompt = f"""
    Du bist ein Meister der Lyrik. Schreibe ein Gedicht in der Sprache: {language_name}.
    Thema: {theme}.
    Details: {details or 'Allgemein passend'}.
    Pflichtwörter: {keywords or 'Keine'}.
    Gewünschter Stil/Form: {poem_style}.
    """
    
    if first_line:
        prompt += f"\nDie erste Zeile MUSS lauten: '{first_line}'. Führe das Gedicht ab der zweiten Zeile passend fort."

    prompt += f"""
    Länge: Die Zielvorgabe ist {lines_count} Zeilen. WICHTIG: Wenn eine feste Form (wie Haiku mit exakt 3 Zeilen oder Elfchen mit exakt 5 Zeilen) gewählt wurde, ignoriere die Zielvorgabe und nutze strikt die korrekte Zeilenzahl und Silben-/Wortregel der gewählten Form!

    Antworte AUSSCHLIESSLICH als ein valides JSON-Array von Strings (eine Zeile pro String).
    Beispiel:
    ["Zeile 1", "Zeile 2", "Zeile 3"]
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = extract_json_data(response.text)

        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    data = val
                    break

        if isinstance(data, list) and len(data) > 0:
            return {"theme": theme, "poem_lines": [str(x) for x in data]}
        else:
            return {"error": "Formatfehler bei der Generierung", "poem_lines": []}
    except Exception as e:
        return {"error": f"Serverfehler: {str(e)}", "poem_lines": []}

# Statische Dateien mounten (Garantiert fehlerfrei)
app.mount("/", StaticFiles(directory="static", html=True), name="static")