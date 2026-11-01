# StackChan カスタムファームウェア + サーバー

[English](README.md) | [Deutsch](README.de.md) | **日本語**

**M5Stack StackChan**（スタックチャン。CoreS3 と Feetech SCS0009 サーボ2個）向けのカスタムファームウェアと、自分で動かす音声サーバーです。純正のファームウェアとメーカーのクラウドを、次のものに置き換えます。

- **自分のサーバー**（Docker・どのホストでも）：リアルタイムの音声に Google Gemini Live、Home Assistant の操作、予定の案内、任意で Web 検索と n8n の状態。
- **落ち着いていて、生き生きしたロボット**：動くシアンの目、カクつかないやわらかな首の動き、気分に合わせた首のしぐさ、内蔵カメラによる**顔の追跡**。
- **自分から話す**：Home Assistant から、ウェイクワードなしでロボットに話させられます（帰宅、予定、何でも）。

> 状態：個人のプロジェクトです。作者の実機で、顔の追跡も含めて動いています。

## 全体のしくみ

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

1. 起動すると、ロボットはサーバーの OTA エンドポイント（`/xiaozhi/ota/`）に接続先を問い合わせ、websocket の URL を受け取ります。
2. ウェイクワードの後、音声をサーバーへ流します。サーバーは Gemini Live と話し、Home Assistant の操作をツールとして実行します。
3. 返事ごとの感情は、サーバーが自分で選びます。ライブの文字起こしに最初の文がそろった時点で、短いテキストの呼び出しで、その文を21種類の目のアニメーションのどれかに対応づけます（Gemini Live は `set_emotion` ツールを自分からは呼びません）。ファームウェアが目と、それに合う首のしぐさを表示します。
4. Home Assistant が `/vinci/say?occasion=...` を呼ぶと、サーバーが Gemini で短い文を書き、音声にしてロボットで再生します。

## リポジトリの構成

