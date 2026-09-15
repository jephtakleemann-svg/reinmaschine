import os
import json
import re
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types

app = FastAPI()

# 1. Gemini API initialisieren
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

LANG_NAMES = {
    "de": "Deutsch",
    "en": "Englisch",
    "es": "Spanisch",
    "fr": "Französisch"
}

def extract_json_data(text: str):
    """Holt zuverlässig JSON aus der Antwort heraus."""
    if not text:
        return None
    # Entferne Markdown Code-Blöcke
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned.strip())
    except Exception:
        # Fallback: Suche erstes Array oder Objekt per Regex
        match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return None

# 2. Reime finden
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
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        data = extract_json_data(response.text)
        if not data:
            data = {"exact": [], "near": [], "multisyllable": []}
        return {"word": word, "lang": language_name, "categories": data}
    except Exception as e:
        return {"error": str(e), "categories": {"exact": [], "near": [], "multisyllable": []}}

# 3. Gedicht- & Song-Generator
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
        return {"error": "API-Schlüssel nicht hinterlegt.", "poem_lines": []}

    language_name = LANG_NAMES.get(lang.lower(), "Deutsch")

    prompt = f"""
    Schreibe ein wohlklingendes Gedicht mit GENAU {lines_count} Zeilen auf {language_name}.
    Thema: {theme}.
    Details/Person: {details or 'Allgemein passend'}.
    Pflichtwörter: {keywords or 'Keine'}.
    """
    if first_line:
        prompt += f"\nErste Zeile MUSS lauten: '{first_line}'. Reime die Folgezeilen passend darauf."

    prompt += f"""
    WICHTIG: Antworte AUSSCHLIESSLICH als JSON-Array von {lines_count} Zeilen-Strings.
    Beispiel:
    ["Zeile 1", "Zeile 2", "Zeile 3", "Zeile 4"]
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        data = extract_json_data(response.text)

        # Falls ein Dictionary statt Liste geliefert wurde
        if isinstance(data, dict):
            # Nimmt die erste Liste, die im Dictionary vorkommt
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

app.mount("/", StaticFiles(directory="static", html=True), name="static")ml=True), name="static")