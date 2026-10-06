# Contributing

Thanks for wanting to help. This project turns the M5Stack StackChan into a self-hosted voice robot, and most of what it can do came from trying things on a real device. You don't need to know the whole codebase to help.

New here? Look for issues labelled [`good first issue`](../../issues?q=is%3Aopen+label%3A%22good+first+issue%22). Issues and pull requests in English or German are both fine.

## Ways to help

- **Try it on your StackChan** and report what happens, good or bad. Every board revision, camera and Wi-Fi setup we hear about makes the build more reliable.
- **Fix or improve the firmware** (head motion, face tracking, display, audio).
- **Improve the server** (Gemini Live, Home Assistant tools, proactive speech).
- **Docs and translations**, Home Assistant examples, new eye animations.

## How the repo works

Nothing upstream is vendored. Both halves are patches against pinned upstream commits:

| Part | Upstream | Pin | Where the changes live |
|---|---|---|---|
| Firmware | [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) | `UPSTREAM_COMMIT` in `firmware/build.sh` | `firmware/xiaozhi-esp32.patch` |
| Server | [rudyll/stackchan_ha_addons](https://github.com/rudyll/stackchan_ha_addons) | `ARG UPSTREAM_COMMIT` in `server/Dockerfile` | inline in `server/Dockerfile` (heredocs, `patch -p1`, `awk`) |

Bumping a pin is a change of its own: open a pull request just for that and say what you re-tested. An unpinned upstream once broke proactive speech on a plain redeploy.

## Firmware changes

You need ESP-IDF v6.1 (see the README).

1. Build once, this creates the working tree:
   ```bash
   cd firmware
   ./build.sh
   ```
2. Edit the sources in `firmware/build-work/` (a git checkout of upstream with the patch applied) and rebuild with `idf.py build` there.
3. Turn your changes back into the patch:
   ```bash
   cd firmware/build-work
   git add -N main/path/to/new_file.h      # only for new files
   git diff HEAD > ../xiaozhi-esp32.patch
   ```
4. Check that the patch still applies to a clean upstream:
   ```bash
   rm -rf /tmp/check && git clone -q https://github.com/78/xiaozhi-esp32.git /tmp/check
   git -C /tmp/check checkout -q <UPSTREAM_COMMIT>
   git -C /tmp/check apply --check "$PWD/../xiaozhi-esp32.patch" && echo ok
   ```

Settings that must survive a fresh build go into `sdkconfig_append` in `main/boards/m5stack/core-s3/config.json`, not only into your local `sdkconfig`.

Please flash and run your change on a real StackChan before opening the pull request, and say in the description what you tested and for how long. Motion and tracking changes need a few minutes of real use; stability changes need hours.

## Server changes

All server code is in `server/Dockerfile`. Build and run it locally:

```bash
cd server
cp .env.example .env      # fill in your keys
docker compose up --build
```

A patch step that no longer matches upstream fails the build, which is intended. If you add Go code, run `gofmt` on it before pasting it into the heredoc.

## Pull requests

- One topic per pull request. Small is better than complete.
- Describe the behaviour before and after, and how you tested it on the device.
- Keep comments in the code short and explain *why*, like the existing ones (`// vinci: ...`).
- Never commit secrets: no API keys, tokens, Wi-Fi passwords, server addresses or personal names in code, logs or screenshots.

## Reporting bugs

Use the bug report template. The most useful things to attach:

- The serial log (`idf.py -p <PORT> monitor` or any serial terminal on the USB port).
- After a reboot or freeze, the crash report from the coredump partition:
  ```bash
  python -m esptool --chip esp32s3 -p <PORT> read-flash 0xe00000 0x10000 core.bin
  esp-coredump info_corefile -t raw -c core.bin build/xiaozhi.elf
  ```
  It only decodes with the `xiaozhi.elf` of the build that is running on the robot.

Reading the coredump resets the robot; press the power button afterwards.

## License

By contributing you agree that your contribution is released under the [MIT License](LICENSE) of this repository.
