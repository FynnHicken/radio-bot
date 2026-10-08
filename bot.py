import os
import sys
import time
import random
import base64
import json
import asyncio
import logging
import requests
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

BERLIN_TZ = ZoneInfo("Europe/Berlin")

def now_berlin() -> datetime:
    return datetime.now(BERLIN_TZ)

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# ==========================================
# KONFIGURATION & CREDENTIALS
# ==========================================
GEMINI_KEY = os.environ.get("GEMINI_KEY", "")
AZURA_KEY = os.environ.get("AZURA_KEY", "")
AZURA_URL = os.environ.get("AZURA_URL", "http://localhost:8090/api")
STATION_ID = os.environ.get("STATION_ID", "1")
WEB_PORT = int(os.environ.get("PORT", "8055"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("radio-bot")

# ==========================================
# MODERATOREN-VERWALTUNG & STIMMEN
# ==========================================
AVAILABLE_VOICES = [
    {"id": "de-DE-KatjaNeural", "name": "Katja (Weiblich, natürlich & klar)", "gender": "Female"},
    {"id": "de-DE-AmalaNeural", "name": "Amala (Weiblich, sanft & freundlich)", "gender": "Female"},
    {"id": "de-DE-SeraphinaMultilingualNeural", "name": "Seraphina (Weiblich, lebendig)", "gender": "Female"},
    {"id": "de-DE-ConradNeural", "name": "Conrad (Männlich, markant & tief)", "gender": "Male"},
    {"id": "de-DE-KillianNeural", "name": "Killian (Männlich, dynamisch & direkt)", "gender": "Male"},
    {"id": "de-DE-FlorianMultilingualNeural", "name": "Florian (Männlich, sympathisch)", "gender": "Male"}
]

# ==========================================
# SENDER-EINSTELLUNGEN & THEME
# ==========================================
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

DEFAULT_SETTINGS = {
    "station_name": "Studio FM",
    "station_frequency": "98.5",
    "station_claim": "Dein Sender. Dein Sound.",
    "station_theme": "Modernes Webradio mit abwechslungsreichem Mix, sympathischen Moderatoren, spannenden Stories und bester Unterhaltung rund um die Uhr.",
    "station_genre": "Rock, Pop, Classic Hits & Alternative",
    "weather_city": "Hamburg",
    "weather_lat": 53.55,
    "weather_lon": 9.99
}

def load_station_settings() -> Dict[str, Any]:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    merged = DEFAULT_SETTINGS.copy()
                    merged.update(data)
                    return merged
        except Exception as e:
            logger.error(f"Fehler beim Laden von settings.json: {e}")
    return DEFAULT_SETTINGS.copy()

def save_station_settings(data: Dict[str, Any]) -> bool:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        state.cached_weather = {}
        state.last_weather_check = 0.0
        return True
    except Exception as e:
        logger.error(f"Fehler beim Speichern von settings.json: {e}")
        return False

def get_station_settings() -> Dict[str, Any]:
    return load_station_settings()

MODERATORS_FILE = os.path.join(os.path.dirname(__file__), "moderators.json")

DEFAULT_PERSONAS = {
    "alice": {
        "id": "alice",
        "name": "Alice",
        "role": "Kult-Chefin & Musik-Liebhaberin",
        "voice": "de-DE-KatjaNeural",
        "avatar": "👩",
        "description": "Lässig, zynisch, mit schwarzem Humor und treue Lokalpatriotin.",
        "enabled": True,
        "active_hours": [0, 24],
        "prompt_persona": (
            "Du bist Alice, die Kult-Chefin und Moderatorin von Studio FM. "
            "Dein Ton: Lässig, zynisch, trocken, mit feinem schwarzem Humor und eine treue Lokalpatriotin. "
            "Du machst scharfe, aber sachliche Spitzen gegen Bürokratiemonster, "
            "hast aber tiefsten Respekt vor den Handwerkern und der arbeitenden Bevölkerung. "
            "Du liebst handgemachte Musik und redest Tacheles."
        )
    },
    "kalle": {
        "id": "kalle",
        "name": "Kalle",
        "role": "Werkstatt-Urgestein & Schrauber",
        "voice": "de-DE-ConradNeural",
        "avatar": "🔧",
        "description": "Urig, norddeutsch, liebt Kaffee, schimpft über Schrauben & reißt Flachwitze.",
        "enabled": True,
        "active_hours": [6, 16],
        "prompt_persona": (
            "Du bist Kalle, der alteingesessene Werkstatt-Schrauber bei Studio FM. "
            "Dein Ton: Urig, norddeutsch ('Moin moin', 'Mensch Kinners'), direkt und kernig. "
            "Du liebst ehrliche Handarbeit, pechschwarzen Filterkaffee und handgemachten Sound. "
            "Du schimpfst liebevoll über modernen Kabelsalat, festgerostete Bolzen und Schreibtisch-Meister. "
            "Du philosophierst gern über Schrauben und WD-40, bist herrlich melancholisch-depressiv "
            "und bringst trockenste Flachwitze, über die sonst keiner lacht."
        )
    },
    "sven": {
        "id": "sven",
        "name": "Sven",
        "role": "Elektronik-Freak & Kaffeepausen-König",
        "voice": "de-DE-KillianNeural",
        "avatar": "⚡",
        "description": "Zickige Platinen, Kaffeejunkie, Harley & Griechenland.",
        "enabled": True,
        "active_hours": [12, 22],
        "prompt_persona": (
            "Du bist Sven, der Elektronik-Kollege bei Studio FM. "
            "Dein Ton: Technisch versiert, verplant, lässig. "
            "Du fluchst über zickige Leitungen und Kupferwürmer. "
            "Du trinkst astronomische Mengen Kaffee, bist Meister im gekonnten Arbeitszeit-Hinauszögern, "
            "zockst heimlich in der Pause PlayStation, fährst eine dröhnende Harley Davidson "
            "und planst gedanklich schon deinen nächsten Griechenland-Urlaub."
        )
    },
    "markus": {
        "id": "markus",
        "name": "Markus",
        "role": "Nachrichtensprecher",
        "voice": "de-DE-ConradNeural",
        "avatar": "📰",
        "description": "Seriös, sachlich, öffentlich-rechtlicher Tonfall zur vollen Stunde.",
        "enabled": True,
        "active_hours": [0, 24],
        "prompt_persona": (
            "Du bist Markus, der Nachrichtensprecher von Studio FM. "
            "Dein Ton: Absolut seriös, sachlich, professionell und wie im klassischen Radio-Rundfunk. "
            "Du präsentierst echte, verlässliche Meldungen sowie knackige Schlagzeilen "
            "aus Deutschland und der Welt."
        )
    }
}

def load_moderators() -> Dict[str, Any]:
    if os.path.exists(MODERATORS_FILE):
        try:
            with open(MODERATORS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
        except Exception as e:
            logger.error(f"Fehler beim Laden von moderators.json: {e}")
    return DEFAULT_PERSONAS.copy()

def save_moderators(data: Dict[str, Any]) -> bool:
    try:
        with open(MODERATORS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Fehler beim Speichern von moderators.json: {e}")
        return False

def get_personas() -> Dict[str, Any]:
    return load_moderators()

def is_moderator_active_at_hour(mod: Dict[str, Any], hour: int) -> bool:
    if not mod.get("enabled", True):
        return False
    active_hours = mod.get("active_hours", [0, 24])
    if len(active_hours) < 2:
        return True
    start, end = active_hours[0], active_hours[1]
    if start == 0 and end >= 24:
        return True
    if start <= end:
        return start <= hour < end
    else:
        # Über Mitternacht hinweg (z. B. 22 bis 6 Uhr)
        return hour >= start or hour < end

def get_active_music_moderators(hour: int) -> List[Dict[str, Any]]:
    mods = get_personas()
    active = [
        m for m in mods.values()
        if m.get("id") != "markus" and is_moderator_active_at_hour(m, hour)
    ]
    if not active:
        active = [m for m in mods.values() if m.get("id") != "markus" and m.get("enabled", True)]
    return active

# ==========================================
# GLOBALER STATUS & BOT-STATUS
# ==========================================
class RadioState:
    def __init__(self):
        self.autopilot_enabled = True
        self.moderation_interval = 5
        self.tracks_since_last_mod = 0
        self.duo_probability = 0.25
        self.persona_mode = "random" # "random", "alice", "kalle", "sven", "duo"
        self.last_played_song = ""
        self.current_song = ""
        self.next_song = ""
        self.now_playing_data: Dict[str, Any] = {}
        self.letzte_nachrichten_stunde = -1
        self.hourly_news_as_moderation = True  # ca. 1x pro Stunde automatisch Nachrichten als Moderation
        self.logs: List[Dict[str, str]] = []
        self.recent_moderations: List[Dict[str, Any]] = []
        self.cached_weather: Dict[str, Any] = {}
        self.last_weather_check = 0.0

    def add_log(self, message: str, level: str = "info"):
        timestamp = now_berlin().strftime("%H:%M:%S")
        entry = {"time": timestamp, "message": message, "level": level}
        self.logs.insert(0, entry)
        if len(self.logs) > 60:
            self.logs.pop()
        logger.info(f"[{level.upper()}] {message}")

    def add_recent_moderation(self, mod: Dict[str, Any]):
        self.recent_moderations.insert(0, mod)
        if len(self.recent_moderations) > 25:
            self.recent_moderations.pop()

state = RadioState()

# ==========================================
# HILFSFUNKTIONEN: WETTER & SCHICHTEN
# ==========================================
def get_station_weather() -> Dict[str, Any]:
    st = get_station_settings()
    city = st.get("weather_city", "Wilhelmshaven")
    lat = st.get("weather_lat", 53.53)
    lon = st.get("weather_lon", 8.11)

    now_ts = time.time()
    if state.cached_weather and (now_ts - state.last_weather_check < 900):
        return state.cached_weather

    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code,wind_speed_10m&timezone=Europe%2FBerlin"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            curr = data.get("current", {})
            temp = curr.get("temperature_2m", 14.0)
            wcode = curr.get("weather_code", 0)
            wind = curr.get("wind_speed_10m", 10.0)

            # WMO Code Übersetzung
            code_desc = {
                0: "Klarer Himmel", 1: "Überwiegend sonnig", 2: "Leicht bewölkt", 3: "Bedeckt",
                45: "Nebel", 48: "Dichter Raureifnebel",
                51: "Leichter Nieselregen", 53: "Mäßiger Nieselregen", 55: "Dauer-Niesel",
                61: "Leichter Regen", 63: "Regenschauer", 65: "Kräftiger Regen",
                71: "Leichter Schneefall", 73: "Schneefall", 75: "Kräftiger Schnee",
                80: "Lokale Regenschauer", 81: "Regenschauer", 82: "Heftige Schauer",
                95: "Gewitter"
            }
            desc = code_desc.get(wcode, "Wechselhaft")
            summary = f"{temp:.1f}°C, {desc}, Wind mit {wind:.1f} km/h in {city}"

            weather_res = {
                "city": city,
                "temp": temp,
                "desc": desc,
                "wind": wind,
                "summary": summary
            }
            state.cached_weather = weather_res
            state.last_weather_check = now_ts
            return weather_res
    except Exception as e:
        logger.warning(f"Konnte Wetter für {city} nicht abrufen: {e}")

    fallback = {"city": city, "temp": 14.0, "desc": "Wechselhaft", "wind": 12.0, "summary": f"14°C, frische Brise in {city}"}
    return fallback

get_wilhelmshaven_weather = get_station_weather  # Kompatibilität

def get_schicht_zeit_info() -> Dict[str, str]:
    now = now_berlin()
    hour = now.hour
    wochentage = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    tag = wochentage[now.weekday()]

    if 6 <= hour < 9:
        schicht = "Frühschicht-Start (noch verschlafen, erster heißer Kaffee)"
    elif 9 <= hour < 12:
        schicht = "Vormittagsschicht (Werkstatt brummt, Schrauberzeit)"
    elif 12 <= hour < 13:
        schicht = "Mittagspause (Kantine, Schnitzel-Debatte, Pause)"
    elif 13 <= hour < 15:
        schicht = "Nachmittagsschicht (Endspurt vor Schichtende)"
    elif 15 <= hour < 16:
        schicht = "Feierabend-Countdown (Gleich fällt der Hammer!)"
    elif 16 <= hour < 22:
        schicht = "Spätschicht / Entspannter Abend"
    else:
        schicht = "Nachtschicht (Totenkopf-Stille, Notbesetzung)"

    flair = ""
    if tag == "Montag":
        flair = "Montags-Blues, noch die ganze Woche vor der Brust"
    elif tag == "Mittwoch":
        flair = "Bergfest! Die halbe Woche ist geschafft"
    elif tag == "Freitag":
        flair = "Freitag! Ab eins macht jeder seins, Wochenende in Sicht!"
    elif tag in ["Samstag", "Sonntag"]:
        flair = "Wochenend-Schicht"

    return {
        "tag": tag,
        "uhrzeit": now.strftime("%H:%M"),
        "schicht": schicht,
        "flair": flair
    }

# ==========================================
# AUDIO & AZURACAST FUNKTIONEN
# ==========================================
def lautstaerke_anheben(datei_pfad: str):
    temp_pfad = "temp_boost_" + os.path.basename(datei_pfad)
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", datei_pfad,
            "-af", "volume=6dB,compand=0.3|0.3:1|1:-90/-60|-60/-40|-40/-30:5:0:0",
            temp_pfad
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(temp_pfad):
            os.replace(temp_pfad, datei_pfad)
    except Exception as e:
        logger.error(f"Lautstärke-Anhebung Fehler: {e}")

def lade_zu_azuracast(datei_pfad: str, ziel_pfad: str) -> bool:
    upload_url = f"{AZURA_URL}/station/{STATION_ID}/files"
    headers = {
        "X-API-Key": AZURA_KEY,
        "Content-Type": "application/json"
    }
    try:
        with open(datei_pfad, "rb") as f:
            encoded_file = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "path": ziel_pfad,
            "file": encoded_file
        }
        res = requests.post(upload_url, headers=headers, json=payload, timeout=25)
        return res.status_code in [200, 201]
    except Exception as e:
        logger.error(f"Upload Fehler zu AzuraCast ({ziel_pfad}): {e}")
        return False

def get_nowplaying_from_azura() -> Dict[str, Any]:
    try:
        url = f"{AZURA_URL}/nowplaying/{STATION_ID}"
        headers = {"X-API-Key": AZURA_KEY}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.warning(f"Fehler beim Abruf von NowPlaying: {e}")
    return {}

# ==========================================
# GEMINI KI-TEXT-GENERIERUNG
# ==========================================
def call_gemini(prompt: str) -> str:
    # 1. Versuche Google GenAI SDK
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_KEY)
        try:
            res = client.models.generate_content(model="gemini-3.5-flash-lite", contents=prompt)
            if res and res.text:
                return res.text.strip()
        except Exception:
            chat = client.chats.create(model="gemini-3.5-flash-lite")
            res = chat.send_message(prompt)
            if res and res.text:
                return res.text.strip()
    except Exception as sdk_err:
        logger.warning(f"SDK Aufruf fehlgeschlagen, nutze REST Fallback: {sdk_err}")

    # 2. REST API Fallback
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(url, json=payload, timeout=20)
    if r.status_code == 200:
        data = r.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
    raise RuntimeError(f"Gemini API Fehler ({r.status_code}): {r.text}")

def generiere_moderations_text(persona_key: str, last_song: str, next_song: str, custom_topic: Optional[str] = None) -> Dict[str, Any]:
    st = get_station_settings()
    weather = get_station_weather()
    schicht_info = get_schicht_zeit_info()
    personas = get_personas()

    # Co-Moderation / Duo
    if persona_key == "duo":
        active_mods = get_active_music_moderators(now_berlin().hour)
        if len(active_mods) >= 2:
            m1, m2 = random.sample(active_mods, 2)
        elif len(personas) >= 2:
            keys = [k for k in personas.keys() if k != "markus"]
            if len(keys) >= 2:
                sampled_keys = random.sample(keys, 2)
                m1, m2 = personas[sampled_keys[0]], personas[sampled_keys[1]]
            else:
                m1, m2 = personas.get("alice", DEFAULT_PERSONAS["alice"]), personas.get("kalle", DEFAULT_PERSONAS["kalle"])
        else:
            m1 = personas.get("alice", DEFAULT_PERSONAS["alice"])
            m2 = personas.get("kalle", DEFAULT_PERSONAS["kalle"])

        name1, name2 = m1["name"], m2["name"]
        p1, p2 = m1["prompt_persona"], m2["prompt_persona"]
        mod_pair_name = f"{name1} & {name2}"

        topic_instruction = f"Thema / Anlass: {custom_topic}" if custom_topic else f"Thema: Kurze, humorvolle Reiberei zwischen {name1} und {name2}"

        prompt = (
            f"Du schreibst einen kurzen Radio-Dialog für das Moderatoren-Duo vom Sender '{st['station_name']} ({st['station_frequency']})' - {st['station_claim']}.\n"
            f"Sender-Atmosphäre & Thema: {st['station_theme']}\n"
            f"Musikstil / Programm: {st['station_genre']}\n\n"
            f"Charakter 1 ({name1}): {p1}\n"
            f"Charakter 2 ({name2}): {p2}\n\n"
            f"Kontext:\n"
            f"- Vorheriger Song (gerade verklungen): {last_song if last_song else 'ein starker Song'}\n"
            f"- Kommender Song (jetzt anmoderieren): {next_song if next_song else 'der nächste Knaller'}\n"
            f"- Aktuelle Uhrzeit & Tagesabschnitt: {schicht_info['uhrzeit']} Uhr, {schicht_info['schicht']}, {schicht_info['flair']}\n"
            f"- Wetter in {st['weather_city']}: {weather['summary']}\n"
            f"- {topic_instruction}\n\n"
            f"Vorgaben:\n"
            f"- Beide Charaktere moderieren für '{st['station_name']}' und passen sich natürlich dem Sender-Thema an ({st['station_theme']}).\n"
            f"- Maximal 4 bis 5 kurze Sprechzeilen insgesamt (knackiger, witziger Schlagabtausch, ca. 20-30 Sekunden).\n"
            f"- Beide Charaktere bleiben voll in ihrer Rolle.\n"
            f"- Eine Zeile bezieht sich kurz auf den vergangenen oder kommenden Song.\n"
            f"- Formatiere JEDE Zeile EXAKT mit Sprecher-Präfix, z.B.:\n"
            f"{name1.upper()}: [Sprechtext]\n"
            f"{name2.upper()}: [Sprechtext]\n"
            f"{name1.upper()}: [Sprechtext]\n"
            f"Antworte NUR mit den Dialogzeilen, kein weiterer Text."
        )

        raw_text = call_gemini(prompt)
        return {
            "is_duo": True,
            "mod_name": mod_pair_name,
            "speaker_key": "duo",
            "text": raw_text,
            "stichwort": "duo_dialog"
        }

    # Einzelmoderator
    persona_data = personas.get(persona_key, personas.get("alice", DEFAULT_PERSONAS["alice"]))
    p_persona = persona_data["prompt_persona"]
    mod_name = persona_data["name"]

    bridge_instruction = ""
    if last_song and next_song:
        bridge_instruction = f"Baue eine geschmeidige Brücke: Erwähne kurz den gerade gespielten Track '{last_song}' und kündige den kommenden Track '{next_song}' an."
    elif next_song:
        bridge_instruction = f"Kündige den kommenden Track '{next_song}' an."

    topic_instruction = f"Beziehe dich unbedingt auf dieses Thema: {custom_topic}" if custom_topic else f"Beziehe dich auf das Sender-Thema ({st['station_theme']}), die Tageszeit oder das Wetter."

    prompt = (
        f"{p_persona}\n\n"
        f"Sender-Kontext:\n"
        f"- Radiosender: {st['station_name']} ({st['station_frequency']}) - {st['station_claim']}\n"
        f"- Sender-Thema & Atmosphäre: {st['station_theme']}\n"
        f"- Musikstil: {st['station_genre']}\n"
        f"- {bridge_instruction}\n"
        f"- Aktuelle Zeit / Stimmung: {schicht_info['uhrzeit']} Uhr, {schicht_info['schicht']}. {schicht_info['flair']}\n"
        f"- Wetter in {st['weather_city']}: {weather['summary']}\n"
        f"- {topic_instruction}\n\n"
        f"Aufgabe:\n"
        f"Formuliere eine kurze, lebendige Radio-Moderation (maximal 3-4 knackige Sätze) für {st['station_name']}.\n"
        f"Bleibe voll in deiner Rolle und passe dich an das Sender-Thema an!\n"
        f"Antworte EXAKT im folgenden Format:\n"
        f"STICHWORT: [einzelnes kurzes Schlagwort, z.B. kaffeepause, wetter, feierabend]\n"
        f"TEXT: [deine gesprochene Moderation]"
    )

    raw_text = call_gemini(prompt)
    stichwort = "moderation"
    mod_text = raw_text

    if "STICHWORT:" in raw_text and "TEXT:" in raw_text:
        teile = raw_text.split("TEXT:")
        stichwort_teil = teile[0].replace("STICHWORT:", "").strip()
        stichwort = "".join(c for c in stichwort_teil.lower() if c.isalnum() or c == "_")[:15]
        mod_text = teile[1].strip()

    return {
        "is_duo": False,
        "mod_name": mod_name,
        "speaker_key": persona_key,
        "text": mod_text,
        "stichwort": stichwort
    }

# ==========================================
# EDGE-TTS AUDIO GENERIERUNG
# ==========================================
def parse_duo_lines(text: str) -> List[tuple]:
    lines = []
    personas = get_personas()
    mapping = {}
    for mid, m in personas.items():
        mapping[m["name"].upper()] = mid
        mapping[mid.upper()] = mid

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        found = False
        for prefix, mid in mapping.items():
            if line.upper().startswith(prefix + ":"):
                lines.append((mid, line[len(prefix) + 1:].strip()))
                found = True
                break
        if not found:
            lines.append(("alice", line))
    return lines

def render_speech_audio(text: str, speaker_key: str, output_path: str):
    personas = get_personas()
    if speaker_key == "duo":
        dialog_lines = parse_duo_lines(text)
        if not dialog_lines:
            dialog_lines = [("alice", text)]

        part_files = []
        try:
            for idx, (spk, part_text) in enumerate(dialog_lines):
                spk_data = personas.get(spk, personas.get("alice", {}))
                voice = spk_data.get("voice", "de-DE-KatjaNeural")
                part_file = f"temp_part_{idx}_{int(time.time()*1000)}.mp3"
                subprocess.run([
                    "edge-tts",
                    "--voice", voice,
                    "--rate=+4%",
                    "--text", part_text,
                    "--write-media", part_file
                ], check=True, stdout=subprocess.DEVNULL)
                part_files.append(part_file)

            # Zusammenfügen mit FFmpeg concat demuxer
            concat_list = f"concat_{int(time.time()*1000)}.txt"
            with open(concat_list, "w") as f:
                for p in part_files:
                    f.write(f"file '{os.path.abspath(p)}'\n")

            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_list, "-c", "copy", output_path
            ], check=True, stdout=subprocess.DEVNULL)

            if os.path.exists(concat_list):
                os.remove(concat_list)
        finally:
            for p in part_files:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except:
                        pass
    else:
        spk_data = personas.get(speaker_key, personas.get("alice", {}))
        voice = spk_data.get("voice", "de-DE-KatjaNeural")
        subprocess.run([
            "edge-tts",
            "--voice", voice,
            "--rate=+4%",
            "--text", text,
            "--write-media", output_path
        ], check=True, stdout=subprocess.DEVNULL)

