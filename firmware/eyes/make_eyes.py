#!/usr/bin/env python3
"""Generate cyan Cozmo-style eye animations for Vinci.

One rounded rectangle per eye, drawn per frame from a small parameter set --
the same idea as playfultechnology/esp32-eyes, but rendered ahead of time into
GIFs because the xiaozhi firmware displays images, not drawing code.

Output is 320x240 (full screen, unlike the 240x240 otto set that left bars on
the sides) with a black background so it blends into the dark theme.
"""
import math
import os
import sys

from PIL import Image, ImageDraw

W, H = 320, 240
BG = (0, 0, 0)
CYAN = (0, 229, 255)
CYAN_DIM = (0, 150, 180)

# Eye geometry at rest
EYE_W, EYE_H = 78, 96
GAP = 44                      # space between the two eyes
CX = W // 2
CY = H // 2


def rounded_eye(img, d, cx, cy, w, h, radius, colour, tilt=0.0, curve=0.0):
    """Draw one eye.

    tilt  : degrees, positive = inner edge down (angry), negative = sad
    curve : 0..1, how much the eye becomes a bottom-arc ("happy" squint)
    """
    if h < 4:
        h = 4
    if curve > 0:
        # Happy eyes: only the lower arc of a circle, like an upturned smile.
        arc_h = int(h * (1.0 - curve) + 8)
        box = [cx - w // 2, cy - arc_h, cx + w // 2, cy + arc_h]
        d.pieslice(box, start=180, end=360, fill=colour)
        return

    layer = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    r = min(radius, w // 2, h // 2)
    ld.rounded_rectangle([20, 20, 20 + w, 20 + h], radius=r, fill=colour + (255,))
    if tilt:
        layer = layer.rotate(tilt, resample=Image.BICUBIC, expand=False)
    img.paste(layer, (cx - (w + 40) // 2, cy - (h + 40) // 2), layer)


def heart(d, cx, cy, size, colour):
    pts = []
    for i in range(0, 360, 4):
        t = math.radians(i)
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t)
              - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * size / 16.0, cy + y * size / 16.0))
    d.polygon(pts, fill=colour)


def frame(params):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    lx = CX - GAP // 2 - EYE_W // 2 + params.get("dx", 0)
    rx = CX + GAP // 2 + EYE_W // 2 + params.get("dx", 0)
    cy = CY + params.get("dy", 0)

    colour = params.get("colour", CYAN)
    lw = int(EYE_W * params.get("sx", 1.0))
    lh = int(EYE_H * params.get("sy", 1.0))
    rw = int(EYE_W * params.get("sx_r", params.get("sx", 1.0)))
    rh = int(EYE_H * params.get("sy_r", params.get("sy", 1.0)))
    radius = params.get("radius", 26)
    tilt = params.get("tilt", 0.0)
    curve = params.get("curve", 0.0)

    if params.get("hearts"):
        heart(d, lx, cy, params.get("heart_size", 80), colour)
        heart(d, rx, cy, params.get("heart_size", 80), colour)
        return img

    rounded_eye(img, d, lx, cy, lw, lh, radius, colour, tilt=tilt, curve=curve)
    rounded_eye(img, d, rx, cy, rw, rh, radius, colour, tilt=-tilt, curve=curve)
    return img


def blink_seq(base, hold=6, closed=1):
    """A resting loop with an occasional blink."""
    out = [dict(base) for _ in range(hold)]
    for s in (0.55, 0.18):
        f = dict(base)
        f["sy"] = base.get("sy", 1.0) * s
        f["sy_r"] = base.get("sy_r", base.get("sy", 1.0)) * s
        out.append(f)
    out += [dict(base) for _ in range(closed)]
    for s in (0.18, 0.55):
        f = dict(base)
        f["sy"] = base.get("sy", 1.0) * s
        f["sy_r"] = base.get("sy_r", base.get("sy", 1.0)) * s
        out.append(f)
    return out


def sway(base, amp=10, steps=8, axis="dx"):
    out = []
    for i in range(steps):
        f = dict(base)
        f[axis] = int(amp * math.sin(2 * math.pi * i / steps))
        out.append(f)
    return out


def pulse(base, lo=0.88, hi=1.06, steps=8):
    out = []
    for i in range(steps):
        k = lo + (hi - lo) * (0.5 + 0.5 * math.sin(2 * math.pi * i / steps))
        f = dict(base)
        f["sx"] = base.get("sx", 1.0) * k
        f["sy"] = base.get("sy", 1.0) * k
        f["sx_r"] = f["sx"]
        f["sy_r"] = f["sy"]
        out.append(f)
    return out



def _hold(base, n, **over):
    f = dict(base)
    f.update(over)
    return [dict(f) for _ in range(n)]


def _blink(base, fast=False):
    """One blink. fast=True is a quick flick, otherwise a softer close."""
    steps = (0.62, 0.3, 0.12) if fast else (0.85, 0.65, 0.45, 0.25, 0.1)
    out = []
    for s in steps:
        f = dict(base)
        f["sy"] = base.get("sy", 1.0) * s
        f["sy_r"] = base.get("sy_r", base.get("sy", 1.0)) * s
        out.append(f)
    out.append({**base, "sy": base.get("sy", 1.0) * 0.1,
                "sy_r": base.get("sy_r", base.get("sy", 1.0)) * 0.1})
    for s in reversed(steps):
        f = dict(base)
        f["sy"] = base.get("sy", 1.0) * s
        f["sy_r"] = base.get("sy_r", base.get("sy", 1.0)) * s
        out.append(f)
    return out


def _ease(t):
    """Smoothstep: slow at both ends, quick through the middle."""
    return t * t * (3.0 - 2.0 * t)


def _glance(base, target, hold=6, step=9):
    """Look toward `target` px, linger, come back -- eased, not linear."""
    out = []
    for i in range(1, step + 1):
        out.append({**base, "dx": int(target * _ease(i / step))})
    out += _hold(base, hold, dx=target)
    for i in range(step - 1, 0, -1):
        out.append({**base, "dx": int(target * _ease(i / step))})
    return out


def idle_loop():
    """A long, non-repetitive resting animation.

    ponytail: baked into the GIF instead of driven from the server -- no
    protocol, no open session, and it keeps working when Vinci is offline.
    """
    b = {}
    seq = []
    seq += _hold(b, 28)
    seq += _blink(b)
    seq += _hold(b, 20)
    seq += _glance(b, 26, hold=16)          # look right
    seq += _hold(b, 12)
    seq += _blink(b, fast=True)
    seq += _hold(b, 24)
    seq += _glance(b, -26, hold=16)         # look left
    seq += _hold(b, 16)
    seq += _blink(b)
    seq += _blink(b, fast=True)            # double blink
    seq += _hold(b, 32)
    seq += _hold(b, 10, dy=-10, sy=0.92)    # glance up, thinking for a beat
    seq += _hold(b, 12, dy=-12, sy=0.9)
    seq += _hold(b, 10, dy=-6, sy=0.96)
    seq += _hold(b, 24)
    seq += _blink(b)
    seq += _hold(b, 18)
    seq += _glance(b, 14, hold=10)          # small glance right
    seq += _hold(b, 36)
    seq += _hold(b, 6, sy=1.05, sx=1.03)   # tiny "breath"
    seq += _hold(b, 6, sy=0.97, sx=0.99)
    seq += _hold(b, 28)
    seq += _blink(b, fast=True)
    seq += _hold(b, 40)
    return seq


# name -> (frames, per-frame duration ms)
def build():
    E = {}

    E["neutral"] = (idle_loop(), 55)
    E["happy"] = (blink_seq({"curve": 0.75, "sy": 1.1}, hold=8), 60)
    E["laughing"] = (sway({"curve": 0.8, "sy": 1.15}, amp=0, steps=2)
                     + [{"curve": 0.8, "sy": 0.9}, {"curve": 0.8, "sy": 1.2}] * 3, 90)
    E["funny"] = (sway({"curve": 0.6}, amp=14, steps=10), 45)
    E["silly"] = ([{"sx": 1.0, "sy": 1.0, "sx_r": 0.7, "sy_r": 0.6, "dy": 6},
                   {"sx": 0.7, "sy": 0.6, "sx_r": 1.0, "sy_r": 1.0, "dy": -6}] * 4, 160)
    E["sad"] = (blink_seq({"tilt": -18, "sy": 0.8, "dy": 10}, hold=10), 75)
    E["crying"] = ([{"tilt": -18, "sy": 0.8, "dy": 10 + (i % 3) * 3}
                    for i in range(10)], 130)
    E["angry"] = (blink_seq({"tilt": 20, "sy": 0.62}, hold=10), 70)
    E["surprised"] = ([{"sx": 1.25, "sy": 1.3, "radius": 40}] * 4
                      + [{"sx": 1.1, "sy": 1.15, "radius": 40}] * 4, 120)
    E["shocked"] = (pulse({"sx": 1.3, "sy": 1.35, "radius": 44}, 0.95, 1.12), 45)
    E["thinking"] = (sway({"dy": -12, "sy": 0.85}, amp=16, steps=10), 70)
    E["confused"] = ([{"sx": 1.0, "sy": 1.0, "sx_r": 0.75, "sy_r": 1.15, "tilt": 8,
                       "dx": (i % 3 - 1) * 6} for i in range(9)], 150)
    E["sleepy"] = ([{"sy": s} for s in (0.5, 0.35, 0.22, 0.14, 0.22, 0.35)], 220)
    E["relaxed"] = (blink_seq({"curve": 0.5, "sy": 0.9}, hold=14), 90)
    E["kissy"] = ([{"curve": 0.7, "sx": 0.9}] * 3
                  + [{"sy": 0.2, "sx": 0.9}] * 2
                  + [{"curve": 0.7, "sx": 0.9}] * 3, 140)
    E["loving"] = ([{"hearts": True, "heart_size": s}
                    for s in (74, 82, 90, 96, 90, 82)], 130)
    E["winking"] = ([{"sy": 1.0, "sy_r": 1.0}] * 4
                    + [{"sy": 1.0, "sy_r": 0.15}] * 4, 160)
    E["confident"] = (blink_seq({"sy": 0.72, "tilt": 8}, hold=12), 75)
    E["cool"] = ([{"sy": 0.55, "tilt": 6, "dx": d} for d in (0, 4, 8, 4, 0, -4, -8, -4)], 140)
    E["embarrassed"] = ([{"sy": 0.7, "dy": 12, "dx": d, "colour": CYAN_DIM}
                         for d in (0, -8, -12, -8, 0, 8, 12, 8)], 150)
    E["delicious"] = ([{"curve": 0.7, "sx": 1.05}, {"curve": 0.5, "sx": 1.0},
                       {"sy": 0.25}, {"curve": 0.5, "sx": 1.0}] * 2, 150)
    return E


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    built = build()
    for name, (frames, dur) in built.items():
        imgs = [frame(p) for p in frames]
        pal = [im.convert("P", palette=Image.ADAPTIVE, colors=32) for im in imgs]
        # Per-frame durations: Pillow merges identical frames, and a single
        # duration value would silently shorten the animation when it does.
        pal[0].save(os.path.join(outdir, f"{name}.gif"),
                    save_all=True, append_images=pal[1:],
                    duration=[dur] * len(pal), loop=0,
                    optimize=True, disposal=1)
    print(f"generated {len(built)} eye animations into {outdir}")
    return built


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "eyes_cyan"
    built = main(out)
    # smallest useful check: every emotion the server can send must exist
    need = {"neutral", "happy", "laughing", "funny", "silly", "sad", "crying",
            "angry", "surprised", "shocked", "thinking", "sleepy", "kissy",
            "loving", "winking", "confident", "cool", "embarrassed",
            "confused", "relaxed", "delicious"}
    missing = need - set(built)
    assert not missing, f"missing emotions: {sorted(missing)}"
    print("all 21 server-side emotions covered")
