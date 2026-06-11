---
title: Getting started
layout: default
nav_order: 2
---

# Getting started
{: .no_toc }

1. TOC
{:toc}

---

## Install

```bash
pip install git+https://github.com/jumpingmushroom/e87_badge@v0.1.0
```

Requires Python ≥ 3.11. Pulls in `bleak`, `bleak-retry-connector`, and `pillow`.

## Find your badge

Put the badge into **Bluetooth matching mode** (a single short press of the BT button — it shows the QR / pairing screen) and scan:

```console
$ e87 discover
46:8B:00:01:83:9C    E87
```

{: .important }
> The badge is only **connectable while it's in matching mode** (the QR-code screen) — not while it's displaying an image. After any failed pairing, **power-cycle the badge** before retrying; it holds stale connection state for ~3 minutes otherwise.

## Send something

```console
$ e87 image my-photo.png  --address 46:8B:00:01:83:9C
$ e87 text "Hi!" --size 96 --colour white
$ e87 slideshow a.png b.png c.png --ms 600
$ e87 gif pulse.gif
$ e87 danmaku "Welcome!" --fg red --bg black
```

Omit `--address` to auto-discover the first badge.

## Library API

```python
import asyncio
from e87_badge import E87Client

async def main():
    async with E87Client("46:8B:00:01:83:9C") as badge:
        await badge.send_image("welcome.png")
        await badge.send_text("Hi")
        await badge.send_slideshow(["a.png", "b.png", "c.png"], frame_ms=500)
        await badge.send_gif("party.gif")
        await badge.send_danmaku("breaking news!", fg="red", bg="black")

asyncio.run(main())
```

`E87Client` accepts either a MAC-address string **or** a pre-resolved `bleak.BLEDevice` (the form Home Assistant uses to route through whichever Bluetooth proxy is closest).

Every `send_*` call returns the **device-side path** the asset was stored under — the handle you reuse for [instant switching](instant-switching).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Won't connect / `BleakDeviceNotFound` | Get the badge onto the **QR-code screen**; it only advertises there. |
| Connects then aborts at "initial window ack" | Normal on the first attempt — retry. Don't press any badge button mid-upload. |
| Stuck, won't pair for minutes | **Power-cycle** the badge (hold power ~10 s). One clean attempt per power-cycle. |
| Weak/slow transfer | Keep the badge within ~1 m of the radio. |