# ==========================================
# SENDEN & ARCHIVIEREN
# ==========================================
def sende_moderation_on_air(text: str, speaker_key: str, stichwort: str = "on_air") -> bool:
    aktuelle_zeit = now_berlin()
    audio_file = f"temp_on_air_{int(time.time())}.mp3"
    ziel_datei = "Moderationen/moderation.mp3"

    try:
        render_speech_audio(text, speaker_key, audio_file)
        lautstaerke_anheben(audio_file)

        # 1. Live Upload nach AzuraCast
        erfolg_live = lade_zu_azuracast(audio_file, ziel_datei)
        if not erfolg_live:
            state.add_log("Fehler beim Upload der Moderation zu AzuraCast!", "error")
            return False

        # 2. Ins Archiv sichern
        heute_ordner = aktuelle_zeit.strftime("%d%m%Y_Moderationen")
        uhrzeit_str = aktuelle_zeit.strftime("%H-%M-%S")
        personas = get_personas()
        if speaker_key == "duo":
            spk_name = "Duo"
        else:
            spk_name = personas.get(speaker_key, {}).get("name", "Moderator")
        archiv_pfad = f"{heute_ordner}/{uhrzeit_str}_{spk_name}_{stichwort}.mp3"
        lade_zu_azuracast(audio_file, archiv_pfad)

        # Im State merken
        state.tracks_since_last_mod = 0
        state.add_log(f"Moderation ({spk_name}) erfolgreich On-Air & archiviert!", "success")
        state.add_recent_moderation({
            "time": aktuelle_zeit.strftime("%H:%M:%S"),
            "speaker": spk_name,
            "speaker_key": speaker_key,
            "text": text,
            "archive_path": archiv_pfad
        })

        return True
    except Exception as e:
        state.add_log(f"Fehler bei Moderation: {e}", "error")
        return False
    finally:
        if os.path.exists(audio_file):
            try:
                os.remove(audio_file)
            except:
                pass