| パス | 中身 |
|---|---|
| `firmware/xiaozhi-esp32.patch` | 固定した [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) のコミットに対する、ファームウェアの変更のすべて |
| `firmware/build.sh` | 上流をクローンし、パッチを当て、目を入れてビルドします |
| `firmware/eyes/` | `make_eyes.py`（目のアニメーションの生成器・Pillow）と、生成した GIF |
| `server/Dockerfile` | サーバーのすべて：[rudyll/stackchan-ai-server](https://github.com/rudyll/stackchan-ai-server) を固定したコミット（`UPSTREAM_COMMIT`）で取得し、サーバーのパッチをすべてその場で当てます。固定を上げる時は意図して行い、`/vinci/say` を試し直してください：固定していなかった上流の変更で、ただ再デプロイしただけで自分から話す機能が壊れたことがあります |
| `server/docker-compose.yml`、`server/.env.example` | Docker が動く所なら、どこでも動かせます |
| `homeassistant/` | 自分から話すための `rest_command` と、自動化の例 |

### 目の色を選ぶ

コミット済みの目のアニメーションはシアンです。別の RGB の色で作り直すには、次を実行します。

```bash
python firmware/eyes/make_eyes.py firmware/eyes/gifs --colour "#FF8800"
```

これで `firmware/eyes/gifs` の GIF が置き換わります。`--colour` を付けなければ、既定のシアンを作り直します。

### ファームウェアのパッチが変える所

| ファイル | 変更 |
|---|---|
| `boards/m5stack/core-s3/head_motion.h` | **新規。** サーボのドライバー（UART1・1 Mbaud・GPIO6/7）、PY32 IO エキスパンダー経由のサーボの電源、減衰つきの動きの追従、感情のしぐさ、顔の探索と休止 |
| `boards/m5stack/core-s3/face_tracker.h` | **新規。** カメラの画像に対する esp-dl の顔検出（MSR+MNP・約2.5 fps）で、いちばん大きい顔を首に渡します。サーバーへの接続・切断のたびに、その前後15秒は止めます：チャンネルの接続中に esp-dl の TIE728 カーネルが落ちた（IllegalInstruction）ためです |
| `boards/m5stack/core-s3/m5stack_core_s3.cc` | 首と顔の追跡を起動し、画面を暗くしたり消したりしません |
| `boards/common/esp_video.*` | 生のフレームを読む `Peek()`、写真ツールと共有するミューテックス |
| `boards/common/board.h`、`application.cc` | `OnEmotion()` のフックで、サーバーの感情をボードに届けます。待機中もサーバーとの接続を開いたままにします（上流はウェイクワードの時しか接続しないので、起動するたびに、自分から話す機能が 503 で失敗していました）。サーバーがチャンネルを閉じた3秒後から、最大10分まで間隔を広げながら黙って再試行します。返事のないまま20秒聞き続けたら会話を終えます（サーバーの音量による待機タイムアウトも、端末の VAD も、オフィスを静かだと判断したことがありませんでした）。チャンネルが開いたら、すぐに古いエラーの文字を消します（WebSocket のプロトコルは `OnConnected` を呼ばないので、「Error」や「Listening」が画面に残っていました） |
| `display/lcd_display.cc` | ダークテーマに固定。LVGL のタスクはコア0 |
| `audio/audio_service.cc`、`audio/engines/afe_audio_engine.cc` | Opus のコーデックとウェイクワードの AFE をコア0に固定し、コア1を顔検出のために空けます（「既知の問題」を参照） |
| `main/CMakeLists.txt` | GIF の絵文字のセットを使います（シアンの目に置き換え済み） |
| `idf_component.yml`、`main/CMakeLists.txt` | `espressif/human_face_detect` を追加。`espcoredump` で、クラッシュの記録を coredump のパーティションに残します（読み解くには、同じビルドの `xiaozhi.elf` を使います） |
| `partitions/v2/16m_vinci.csv`、`config.json` | アプリのパーティションを大きく（顔のモデルのため）、USB シリアルのコンソール、coredump をフラッシュへ、lwIP の `tcpip` タスクをコア0に、CPU を 160 MHz に |

## セットアップ

### 0. 純正のファームウェアをバックアップする

戻れる道を残しておきます。ロボットを USB でつないだ状態で：

```bash
python -m esptool --chip esp32s3 -p <PORT> read-flash 0 0x1000000 stackchan_stock_backup.bin
```

### 1. サーバー

ロボットから届くマシン（家庭のサーバー、NAS、VPS）と、そこで動く Docker が要ります。

```bash
cd server
cp .env.example .env      # fill in the keys
docker compose up -d --build
```

| 変数 | 必須 | 意味 |
|---|---|---|
| `GEMINI_API_KEY` | はい | Google AI Studio の API キー |
| `HA_MCP_TOKEN` | はい | Home Assistant の長期アクセストークン |
| `HA_WS_URL` | はい | Home Assistant の websocket。例：`wss://ha.example.com/api/websocket` |
| `LOCAL_HOST` | LAN で使う時 | ロボットが接続するサーバーの IP |
| `PUBLIC_WS_URL` | プロキシの後ろに置く時 | サーバーが TLS の後ろにある時の、websocket の完全な URL。例：`wss://stackchan.example.com/xiaozhi/ws` |
| `SYSTEM_PROMPT` | いいえ | アシスタントの性格 |
| `GEMINI_MODEL`、`GEMINI_VOICE` | いいえ | 既定値：`gemini-2.5-flash-native-audio-latest`、`Aoede` |
| `TAVILY_API_KEY`、`N8N_URL`、`N8N_API_KEY` | いいえ | Web 検索と n8n の状態のツールを有効にします |
| `CONVERSATION_IDLE_SECONDS` | いいえ | サーバー側の待機タイムアウト。既定は `0`（オフ）。オフのままにしてください：これはチャンネル全体を閉じますが、ファームウェアは自分から話すためにチャンネルを開いたままにしています。静かになった会話は、ファームウェアが自分で終えます |

サーバーはポート `12800` で待ち受けます。

> **セキュリティ：** サーバー自体には**認証がありません**。`/xiaozhi/ws` に届く人は誰でもアシスタントと（つまり Home Assistant とも）話せ、`/vinci/say` や `/vinci/push` に届く人は誰でもロボットに話させられます。LAN の中に置くか、認証のあるリバースプロキシやトンネル（アクセス制御つきのトンネル、VPN、認証つきのプロキシなど）の後ろに置いてください。ポート 12800 をインターネットに直接さらさないでください。

アシスタントの人格（「Vinci」・オーストリアのドイツ語）は作者のものです。`SYSTEM_PROMPT` で主なプロンプトを上書きできます。予定の案内と自分から話す時のプロンプト、一部のツールの説明は `server/Dockerfile` にあり（`sysHint`・`vinciProactiveHint` で検索できます）、作者の名前が入っているので、自分用に直してください。

### 2. ファームウェア

ESP-IDF を読み込んだシェルで（v6.1 で確認済み）：

```bash
cd firmware
./build.sh                                  # German UI, wake word "Jarvis"
LANG_CODE=en-US ./build.sh                  # English UI
WAKE_WORD=wn9_hiesp ./build.sh              # other esp-sr wake word
```

### 3. 書き込み

パッチは独自のパーティションテーブルを使うので、**最初の**書き込みではすべてを書きます。

```bash
cd firmware/build-work
idf.py -p <PORT> flash
```

その後の更新は、アプリだけで足ります。

```bash
python -m esptool --chip esp32s3 -p <PORT> write-flash 0x20000 build/xiaozhi.bin
```

書き込んだ後は**電源ボタンを押してください**。USB のリセットの後、ロボットは電源が切れたままです。

### 4. ロボットの接続先を自分のサーバーにする

ファームウェアは、サーバーのアドレスを NVS（名前空間 `wifi`・キー `ota_url`）から読みます。一度だけ書き込みます。

```bash
cat > nvs.csv <<EOF
key,type,encoding,value
wifi,namespace,,
ota_url,data,string,http://<SERVER-IP>:12800/xiaozhi/ota/
EOF
python $IDF_PATH/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py generate nvs.csv nvs.bin 0x4000
python -m esptool --chip esp32s3 -p <PORT> write-flash 0x9000 nvs.bin
```

これは NVS のパーティション全体を置き換えます。Wi-Fi の設定は消え（次の起動で、ロボットが設定用のアクセスポイントを開きます）、サーボの校正値は既定値（yaw 460・pitch 620）に戻ります。[rudyll の `flash_nvs.py`](https://github.com/rudyll/stackchan-ai-server) でも、同じことを対話式で行えます。

### 5. Home Assistant（任意・自分から話す機能）

`homeassistant/configuration.yaml` を設定に加え（`STACKCHAN_SERVER` を置き換えます）、Home Assistant を再起動してから、`homeassistant/automations.yaml` にあるような自動化を作ります。

```yaml
action: rest_command.stackchan_say
data:
  occasion: "In 30 minutes: dentist"
```

`rest_command` の `timeout: 30` は残してください：サーバーは Gemini で文を書き、音声にしてから返事をするので、Home Assistant の既定の10秒より長くかかります。カレンダーの予定名には改行が入ることがあるので、テンプレートの中で取り除いてください（`homeassistant/automations.yaml` を参照）。

## 校正

調整できる値は、すべて `head_motion.h` の先頭にある定数です。

| 定数 | 既定値 | 効き目 |
|---|---|---|
| `kMaxDegPerSec` | 25 | 首の最高速度。低いほど落ち着きます |
| `kMaxDegPerSec2` | 80 | 加速度の上限。動き出しをやわらかくします |
| `kOmega` | 4 | 追従の硬さ（20° を約1.7秒で、行き過ぎなしに収めます） |
| `kYawMax`、`kPitchMax` | 70, 65 | 動く範囲（度。pitch 0 がいちばん下） |
| `kTrackSignX`、`kTrackSignY` | -1, 1 | 首が顔から**離れる**向きに回る時は反転します（CoreS3 のカメラの画像は鏡像です） |
| `kFaceMemoryMs` | 4000 | 見失った顔を、探し始める前に覚えておく時間 |
| `kSearch[]`、`kSearchDwellMs` | ±20/40/60°, 2000 | 最後に分かった位置のまわりで探す姿勢と、姿勢ごとに止まる時間 |
| `kTrackGain` | 0.6 | 1フレームで、ずれのどれだけを直すか |

顔が見えている間、シリアルのログに5秒ごとに `FaceTracker: face dx=.. dy=.. yaw=.. pitch=..` が出ます。首が動く間に `|dx|` が大きくなるなら、符号が逆です。`HeadMotion: search ...` / `found face ...` の行で、探す様子が分かります。

休む時の pitch（45°）は、机の上のロボットが、座っている人を見上げる置き方に合わせています。目の高さに置くなら、`head_motion.h` の pitch の値を下げてください。

検出のしきい値は、`face_tracker.h` で 0.25（MSR）／0.3（MNP）に下げています：机の高さから見上げると、既定値（0.5）では顔を捉えたのはフレームの約7％、下げた値では約81％で、最終のスコアは 0.9〜1.0 のままでした。

サーボのゼロ位置は、純正のファームウェアの校正が書いた NVS の `servo/zero_pos_1` と `servo/zero_pos_2` から読みます。

## ふるまい

| 状況 | 首 |
|---|---|
| 起動の後 | 顔を1回探します（約30秒） |
| 顔が見えている | 顔を追います（ぴくつかないよう不感帯つき） |
| 顔を4秒見失った | 1回探します。最後の位置の近くから、外へ |
| 探しても誰もいない | いつも人が座る方向（覚えた向き）を向いて休みます。一晩中探し続けることはありません |
| ウェイクワード、または自分から話す時 | 顔が見えていなければ、新しく探し始めます |
| 返事のないまま20秒聞いた | 会話を終え、ウェイクワードの待機に戻ります（接続は開いたまま） |
| happy / laughing / loving | やさしくうなずく |
| sad / sleepy | うつむく |
| surprised | 見上げる |
| thinking / confused | 横の上の方を見る |
| angry | ゆっくり首を振る |

## ハードウェアのメモ

- サーボ：Feetech SCS0009 を2個。UART1・1 Mbaud、TX GPIO6、RX GPIO7、ID 1 = yaw、ID 2 = pitch、1ステップ 0.3125°。
- サーボの電源：I²C `0x6F` の PY32 IO エキスパンダー、ピン0（VM EN）。
- カメラ：GC0308、320x240 YUV422。

ピン配置の出どころ：M5Stack 公式の [StackChan-BSP](https://github.com/m5stack/StackChan-BSP)。

## 既知の問題

- **240 MHz で顔検出が落ちる（回避済み）。** 検出を動かすコアで、esp-dl の TIE728 カーネル（MSR/MNP の段）が、ときどき IllegalInstruction・LoadProhibited・StoreProhibited で落ちます。上流に [esp-dl #337](https://github.com/espressif/esp-dl/issues/337) として報告済みで、これまでの落ち方は、すべて TIE728 の 3x3 depthwise 畳み込みの中でした。その層で esp-dl の C の経路を強制すると落ちなくなりましたが、顔も一切見つからなくなりました。ロボットは約10秒で再起動して、そのまま動き続けます。
  - サーバーへの再接続の前後で検出を止めると、約10分ごとだったのが数時間ごとに減りました。
  - 検出に専用のコアを与える（音声・画面・首・`tcpip` はコア0）と、さらに減りました。ただし直近の週末にも、少なくとも1回は落ちました（何回かは記録していません）。
  - **CPU を 240 MHz でなく 160 MHz で動かす**（チケットで Espressif が提案）と止まりました：240 MHz では長くて約2.5日だったのが、9日間落ちませんでした。ファームウェアの既定は今は 160 MHz（`config.json`）で、顔検出・ウェイクワード・会話は問題なく動きます。
  - 落ちた時の記録を見るには：`esptool.py read_flash 0xe00000 0x10000 core.bin` の後、動いているビルドの ELF で `esp-coredump info_corefile -t raw -c core.bin build/xiaozhi.elf` を実行します。
- **サーバーには Home Assistant が要ります。** サーバーは、ロボットの `hello` に答える前に Home Assistant の WebSocket を開きます。Home Assistant に届かない時は、ロボットに「Error」と出て、Home Assistant が戻ると自分で再接続します。

## 貢献

Issue と pull request は、英語かドイツ語で歓迎します。[CONTRIBUTING.md](CONTRIBUTING.md) に、パッチで成り立つ構成のしくみと、実機での試し方が書いてあります。始めやすいのは、[`good first issue`](../../issues?q=is%3Aopen+label%3A%22good+first+issue%22) の札が付いた Issue です。

## クレジットとライセンス

- [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)、MIT
- [rudyll/stackchan-ai-server](https://github.com/rudyll/stackchan-ai-server)、MIT
- [m5stack/StackChan-BSP](https://github.com/m5stack/StackChan-BSP)、MIT（ピン配置とサーボのプロトコルの参考）
- [espressif/esp-dl](https://github.com/espressif/esp-dl) と `human_face_detect`（ESP component registry 経由）
- 目のデザインは esp32-eyes のプロジェクトを参考にしました

このリポジトリ：MIT。[LICENSE](LICENSE) を参照してください。
