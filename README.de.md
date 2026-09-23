# StackChan Custom Firmware + Server

[English](README.md) | **Deutsch**

Eigene Firmware und ein selbst gehosteter Sprachserver für den **M5Stack StackChan** (CoreS3 mit zwei Feetech-SCS0009-Servos). Ersetzt die Stock-Firmware und die Hersteller-Cloud durch:

- **Deinen eigenen Server** (Docker, beliebiger Host): Google Gemini Live für Echtzeit-Sprache, Home-Assistant-Steuerung, Kalender-Briefing, optional Websuche und n8n-Status.
- **Einen ruhigeren, lebendigeren Roboter**: animierte cyanfarbene Augen, weiche Kopfbewegungen ohne Ruckeln, Kopfgesten passend zur Stimmung und **Gesichtsverfolgung** über die eingebaute Kamera.
- **Proaktives Sprechen**: Home Assistant kann den Roboter von sich aus sprechen lassen (Ankunft, Termine, beliebige Anlässe), ohne Wake-Word.

> Status: privates Projekt, läuft auf dem Gerät des Autors, Gesichtsverfolgung inklusive.

## Zusammenspiel

```
 StackChan (CoreS3)                    Dein Server (Docker)                 Cloud / LAN
┌──────────────────────┐  WebSocket  ┌────────────────────────┐        ┌──────────────────┐
│ xiaozhi-esp32 + Patch│◄───────────►│ stackchan-server       │◄──────►│ Gemini Live/TTS  │
│ Wake-Word, Mic, Amp  │  /xiaozhi/ws│ (rudyll-Fork + Patches)│        └──────────────────┘
│ Augen, Servos, Kamera│             │ /vinci/say  /vinci/push│◄──────►┌──────────────────┐
└──────────────────────┘             └───────────▲────────────┘  ws    │ Home Assistant   │
                                                 └─────────────────────┤ rest_command     │
                                                        HTTP           └──────────────────┘
```

1. Beim Start fragt der Roboter den OTA-Endpunkt des Servers (`/xiaozhi/ota/`), wohin er sich verbinden soll, und bekommt die WebSocket-URL.
2. Nach dem Wake-Word streamt er Audio zum Server; der Server spricht mit Gemini Live und führt Home-Assistant-Aktionen als Tools aus.
3. Der Server schickt Emotionen (`{"type":"llm","emotion":"happy"}`); die Firmware zeigt die passende Augenanimation und Kopfgeste.
4. Home Assistant ruft `/vinci/say?occasion=...` auf; der Server formuliert mit Gemini einen kurzen Satz, synthetisiert ihn und spielt ihn am Roboter ab.

## Aufbau des Repos