def generiere_nachrichten_moderation(last_song: str = "", next_song: str = "") -> Dict[str, Any]:
    st = get_station_settings()
    weather = get_station_weather()
    personas = get_personas()
    p_markus = personas.get("markus", {}).get("prompt_persona", DEFAULT_PERSONAS["markus"]["prompt_persona"])
    now = now_berlin()
    uhrzeit = now.strftime("%H:%M")

    bridge = ""
    if next_song:
        bridge = f"Am Ende der Sendung kündigst du kurz an, dass es nun weitergeht mit: '{next_song}'."

    prompt = (
        f"{p_markus}\n\n"
        f"Sender-Kontext:\n"
        f"- Radiosender: {st['station_name']} ({st['station_frequency']}) - {st['station_claim']}\n"
        f"- Sendezeit: {uhrzeit} Uhr\n"
        f"- Wetter in {st['weather_city']}: {weather['summary']}\n"
        f"- {bridge}\n\n"
        f"Aufgabe:\n"
        f"Formuliere eine kompakte, hochprofessionelle Nachrichtensendung zur vollen Stunde auf {st['station_name']}.\n"
        f"Struktur:\n"
        f"1. Seriöser Sendungsstart: 'Hier ist {st['station_name']} mit den Nachrichten um {uhrzeit} Uhr mit Markus...'\n"
        f"2. Eine kurze, glaubwürdige Meldung aus {st['weather_city']} und der Region.\n"
        f"3. Ein bis zwei prägnante Schlagzeilen aus Deutschland oder der Welt.\n"
        f"4. Das Wetter in {st['weather_city']}: '{weather['summary']}'.\n"
        f"5. Kurzer Abgang zur Musik: 'Und jetzt geht es weiter mit Musik auf {st['station_name']}: Hier ist {next_song if next_song else 'der nächste Track'}!'\n\n"
        f"Länge: ca. 4 bis 5 Sätze, sauber und flüssig vorlesbar (ca. 35-45 Sekunden).\n"
        f"Antworte EXAKT im folgenden Format:\n"
        f"STICHWORT: [kurzes Schlagwort wie stundennews, regional, welt]\n"
        f"TEXT: [gesprochener Nachrichtentext]"
    )

    raw = call_gemini(prompt)
    stichwort = "stundennews"
    mod_text = raw
    if "STICHWORT:" in raw and "TEXT:" in raw:
        teile = raw.split("TEXT:")
        stichwort_teil = teile[0].replace("STICHWORT:", "").strip()
        stichwort = "".join(c for c in stichwort_teil.lower() if c.isalnum() or c == "_")[:15]
        mod_text = teile[1].strip()

    return {
        "is_duo": False,
        "mod_name": "Markus (Nachrichten)",
        "speaker_key": "markus",
        "text": mod_text,
        "stichwort": stichwort
    }

