# StackChan Custom Firmware + Server

**English** | [Deutsch](README.de.md)

Custom firmware and a self-hosted voice server for the **M5Stack StackChan** (CoreS3 with two Feetech SCS0009 servos). It replaces the stock firmware and the vendor cloud with:

- **Your own server** (Docker, any host): Google Gemini Live for real-time voice, Home Assistant control, calendar briefing, optional web search and n8n status.
- **A calmer, livelier robot**: animated cyan eyes, soft head motion with no jerky moves, head gestures that follow the mood, and **face tracking** via the built-in camera.
- **Proactive speech**: Home Assistant can make the robot speak on its own (arrival, calendar, anything), without a wake word.

> Status: personal project, working on the author's device. Face tracking is new and still experimental (see [Calibration](#calibration)).

## How it fits together

```
 StackChan (CoreS3)                    Your server (Docker)                 Cloud / LAN
┌──────────────────────┐  websocket  ┌────────────────────────┐        ┌──────────────────┐
│ xiaozhi-esp32 + patch│◄───────────►│ stackchan-server       │◄──────►│ Gemini Live/TTS  │
│ wake word, mic, amp  │  /xiaozhi/ws│ (rudyll fork + patches)│        └──────────────────┘
│ eyes, servos, camera │             │ /vinci/say  /vinci/push│◄──────►┌──────────────────┐
└──────────────────────┘             └───────────▲────────────┘  ws    │ Home Assistant   │
                                                 └─────────────────────┤ rest_command     │
                                                        HTTP           └──────────────────┘
```

1. On boot the robot asks the server's OTA endpoint (`/xiaozhi/ota/`) where to connect and gets the websocket URL.
2. After the wake word it streams audio to the server; the server talks to Gemini Live and executes Home Assistant actions as tools.
3. The server sends emotions (`{"type":"llm","emotion":"happy"}`); the firmware shows the matching eye animation and head gesture.
4. Home Assistant calls `/vinci/say?occasion=...`; the server writes a short sentence with Gemini, synthesises it and plays it on the robot.

## Repository layout

