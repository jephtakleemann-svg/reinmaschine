import os
import json
import re
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
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
    Kategorisiere streng in:
    "exact" (reine Reime),
    "near" (unreine Reime/Assonanzen),
    "multisyllable" (mehrsilbige Reime).

    Gib NUR folgendes JSON-Format zurück:
    {{
      "exact": ["Wort1", "Wort2"],
      "near": ["Wort1", "Wort2"],
      "multisyllable": ["Wort1", "Wort2"]
    }}
    """
    try:
        # Hier ist das korrekte Modell 3.6 eingetragen
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
    theme: str = Query("Geburtstag"),
    poem_style: str = Query("Klassisches Gedicht"),
    details: Optional[str] = Query(None),
    keywords: Optional[str] = Query(None),
    first_line: Optional[str] = Query(None),
    lines_count: int = Query(8),
    lang: str = Query("de")
):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "result": None}

    language_name = LANG_NAMES.get(lang.lower(), "Deutsch")

    prompt = f"""
    Du bist Songwriter und Lyriker in {language_name}.
    Erstelle ein lyrisches Werk (Gedicht oder Song) passend zu:
    - Thema: {theme}
    - Form/Stil: {poem_style}
    - Länge/Umfang: Ungefähr {lines_count} Zeilen insgesamt (außer bei festen Formen wie Haiku/Elfchen).
    - Details: {details or 'Allgemein passend'}
    - Pflichtwörter: {keywords or 'Keine'}
    """
    if first_line:
        prompt += f"\n- Die allererste Textzeile MUSS exakt so lauten: '{first_line}'."

    prompt += """
    WICHTIG: Antworte AUSSCHLIESSLICH als valides JSON-Objekt in exakt dieser Struktur:
    {
      "hookline": "Eine Hookline oder ein Titel (nur wenn 'Song' als Stil gewählt wurde, sonst leer lassen)",
      "verses": [
        ["Zeile 1", "Zeile 2", "Zeile 3", "Zeile 4"], 
        ["Strophe 2 Zeile 1", "Strophe 2 Zeile 2", "Strophe 2 Zeile 3", "Strophe 2 Zeile 4"]
      ],
      "chorus": [
        "Refrain Zeile 1", "Refrain Zeile 2"
      ]
    }
    Hinweis: Wenn ein normales Gedicht (Paarreim, Haiku etc.) gefordert ist, lass 'chorus' und 'hookline' einfach weg oder mach sie leer und fülle nur das 'verses'-Array mit den Strophen.
    """

    try:
        # Hier ist das korrekte Modell 3.6 eingetragen
        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = extract_json_data(response.text)
        
        # Falls die KI aus Versehen nur ein flaches Array liefert (Fallback)
        if isinstance(data, list):
            data = {"hookline": "", "verses": [data], "chorus": []}

        if data and ("verses" in data or "chorus" in data):
            return {"theme": theme, "result": data}
        return {"error": "Konnte kein valides Format erzeugen.", "result": None}
    except Exception as e:
        return {"error": f"Serverfehler: {str(e)}", "result": None}

app.mount("/", StaticFiles(directory="static", html=True), name="static")