def generiere_stunden_nachrichten(erzwinge: bool = False) -> bool:
    aktuelle_zeit = now_berlin()
    aktuelle_stunde = aktuelle_zeit.hour

    if erzwinge or (aktuelle_zeit.minute <= 5 and state.letzte_nachrichten_stunde != aktuelle_stunde):
        state.add_log(f"Markus bereitet die stündlichen Nachrichten für {aktuelle_stunde}:00 Uhr vor...", "info")
        state.letzte_nachrichten_stunde = aktuelle_stunde

        try:
            mod_result = generiere_nachrichten_moderation(last_song=state.current_song, next_song=state.next_song)
            return sende_moderation_on_air(
                text=mod_result["text"],
                speaker_key="markus",
                stichwort="stundennews"
            )
        except Exception as e:
            state.add_log(f"Fehler bei stündlichen Nachrichten: {e}", "error")
            return False
    return False

# ==========================================
# ASYNCHRONE HINTERGRUND-SCHLEIFE
# ==========================================
async def background_radio_loop():
    logger.info("Starte Studio FM Hintergrund-Worker...")
    await asyncio.sleep(2)

    # Initial-Nachrichten beim Container-Start falls noch nicht erfolgt
    try:
        curr_hour = now_berlin().hour
        if state.hourly_news_as_moderation and state.letzte_nachrichten_stunde != curr_hour:
            state.add_log(f"Bereite Initial-Nachrichten für {curr_hour}:00 Uhr als Moderation vor...", "info")
            state.letzte_nachrichten_stunde = curr_hour
            mod_result = generiere_nachrichten_moderation(last_song=state.current_song, next_song=state.next_song)
            sende_moderation_on_air(
                text=mod_result["text"],
                speaker_key="markus",
                stichwort="start_news"
            )
    except Exception as e:
        logger.warning(f"Fehler beim Initialisieren der Nachrichten: {e}")

    while True:
        try:
            # NowPlaying von AzuraCast prüfen
            np_data = get_nowplaying_from_azura()
            if np_data:
                state.now_playing_data = np_data
                curr = np_data.get("now_playing", {})
                curr_song_text = curr.get("song", {}).get("text", "")
                curr_playlist = curr.get("playlist", "")

                nxt = np_data.get("playing_next", {})
                next_song_text = nxt.get("song", {}).get("text", "")

                # Songwechsel erkannt?
                if curr_song_text and curr_song_text != state.current_song:
                    state.last_played_song = state.current_song
                    state.current_song = curr_song_text
                    state.next_song = next_song_text

                    # Prüfen, ob eine Moderation läuft
                    ist_moderation = "moderation" in curr_song_text.lower() or "moderation" in curr_playlist.lower()

                    if ist_moderation:
                        state.tracks_since_last_mod = 0
                        state.add_log(f"On-Air: Moderation wird aktuell abgespielt! Zähler zurückgesetzt.", "info")
                    else:
                        state.tracks_since_last_mod += 1
                        state.add_log(
                            f"Neuer Track: '{curr_song_text}' (Track {state.tracks_since_last_mod}/{state.moderation_interval} bis zur nächsten Moderation)",
                            "info"
                        )

                        # Wenn Autopilot an ist und der Intervall-Schwellenwert erreicht wird:
                        # Bereite Moderation vor, sobald track >= interval - 1 ist!
                        if state.autopilot_enabled and state.tracks_since_last_mod >= (state.moderation_interval - 1):
                            curr_hour = now_berlin().hour
                            soll_nachrichten_sein = state.hourly_news_as_moderation and (state.letzte_nachrichten_stunde != curr_hour)

                            if soll_nachrichten_sein:
                                state.add_log(
                                    f"Autopilot: Stündliche Nachrichten für {curr_hour}:00 Uhr werden als nächster Moderations-Slot vorbereitet!",
                                    "info"
                                )
                                state.letzte_nachrichten_stunde = curr_hour
                                mod_result = generiere_nachrichten_moderation(
                                    last_song=state.current_song,
                                    next_song=state.next_song
                                )
                                sende_moderation_on_air(
                                    text=mod_result["text"],
                                    speaker_key="markus",
                                    stichwort=mod_result["stichwort"]
                                )
                            else:
                                state.add_log("Autopilot: Bereite Musik-Moderation für den anstehenden Slot vor...", "info")

                                # Sprecher-Wahl dynamisch nach aktiven Sendezeiten
                                if state.persona_mode == "random":
                                    if random.random() < state.duo_probability:
                                        chosen_persona = "duo"
                                    else:
                                        active_candidates = get_active_music_moderators(curr_hour)
                                        if active_candidates:
                                            chosen_persona = random.choice(active_candidates)["id"]
                                        else:
                                            chosen_persona = "alice"
                                else:
                                    chosen_persona = state.persona_mode

                                mod_result = generiere_moderations_text(
                                    persona_key=chosen_persona,
                                    last_song=state.current_song,
                                    next_song=state.next_song
                                )

                                sende_moderation_on_air(
                                    text=mod_result["text"],
                                    speaker_key=mod_result["speaker_key"],
                                    stichwort=mod_result["stichwort"]
                                )

        except Exception as e:
            logger.error(f"Fehler in Hintergrund-Schleife: {e}")

        await asyncio.sleep(15)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(background_radio_loop())
    yield
    task.cancel()