| Path | What it is |
|---|---|
| `firmware/xiaozhi-esp32.patch` | All firmware changes against a pinned [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) commit |
| `firmware/build.sh` | Clones upstream, applies the patch, drops in the eyes, builds |
| `firmware/eyes/` | `make_eyes.py` (eye animation generator, Pillow) and the generated GIFs |
| `server/Dockerfile` | The complete server: clones [rudyll/stackchan_ha_addons](https://github.com/rudyll/stackchan_ha_addons) and applies all server patches inline |
| `server/docker-compose.yml`, `server/.env.example` | Run it anywhere Docker runs |
| `homeassistant/` | `rest_command` and example automations for proactive speech |

### What the firmware patch changes

| File | Change |
|---|---|
| `boards/m5stack/core-s3/head_motion.h` | **New.** Servo driver (UART1, 1 Mbaud, GPIO6/7), servo power via the PY32 IO expander, damped motion follower, emotion gestures, idle behaviour |
| `boards/m5stack/core-s3/face_tracker.h` | **New.** esp-dl face detection (MSR+MNP) on camera frames at ~5 fps, feeds the largest face to the head |
| `boards/m5stack/core-s3/m5stack_core_s3.cc` | Starts head + face tracker, never dims or powers off the display |
| `boards/common/esp_video.*` | `Peek()` for raw frame access, mutex shared with the photo tool |
| `boards/common/board.h`, `application.cc` | `OnEmotion()` hook so server emotions reach the board |
| `display/lcd_display.cc` | Dark theme pinned |
| `main/CMakeLists.txt` | Uses the GIF emoji set (replaced by the cyan eyes) |
| `idf_component.yml` | Adds `espressif/human_face_detect` |
| `partitions/v2/16m_vinci.csv`, `config.json` | Larger app partitions (face model), USB serial console |

## Setup

### 0. Back up the stock firmware

Keep a way back. With the robot on USB:

```bash
python -m esptool --chip esp32s3 -p <PORT> read-flash 0 0x1000000 stackchan_stock_backup.bin
```

### 1. Server

You need a machine that the robot can reach (home server, NAS, VPS) with Docker.

```bash
cd server
cp .env.example .env      # fill in the keys
docker compose up -d --build
```

| Variable | Required | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | yes | Google AI Studio API key |
| `HA_MCP_TOKEN` | yes | Home Assistant long-lived access token |
| `HA_WS_URL` | yes | Home Assistant websocket, e.g. `wss://ha.example.com/api/websocket` |
| `LOCAL_HOST` | LAN setup | Server IP the robot should connect to |
| `PUBLIC_WS_URL` | proxy setup | Full websocket URL if the server sits behind TLS, e.g. `wss://stackchan.example.com/xiaozhi/ws` |
| `SYSTEM_PROMPT` | no | Personality of the assistant |
| `GEMINI_MODEL`, `GEMINI_VOICE` | no | Defaults: `gemini-2.5-flash-native-audio-latest`, `Aoede` |
| `TAVILY_API_KEY`, `N8N_URL`, `N8N_API_KEY` | no | Enable web search and n8n status tools |

The server listens on port `12800`.

> **Security:** the server has **no authentication** of its own. Anyone who can reach `/xiaozhi/ws` can talk to your assistant (and thereby to Home Assistant), and anyone who can reach `/vinci/say` or `/vinci/push` can make the robot speak. Keep it in your LAN, or put it behind a reverse proxy or tunnel that authenticates (e.g. an access-controlled tunnel, VPN, or proxy with auth). Do not expose port 12800 directly to the internet.

The assistant persona ("Vinci", Austrian German) is the author's. `SYSTEM_PROMPT` overrides the main prompt; the briefing and proactive-speech prompts and some tool descriptions live in `server/Dockerfile` (search for `sysHint`, `vinciProactiveHint`) and mention the author by name, so adjust them for yourself.

### 2. Firmware

In a shell with ESP-IDF loaded (tested with v6.1):

```bash
cd firmware
./build.sh                                  # German UI, wake word "Jarvis"
LANG_CODE=en-US ./build.sh                  # English UI
WAKE_WORD=wn9_hiesp ./build.sh              # other esp-sr wake word
```

### 3. Flash

The patch uses its own partition table, so the **first** flash writes everything:

```bash
cd firmware/build-work
idf.py -p <PORT> flash
```

Later updates only need the app:

```bash
python -m esptool --chip esp32s3 -p <PORT> write-flash 0x20000 build/xiaozhi.bin
```

After flashing, **press the power button**; the robot stays off after a USB reset.

### 4. Point the robot to your server

The firmware reads the server address from NVS (`wifi` namespace, key `ota_url`). Write it once:

```bash
cat > nvs.csv <<EOF
key,type,encoding,value
wifi,namespace,,
ota_url,data,string,http://<SERVER-IP>:12800/xiaozhi/ota/
EOF
python $IDF_PATH/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py generate nvs.csv nvs.bin 0x4000
python -m esptool --chip esp32s3 -p <PORT> write-flash 0x9000 nvs.bin
```

This replaces the whole NVS partition: Wi-Fi credentials are gone (the robot opens its setup hotspot on the next boot) and the servo calibration falls back to the defaults (yaw 460, pitch 620). [rudyll's `flash_nvs.py`](https://github.com/rudyll/stackchan_ha_addons) does the same interactively.

### 5. Home Assistant (optional, proactive speech)

Add `homeassistant/configuration.yaml` to your configuration (replace `STACKCHAN_SERVER`), restart Home Assistant, then build automations like the ones in `homeassistant/automations.yaml`:

```yaml
action: rest_command.stackchan_say
data:
  occasion: "In 30 minutes: dentist"
```

## Calibration

All knobs are constants at the top of `head_motion.h`:

| Constant | Default | Effect |
|---|---|---|
| `kMaxDegPerSec` | 25 | Top head speed. Lower = calmer |
| `kMaxDegPerSec2` | 80 | Acceleration cap, keeps starts soft |
| `kOmega` | 4 | Stiffness of the follower (settles 20° in ~1.7 s, no overshoot) |
| `kYawMax`, `kPitchMax` | 35, 20 | Range of motion in degrees |
| `kTrackSignX`, `kTrackSignY` | 1, 1 | Flip to `-1` if the head turns **away** from your face |
| `kTrackGain` | 0.6 | How much of the offset one frame corrects |

The serial log prints `FaceTracker: face dx=.. dy=..` every two seconds while a face is seen: if `|dx|` grows while the head moves, the sign is wrong.

Servo zero positions come from NVS `servo/zero_pos_1` and `servo/zero_pos_2`, as written by the stock firmware's calibration.

## Behaviour

| Situation | Head |
|---|---|
| Face in view | Follows your face (dead zone against twitching) |
| Idle, nobody there | Looks around slowly every 5 to 14 s |
| Listening | Faces forward, head slightly raised, still |
| Speaking | Small drift |
| happy / laughing / loving | Gentle nod |
| sad / sleepy | Head down |
| surprised | Head up |
| thinking / confused | Looks aside and up |
| angry | Slow head shake |

## Hardware notes

- Servos: 2x Feetech SCS0009 on UART1 at 1 Mbaud, TX GPIO6, RX GPIO7, ID 1 = yaw, ID 2 = pitch, 0.3125° per step.
- Servo power: PY32 IO expander at I²C `0x6F`, pin 0 (VM EN).
- Camera: GC0308, 320x240 YUV422.

Source for the pinout: M5Stack's official [StackChan-BSP](https://github.com/m5stack/StackChan-BSP).

## Credits and licenses

- [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32), MIT
- [rudyll/stackchan_ha_addons](https://github.com/rudyll/stackchan_ha_addons), MIT
- [m5stack/StackChan-BSP](https://github.com/m5stack/StackChan-BSP), MIT (pinout and servo protocol reference)
- [espressif/esp-dl](https://github.com/espressif/esp-dl) and `human_face_detect`, via the ESP component registry
- Eye style inspired by the esp32-eyes projects

This repository: MIT, see [LICENSE](LICENSE).
