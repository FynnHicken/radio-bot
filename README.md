# 🎙️ AI Radio Studio & Automation Bot

Ein vollautomatisiertes, modernes Web-Regiepult und KI-Moderatoren-System für Webradios (speziell entwickelt für **AzuraCast**). Das System verbindet **Google Gemini** für kontextbewusste Moderationen & Dialoge, **Microsoft Edge-TTS** für lebensechte deutsche Stimmen und das **Open-Meteo API** für lokales Live-Wetter.

![AI Radio Studio](https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/radio.svg)

---

## ✨ Features

- **🔴 Live-Studio Web-Interface**:
  - Teleprompter mit Live-Charakterzählung und Entwurf-Generierung via Gemini.
  - Sofortiges Vorhören generierter Audiomoderationen im Browser.
  - 1-Klick „ON AIR“-Button für direkten Upload in den AzuraCast-Moderatoren-Slot.
  - Spontane Blitz-Durchsagen / Eilmeldungen on-the-fly vertonen und senden.
  - Live Now-Playing Anzeige, Track-Fortschritt, Sende-Historie und Studio-Logbuch.
- **🤖 Autopilot & Automatisierung**:
  - Wählbares Track-Intervall (z. B. alle 5 Songs automatisch eine Moderation).
  - Stündliche automatisierte Radionachrichten (mit Moderator *Markus*) zur vollen Stunde inkl. Übergang zum nächsten Track.
  - Song-Brücken: Bezieht sich natürlich auf den gerade verklungenen Track und moderiert den kommenden an.
  - Live-Wetter & Schichtkontext (z. B. Frühschicht, Bergfest, Feierabend, lokale Wetterbedingungen).
- **👥 Multi-Moderatoren-Management**:
  - Verwalte ein ganzes Team von Radio-Moderatoren (z. B. *Alice*, *Kalle*, *Sven*, *Markus*).
  - Individuelle Sendezeiten & Schichten (24/7, Frühschicht, Spätschicht, Nachtschicht oder eigene Zeiten).
  - Zuordnung realistischer deutscher Stimmen (*Katja, Conrad, Killian, Seraphina, Amala, Florian*).
  - **Duo-Co-Moderation**: Dynamische Dialoge und witzige Schlagabtausche zwischen zwei Sprechern.
  - **Charakter-Randomizer & KI-Erfinder**: 1-Klick Auswürfeln neuer Charaktere oder Live-Erfindung via Gemini.
- **⚙️ Voll konfigurierbare Sender-Identität & Themes**:
  - Sendername, Frequenz, Claim, Musikstil und generelles Thema frei anpassbar.
  - Alle Moderatoren und Prompts passen sich automatisch in Echtzeit an das gewählte Sender-Thema an.
  - Schnellauswahl vorgefertigter Themes (Studio FM, Orbital Space Station, Pure Rock, Piratenradio, Beach Club, Cyberpunk).

---

## 🚀 Schnellstart mit Docker Compose

### 1. Repository klonen
```bash
git clone https://github.com/<DEIN-USERNAME>/radio-bot.git
cd radio-bot
```

### 2. Konfiguration anlegen
Kopiere das Template und trage deine API-Schlüssel ein:
```bash
cp .env.example .env
nano .env
```

`.env`-Parameter:
| Variable | Beschreibung | Standard |
|---|---|---|
| `GEMINI_KEY` | Google Gemini API Key ([Google AI Studio](https://aistudio.google.com/)) | *Erforderlich* |
| `AZURA_URL` | AzuraCast API Basis-URL (z. B. `http://192.168.0.14:8090/api`) | *Erforderlich* |
| `AZURA_KEY` | AzuraCast API Schlüssel (unter AzuraCast -> Mein Konto -> API-Schlüssel) | *Erforderlich* |
| `STATION_ID` | AzuraCast Sender-ID | `1` |
| `PORT` | Web-Port des Studios | `8060` (fällt auto auf freien Port zurück) |
| `TZ` | Zeitzone für Schichten & Uhrzeiten | `Europe/Berlin` |

### 3. Container starten
```bash
docker compose up -d --build
```

Das Web-Studio ist nun erreichbar unter:
👉 **`http://<SERVER-IP>:8085`** (oder dem in den Logs angegebenen Port).

---

## 📻 AzuraCast Integration

1. Lege in AzuraCast eine Playlist vom Typ **„Standard“** an (oder nutze Jingles/Erweitert).
2. Lade einen Platzhalter-Track unter `Moderationen/moderation.mp3` hoch.
3. Stelle die Playlist so ein, dass sie alle X Tracks abgespielt wird.
4. Der Bot vertont Moderationen automatisch und ersetzt `Moderationen/moderation.mp3` nahtlos über die AzuraCast-API, bevor der Slot gespielt wird.
5. Zusätzlich wird jede gesendete Moderation in einem datumsbasierten Archiv-Ordner in AzuraCast dauerhaft gesichert.

---

## 🛠️ Verwendete Technologien

- **Backend**: Python 3.11, [FastAPI](https://fastapi.tiangolo.com/), Uvicorn
- **KI & TTS**: [Google Gemini](https://ai.google.dev/), [Edge-TTS](https://github.com/rany2/edge-tts)
- **Audio-Processing**: FFmpeg
- **Frontend**: Tailwind CSS, Lucide Icons, Vanilla JavaScript
- **Wetterdaten**: [Open-Meteo API](https://open-meteo.com/) (ohne API-Key)
- **Container**: Docker & Docker Compose

---

## 📄 Lizenz
MIT License.