app = FastAPI(title="Studio FM - Regiepult", lifespan=lifespan)

# Static Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def get_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Studio FM</h1><p>Static index.html wird geladen...</p>")

@app.get("/api/status")
def get_status():
    np = state.now_playing_data
    curr = np.get("now_playing", {})
    nxt = np.get("playing_next", {})
    song_hist = np.get("song_history", [])[:5]

    st = get_station_settings()
    weather = get_station_weather()
    schicht = get_schicht_zeit_info()

    curr_hour = now_berlin().hour
    next_is_news = state.hourly_news_as_moderation and (state.letzte_nachrichten_stunde != curr_hour)

    return {
        "status": "online",
        "station_name": st["station_name"],
        "station_settings": st,
        "autopilot": {
            "enabled": state.autopilot_enabled,
            "interval": state.moderation_interval,
            "tracks_since_last_mod": state.tracks_since_last_mod,
            "duo_probability": state.duo_probability,
            "persona_mode": state.persona_mode,
            "hourly_news": state.hourly_news_as_moderation,
            "next_slot_is_news": next_is_news,
            "last_news_hour": state.letzte_nachrichten_stunde
        },
        "now_playing": {
            "title": curr.get("song", {}).get("title", ""),
            "artist": curr.get("song", {}).get("artist", ""),
            "text": curr.get("song", {}).get("text", state.current_song),
            "art": curr.get("song", {}).get("art", ""),
            "duration": curr.get("duration", 0),
            "elapsed": curr.get("elapsed", 0),
            "remaining": curr.get("remaining", 0),
            "playlist": curr.get("playlist", "")
        },
        "playing_next": {
            "title": nxt.get("song", {}).get("title", ""),
            "artist": nxt.get("song", {}).get("artist", ""),
            "text": nxt.get("song", {}).get("text", state.next_song),
            "playlist": nxt.get("playlist", "")
        },
        "history": song_hist,
        "weather": weather,
        "schicht": schicht,
        "personas": get_personas(),
        "recent_moderations": state.recent_moderations[:10],
        "logs": state.logs[:20]
    }

