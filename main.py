import os
import json
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from google import genai

app = FastAPI(title="Reimfabrik Studio")

# Gemini Client initialisieren (liest Umgebungsvariable auf Render)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


# 1. Wortsuche: Reine Reime, Slant-Rhymes und mehrsilbige Paare
@app.get("/api/rhyme")
def get_rhymes(word: str = Query(..., min_length=1), lang: str = "de"):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "categories": {}}

    prompt = f"""
Du bist ein poetisches Reimlexikon für Songwriter und Texter.
Finde inspirierende, klangvolle Reime zum Wort: "{word}".

Gib das Ergebnis ausschließlich als valides JSON in exakt dieser Struktur aus:
{{
  "exact": ["Wort1", "Wort2", "Wort3", "Wort4", "Wort5"],
  "near": ["Wort1", "Wort2", "Wort3", "Wort4", "Wort5"],
  "multisyllable": ["Wortpaar 1", "Wortpaar 2", "Wortpaar 3"]
}}

Kategorien:
- exact: Reiner Vollreim (gleicher Vokal und Endkonsonanten).
- near: Weicher Klangreim / Assonanz / Slant Rhyme (gleicher Vokal, ähnlicher Klang).
- multisyllable: Mehrsilbige Reime oder Doppelreim-Verbindungen.
"""
    try:
        response = ai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        data = json.loads(response.text)
        return {"word": word, "categories": data}
    except Exception as e:
        print(f"Fehler bei /api/rhyme: {e}")
        return {
            "error": str(e),
            "categories": {"exact": [], "near": [], "multisyllable": []},
        }


# 2. Zeilen-Kontext: Thematische Reimwörter und rhythmische Impulszeilen
@app.get("/api/rhyme-line")
def get_line_inspiration(line: str = Query(..., min_length=3), lang: str = "de"):
    if not ai_client:
        return {"error": "API-Schlüssel fehlt.", "words": [], "lines": []}

    prompt = f"""
Ein Songwriter hat folgende Zeile geschrieben:
"{line}"

Analysiere Rhythmus, Stimmung und das Endwort dieser Zeile.
Gib das Ergebnis ausschließlich als valides JSON in exakt dieser Struktur aus:
{{
  "context_rhymes": ["Wort1", "Wort2", "Wort3", "Wort4", "Wort5", "Wort6"],
  "suggested_lines": [
    "Vorschlag für eine rhythmisch passende Folgezeile 1",
    "Vorschlag für eine rhythmisch passende Folgezeile 2"
  ]
}}
"""
    try:
        response = ai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        data = json.loads(response.text)
        return {
            "line": line,
            "words": data.get("context_rhymes", []),
            "lines": data.get("suggested_lines", []),
        }
    except Exception as e:
        print(f"Fehler bei /api/rhyme-line: {e}")
        return {"error": str(e), "words": [], "lines": []}


# 3. Statische Dateien (Frontend) als allerletztes ausliefern
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")