| Pfad | Inhalt |
|---|---|
| `firmware/xiaozhi-esp32.patch` | Alle Firmware-Änderungen gegen einen festen [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)-Commit |
| `firmware/build.sh` | Klont Upstream, wendet den Patch an, legt die Augen ein, baut |
| `firmware/eyes/` | `make_eyes.py` (Generator für die Augenanimationen, Pillow) und die erzeugten GIFs |
| `server/Dockerfile` | Der komplette Server: klont [rudyll/stackchan_ha_addons](https://github.com/rudyll/stackchan_ha_addons) und bringt alle Server-Patches inline mit |
| `server/docker-compose.yml`, `server/.env.example` | Läuft überall, wo Docker läuft |
| `homeassistant/` | `rest_command` und Beispiel-Automationen für proaktives Sprechen |

### Was der Firmware-Patch ändert

| Datei | Änderung |
|---|---|
| `boards/m5stack/core-s3/head_motion.h` | **Neu.** Servo-Treiber (UART1, 1 Mbaud, GPIO6/7), Servo-Strom über den PY32-IO-Expander, gedämpfter Bewegungs-Nachführer, Emotions-Gesten, Gesichtssuche und Ruhe |
| `boards/m5stack/core-s3/face_tracker.h` | **Neu.** esp-dl-Gesichtserkennung (MSR+MNP) auf Kamerabildern mit ~2,5 fps, das größte Gesicht geht an den Kopf |
| `boards/m5stack/core-s3/m5stack_core_s3.cc` | Startet Kopf und Face-Tracker, Display wird nie gedimmt oder abgeschaltet |
| `boards/common/esp_video.*` | `Peek()` für Rohbild-Zugriff, Mutex gemeinsam mit dem Foto-Tool |
| `boards/common/board.h`, `application.cc` | `OnEmotion()`-Hook, damit Server-Emotionen beim Board ankommen |
| `display/lcd_display.cc` | Dunkles Theme fest eingestellt |
| `main/CMakeLists.txt` | Nutzt das GIF-Emoji-Set (ersetzt durch die Cyan-Augen) |
| `idf_component.yml` | Fügt `espressif/human_face_detect` hinzu |
| `partitions/v2/16m_vinci.csv`, `config.json` | Größere App-Partitionen (Gesichtsmodell), USB-Serial-Konsole |

## Einrichtung

### 0. Stock-Firmware sichern

Halte dir einen Weg zurück offen. Roboter per USB anschließen:

```bash
python -m esptool --chip esp32s3 -p <PORT> read-flash 0 0x1000000 stackchan_stock_backup.bin
```

### 1. Server

Du brauchst einen Rechner mit Docker, den der Roboter erreicht (Homeserver, NAS, VPS).

```bash
cd server
cp .env.example .env      # Keys eintragen
docker compose up -d --build
```

| Variable | Pflicht | Bedeutung |
|---|---|---|
| `GEMINI_API_KEY` | ja | API-Key aus Google AI Studio |
| `HA_MCP_TOKEN` | ja | Home-Assistant-Langzeit-Zugriffstoken |
| `HA_WS_URL` | ja | Home-Assistant-WebSocket, z. B. `wss://ha.example.com/api/websocket` |
| `LOCAL_HOST` | LAN-Betrieb | Server-IP, zu der sich der Roboter verbinden soll |
| `PUBLIC_WS_URL` | Proxy-Betrieb | Vollständige WebSocket-URL, wenn der Server hinter TLS liegt, z. B. `wss://stackchan.example.com/xiaozhi/ws` |
| `SYSTEM_PROMPT` | nein | Persönlichkeit der Assistentin |
| `GEMINI_MODEL`, `GEMINI_VOICE` | nein | Standard: `gemini-2.5-flash-native-audio-latest`, `Aoede` |
| `TAVILY_API_KEY`, `N8N_URL`, `N8N_API_KEY` | nein | Aktivieren Websuche und n8n-Status-Tool |

Der Server lauscht auf Port `12800`.

> **Sicherheit:** Der Server hat **keine eigene Authentifizierung**. Wer `/xiaozhi/ws` erreicht, kann mit deiner Assistentin sprechen (und damit Home Assistant steuern); wer `/vinci/say` oder `/vinci/push` erreicht, kann den Roboter sprechen lassen. Betreib ihn im LAN oder hinter einem Reverse-Proxy bzw. Tunnel mit Authentifizierung (z. B. zugriffsgeschützter Tunnel, VPN, Proxy mit Auth). Port 12800 nie direkt ins Internet freigeben.

Die Persona ("Vinci", österreichisches Deutsch) ist die des Autors. `SYSTEM_PROMPT` überschreibt den Haupt-Prompt; die Prompts für Briefing und proaktives Sprechen sowie einige Tool-Beschreibungen stehen in `server/Dockerfile` (Suche nach `sysHint`, `vinciProactiveHint`) und nennen den Autor beim Namen, die also für dich anpassen.

### 2. Firmware

In einer Shell mit geladenem ESP-IDF (getestet mit v6.1):

```bash
cd firmware
./build.sh                                  # deutsches UI, Wake-Word "Jarvis"
LANG_CODE=en-US ./build.sh                  # englisches UI
WAKE_WORD=wn9_hiesp ./build.sh              # anderes esp-sr-Wake-Word
```

### 3. Flashen

Der Patch bringt eine eigene Partitionstabelle mit, daher schreibt der **erste** Flash alles:

```bash
cd firmware/build-work
idf.py -p <PORT> flash
```

Spätere Updates brauchen nur die App:

```bash
python -m esptool --chip esp32s3 -p <PORT> write-flash 0x20000 build/xiaozhi.bin
```

Nach dem Flashen **den Power-Knopf drücken**; nach einem USB-Reset bleibt der Roboter aus.

### 4. Roboter auf deinen Server zeigen lassen

Die Firmware liest die Server-Adresse aus dem NVS (Namespace `wifi`, Key `ota_url`). Einmalig schreiben:

```bash
cat > nvs.csv <<EOF
key,type,encoding,value
wifi,namespace,,
ota_url,data,string,http://<SERVER-IP>:12800/xiaozhi/ota/
EOF
python $IDF_PATH/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py generate nvs.csv nvs.bin 0x4000
python -m esptool --chip esp32s3 -p <PORT> write-flash 0x9000 nvs.bin
```

Das ersetzt die ganze NVS-Partition: WLAN-Zugangsdaten sind weg (der Roboter öffnet beim nächsten Start seinen Einrichtungs-Hotspot) und die Servo-Kalibrierung fällt auf die Standardwerte zurück (Yaw 460, Pitch 620). [rudylls `flash_nvs.py`](https://github.com/rudyll/stackchan_ha_addons) macht dasselbe interaktiv.

### 5. Home Assistant (optional, proaktives Sprechen)

`homeassistant/configuration.yaml` in deine Konfiguration übernehmen (`STACKCHAN_SERVER` ersetzen), Home Assistant neu starten, dann Automationen wie in `homeassistant/automations.yaml` bauen:

```yaml
action: rest_command.stackchan_say
data:
  occasion: "In 30 Minuten: Zahnarzt"
```

## Kalibrierung

Alle Stellschrauben sind Konstanten oben in `head_motion.h`:

| Konstante | Standard | Wirkung |
|---|---|---|
| `kMaxDegPerSec` | 25 | Höchstgeschwindigkeit des Kopfes. Kleiner = ruhiger |
| `kMaxDegPerSec2` | 80 | Beschleunigungsgrenze, hält das Anfahren weich |
| `kOmega` | 4 | Steifigkeit des Nachführers (20° in ~1,7 s, ohne Überschwingen) |
| `kYawMax`, `kPitchMax` | 70, 65 | Bewegungsbereich in Grad (Pitch 0 = tiefste Stellung) |
| `kTrackSignX`, `kTrackSignY` | -1, 1 | Umdrehen, wenn sich der Kopf von deinem Gesicht **wegdreht** (das Kamerabild des CoreS3 ist gespiegelt) |
| `kFaceMemoryMs` | 4000 | Wie lange ein verlorenes Gesicht gehalten wird, bevor er sucht |
| `kSearch[]`, `kSearchDwellMs` | ±20/40/60°, 2000 | Suchpositionen rund um die letzte bekannte Stelle, Standzeit pro Position |
| `kTrackGain` | 0,6 | Welcher Anteil der Abweichung pro Bild korrigiert wird |

Im seriellen Log steht alle fünf Sekunden `FaceTracker: face dx=.. dy=.. yaw=.. pitch=..`, solange ein Gesicht erkannt wird: wird `|dx|` größer, während sich der Kopf bewegt, stimmt das Vorzeichen nicht. Zeilen mit `HeadMotion: search ...` / `found face ...` zeigen die Suche.

Die Ruhe-Neigung (45°) passt für einen Roboter auf dem Schreibtisch, der zu einer sitzenden Person hochschaut. Steht deiner auf Augenhöhe, die Pitch-Werte in `head_motion.h` senken.

Die Erkennungsschwellen sind in `face_tracker.h` auf 0,25 (MSR) / 0,3 (MNP) gesenkt: Beim Blick von Tischhöhe nach oben erkannten die Standardwerte (0,5) nur ~7 % der Bilder, die gesenkten ~81 %, bei Endbewertungen weiterhin um 0,9 bis 1,0.

Die Servo-Nullpositionen kommen aus NVS `servo/zero_pos_1` und `servo/zero_pos_2`, so wie sie die Kalibrierung der Stock-Firmware geschrieben hat.

## Verhalten

| Situation | Kopf |
|---|---|
| Nach dem Start | Ein Suchdurchgang nach einem Gesicht (~30 s) |
| Gesicht im Bild | Folgt deinem Gesicht (Totzone gegen Zucken) |
| Gesicht 4 s verloren | Ein Suchdurchgang, zuerst nahe der letzten Position, dann nach außen |
| Suche erfolglos | Ruht und schaut dorthin, wo du zuletzt warst; kein Suchen die ganze Nacht |
| Wake-Word oder proaktives Sprechen | Startet einen neuen Suchdurchgang, wenn kein Gesicht im Bild ist |
| happy / laughing / loving | Sanftes Nicken |
| sad / sleepy | Kopf senken |
| surprised | Kopf heben |
| thinking / confused | Schaut seitlich nach oben |
| angry | Langsames Kopfschütteln |

## Hardware-Hinweise

- Servos: 2x Feetech SCS0009 an UART1 mit 1 Mbaud, TX GPIO6, RX GPIO7, ID 1 = Yaw, ID 2 = Pitch, 0,3125° pro Schritt.
- Servo-Strom: PY32-IO-Expander an I²C `0x6F`, Pin 0 (VM EN).
- Kamera: GC0308, 320x240 YUV422.

Quelle für die Belegung: M5Stacks offizielles [StackChan-BSP](https://github.com/m5stack/StackChan-BSP).

## Danksagung und Lizenzen

- [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32), MIT
- [rudyll/stackchan_ha_addons](https://github.com/rudyll/stackchan_ha_addons), MIT
- [m5stack/StackChan-BSP](https://github.com/m5stack/StackChan-BSP), MIT (Referenz für Pinbelegung und Servo-Protokoll)
- [espressif/esp-dl](https://github.com/espressif/esp-dl) und `human_face_detect`, über die ESP Component Registry
- Augen-Stil inspiriert von den esp32-eyes-Projekten

Dieses Repository: MIT, siehe [LICENSE](LICENSE).