class AutopilotConfig(BaseModel):
    enabled: bool
    interval: int
    duo_probability: float
    persona_mode: str
    hourly_news: Optional[bool] = True

@app.post("/api/autopilot")
def set_autopilot(config: AutopilotConfig):
    state.autopilot_enabled = config.enabled
    state.moderation_interval = max(1, config.interval)
    state.duo_probability = max(0.0, min(1.0, config.duo_probability))
    state.persona_mode = config.persona_mode
    if config.hourly_news is not None:
        state.hourly_news_as_moderation = config.hourly_news
    state.add_log(
        f"Autopilot-Einstellungen aktualisiert: Aktiv={config.enabled}, Intervall={config.interval}, News/h={state.hourly_news_as_moderation}, Modus={config.persona_mode}",
        "info"
    )
    return {"status": "ok", "state": config}

class GenerateDraftRequest(BaseModel):
    speaker: str
    custom_topic: Optional[str] = None

@app.post("/api/generate-draft")
def generate_draft(req: GenerateDraftRequest):
    try:
        draft = generiere_moderations_text(
            persona_key=req.speaker,
            last_song=state.current_song,
            next_song=state.next_song,
            custom_topic=req.custom_topic
        )
        state.add_log(f"Entwurf für {draft['mod_name']} generiert.", "info")
        return {"status": "ok", "draft": draft}
    except Exception as e:
        state.add_log(f"Fehler bei Entwurf-Generierung: {e}", "error")
        raise HTTPException(status_code=500, detail=str(e))

