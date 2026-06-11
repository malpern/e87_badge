---
title: Home
layout: default
nav_order: 1
---

# e87_badge
{: .fs-9 }

Drive the round **E-Badge E87 / L8** Bluetooth pin from your own code — the badge that normally only talks to the Zrun app.
{: .fs-6 .fw-300 }

[Get started](getting-started){: .btn .btn-primary .fs-5 .mb-4 .mb-md-0 .mr-2 }
[⚡ Instant switching](instant-switching){: .btn .fs-5 .mb-4 .mb-md-0 .mr-2 }
[Source on GitHub](https://github.com/malpern/e87_badge){: .btn .fs-5 .mb-4 .mb-md-0 }

---

## What it does

A small async Python library (+ CLI, + Home Assistant integration) that connects to the badge over BLE, runs the JieLi mutual-auth handshake, and pushes content to the 368×368 round screen.

- 🖼️ **Static images** — JPEG/PNG, auto-fit to the round display
- 📝 **Rendered text** — any size and colour
- 🎞️ **Slideshows** — multiple images as an MJPG-AVI
- 🖼️ **Animated GIFs** — looped on-device
- 🧧 **Danmaku** — scrolling text
- ⚡ **Instant asset switching** *(experimental)* — preload several assets once, then flip between them with one tiny command instead of re-uploading. [Read the guide →](instant-switching)

## 30-second taste

```python
import asyncio
from e87_badge import E87Client

async def main():
    async with E87Client("46:8B:00:01:83:9C") as badge:
        await badge.send_text("Hello", size=96, colour="white")

asyncio.run(main())
```

```console
$ e87 discover
$ e87 image my-photo.png
$ e87 gif pulse.gif
```

## How it came to be

The protocol was recovered by capturing BLE traffic and decompiling the Zrun APK's bundled JieLi watch SDK, then re-implemented cleanly in Python. The full wire-level write-up — every frame, the auth cipher, the upload state machine, and the newly-discovered switch commands — lives in the [Protocol reference](protocol).

{: .note }
> The instant-switching feature is **experimental and reverse-engineered**; whether a given badge's firmware implements it can be confirmed with `e87 probe`. See [Is my badge supported?](instant-switching#is-my-badge-supported)