class PreviewAudioRequest(BaseModel):
    speaker: str
    text: str

@app.post("/api/render-preview")
def render_preview(req: PreviewAudioRequest):
    try:
        preview_file = os.path.join(static_dir, "temp_preview.mp3")
        render_speech_audio(req.text, req.speaker, preview_file)
        lautstaerke_anheben(preview_file)
        # Cache buster
        ts = int(time.time() * 1000)
        return {"status": "ok", "audio_url": f"/static/temp_preview.mp3?t={ts}"}
    except Exception as e:
        state.add_log(f"Fehler bei Audio-Vorschau: {e}", "error")
        raise HTTPException(status_code=500, detail=str(e))

class OnAirRequest(BaseModel):
    speaker: str
    text: str
    stichwort: Optional[str] = "regie_manuell"

@app.post("/api/on-air")
def put_on_air(req: OnAirRequest, background_tasks: BackgroundTasks):
    try:
        erfolg = sende_moderation_on_air(
            text=req.text,
            speaker_key=req.speaker,
            stichwort=req.stichwort or "manuell"
        )
        if erfolg:
            return {"status": "ok", "message": "Moderation erfolgreich nach AzuraCast übertragen!"}
        else:
            raise HTTPException(status_code=500, detail="Upload fehlgeschlagen")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class QuickShoutoutRequest(BaseModel):
    speaker: str
    text: str

@app.post("/api/quick-shoutout")
def quick_shoutout(req: QuickShoutoutRequest):
    try:
        erfolg = sende_moderation_on_air(
            text=req.text,
            speaker_key=req.speaker,
            stichwort="shoutout"
        )
        if erfolg:
            return {"status": "ok", "message": "Durchsage sofort On-Air gebracht!"}
        else:
            raise HTTPException(status_code=500, detail="Durchsage konnte nicht übertragen werden")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/trigger-news")
def trigger_news():
    erfolg = generiere_stunden_nachrichten(erzwinge=True)
    if erfolg:
        return {"status": "ok", "message": "Nachrichten erfolgreich aktualisiert!"}
    raise HTTPException(status_code=500, detail="Fehler bei Nachrichten-Erstellung")

# ==========================================
# MODERATOREN-VERWALTUNG ENDPUNKTE
# ==========================================
class ModeratorModel(BaseModel):
    id: str
    name: str
    role: str
    voice: str
    avatar: Optional[str] = "🎙️"
    description: Optional[str] = ""
    enabled: bool = True
    active_hours: List[int] = [0, 24]
    prompt_persona: str

@app.get("/api/moderators")
def get_moderators_endpoint():
    return {
        "status": "ok",
        "moderators": get_personas(),
        "available_voices": AVAILABLE_VOICES
    }

@app.post("/api/moderators")
def save_or_update_moderator(mod: ModeratorModel):
    mod_id = mod.id.strip().lower()
    mod_id = "".join(c for c in mod_id if c.isalnum() or c in ("_", "-"))
    if not mod_id:
        mod_id = "".join(c for c in mod.name.lower() if c.isalnum() or c in ("_", "-"))
    if not mod_id:
        raise HTTPException(status_code=400, detail="Ungültige Moderator-ID oder Name.")

    mods = load_moderators()
    mods[mod_id] = {
        "id": mod_id,
        "name": mod.name.strip(),
        "role": mod.role.strip(),
        "voice": mod.voice.strip(),
        "avatar": mod.avatar or "🎙️",
        "description": mod.description or "",
        "enabled": bool(mod.enabled),
        "active_hours": mod.active_hours if len(mod.active_hours) == 2 else [0, 24],
        "prompt_persona": mod.prompt_persona.strip()
    }
    saved = save_moderators(mods)
    if not saved:
        raise HTTPException(status_code=500, detail="Fehler beim Speichern der Moderatoren.")

    state.add_log(f"Moderator '{mod.name}' ({mod_id}) gespeichert.", "info")
    return {"status": "ok", "moderator": mods[mod_id], "moderators": mods}

@app.delete("/api/moderators/{mod_id}")
def delete_moderator_endpoint(mod_id: str):
    mod_id = mod_id.strip().lower()
    if mod_id == "markus":
        raise HTTPException(status_code=400, detail="Der Nachrichtensprecher 'Markus' darf nicht gelöscht werden!")

    mods = load_moderators()
    if mod_id not in mods:
        raise HTTPException(status_code=404, detail=f"Moderator '{mod_id}' nicht gefunden.")

    deleted_name = mods[mod_id].get("name", mod_id)
    del mods[mod_id]
    save_moderators(mods)
    state.add_log(f"Moderator '{deleted_name}' ({mod_id}) gelöscht.", "info")
    return {"status": "ok", "message": f"Moderator '{deleted_name}' gelöscht.", "moderators": mods}

# ==========================================
# SENDER-EINSTELLUNGEN ENDPUNKTE
# ==========================================
class StationSettingsModel(BaseModel):
    station_name: str
    station_frequency: Optional[str] = "98.5"
    station_claim: Optional[str] = "Dein Sender. Dein Sound."
    station_theme: str
    station_genre: Optional[str] = "Rock, Pop & Alternative"
    weather_city: Optional[str] = "Hamburg"
    weather_lat: Optional[float] = 53.55
    weather_lon: Optional[float] = 9.99

@app.get("/api/settings")
def get_settings_endpoint():
    return {
        "status": "ok",
        "settings": get_station_settings()
    }

@app.post("/api/settings")
def save_settings_endpoint(settings_data: StationSettingsModel):
    data = settings_data.dict()
    saved = save_station_settings(data)
    if not saved:
        raise HTTPException(status_code=500, detail="Fehler beim Speichern der Einstellungen.")
    state.add_log(f"Sender-Einstellungen aktualisiert: '{data['station_name']} ({data['station_frequency']})' - {data['station_claim']}", "info")
    return {"status": "ok", "settings": data}

@app.post("/api/random-moderator-ai")
def generate_ai_moderator():
    st = get_station_settings()
    voices_str = ", ".join([f"'{v['id']}' ({v['gender']}, {v['name']})" for v in AVAILABLE_VOICES])
    prompt = (
        f"Erfinde einen einzigartigen, witzigen, sympathischen und originellen Radio-Moderator für den Radiosender '{st['station_name']} ({st['station_frequency']})' - {st['station_claim']}.\n"
        f"Sender-Thema & Atmosphäre: {st['station_theme']}\n"
        f"Musikstil / Vibe: {st['station_genre']}\n"
        f"Standort: {st['weather_city']}\n"
        f"Die Persönlichkeit der Person soll perfekt zum Thema '{st['station_theme']}' passen!\n"
        f"WICHTIG - Wähle eine passende Stimme aus dieser Liste:\n"
        f"{voices_str}\n\n"
        "Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt ohne Markdown-Codeblöcke mit folgender Struktur:\n"
        "{\n"
        '  "id": "eindeutige_kurze_id_ohne_leerzeichen",\n'
        '  "name": "Vorname oder Spitzname",\n'
        '  "role": "Kurze Berufsbezeichnung & Rolle",\n'
        '  "avatar": "Ein einzelnes passendes Emoji",\n'
        '  "voice": "Eine der exakten Stimmen-IDs oben passend zum Geschlecht",\n'
        '  "description": "Ein kurzer, humorvoller Satz über den Charakter",\n'
        '  "active_hours": [6, 16],\n'
        '  "prompt_persona": "Ausführliche Persönlichkeitsbeschreibung: Tonfall, Marotten, typische Begrüßung, Bezug zum Sender-Thema, Humor."\n'
        "}"
    )
    raw = call_gemini(prompt)
    try:
        clean = raw.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        data = json.loads(clean.strip())
        return {"status": "ok", "moderator": data}
    except Exception as e:
        logger.error(f"Fehler beim Parsen des KI-Moderators: {e}, Text: {raw}")
        raise HTTPException(status_code=500, detail="KI-Moderator konnte nicht generiert werden.")


# ==========================================
# MAIN ENTRYPOINT
# ==========================================
if __name__ == "__main__":
    import socket
    selected_port = WEB_PORT
    for test_port in [WEB_PORT, 8060, 8065, 8070, 8085, 8095, 8555]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", test_port))
                selected_port = test_port
                break
            except OSError:
                print(f"[HINWEIS] Port {test_port} ist bereits belegt, teste Port {test_port + 1}...")

    print(f"==================================================")
    print(f" Studio FM 98.5 & Moderatoren-Bot gestartet")
    print(f" Web-Interface erreichbar unter: http://0.0.0.0:{selected_port}")
    print(f"==================================================")
    uvicorn.run(app, host="0.0.0.0", port=selected_port, log_level="warning")
