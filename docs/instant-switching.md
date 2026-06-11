# Instant Asset Switching

### Flip between preloaded images without re-uploading — a single tiny command instead of a multi-second transfer.

> **Status: tested on E87 firmware `V11.1.0.3` — NOT supported on that firmware.**
> The switch command is real (it's in the device's own SDK), and the badge
> *acknowledges* it at the transport level — but on the firmware we measured it
> replies with RCSP error status `0x02` and the display does **not** change. The
> "watch dial" subsystem this relies on simply isn't wired up in this
> display-badge firmware; the badge always shows the most-recently-uploaded file.
> This page documents the mechanism and how to check your own unit
> (`e87 probe`); **on V11.1.0.3 the answer is no, fall back to re-upload.** Other
> or newer firmware may differ. See [Is my badge supported?](#is-my-badge-supported)

---

## The problem

Uploading to an E87 is not fast. A still image is **5–15 seconds**; an
animation is **30–60 seconds**. That's fine when you set a badge once and walk
away — but it falls apart the moment you want the badge to *react*.

Picture a presence badge for a hackathon demo: an **idle** eye that blinks, and
an **active** eye that locks on when someone walks up. If every state change
means re-encoding and re-streaming a whole GIF, your "reaction" arrives a
minute late. You need switching measured in **milliseconds**, not megabytes.

## The insight

Here's the thing we discovered reading the firmware's SDK: **the badge already
stores every asset you upload as its own persistent file.** When an upload
finishes, the client answers the device's `FILE_COMPLETE` with a path, and the
badge commits the bytes under that name — `啜20260610153000.jpg`, and so on.
They don't overwrite a single slot; they *accumulate*.

So half of "instant switching" already works today. The missing half is simply:

> **"Hey badge — show the file I already gave you."**

That's one command. It carries a filename, not pixels. It's the difference
between mailing a photo and pointing at one already on the wall.

## How it works

The switch rides the exact same FE frame as everything else in the protocol:

```
FE DC BA │ flag │ cmd │ len(2 BE) │ body │ EF
```

with `cmd = 0x1A` (RCSP *External-Flash I/O control*, opcode 26) and a body of:

```
┌──────────┬─────────────────┬──────────────┬─────────────────┐
│ opCodeSn │ op = 0x03       │ flag         │ payload         │
│  (1 B)   │ (DIAL_ACTION)   │ 0x01 = set   │ file path (UTF-8)│
└──────────┴─────────────────┴──────────────┴─────────────────┘
```

The bytes after the sequence number are precisely JieLi's
`ExternalFlashIOCtrlParam.toData() = [op][flag][payload]`. Flag `0x00` *reads*
the current file, `0x01` *switches* to the file named in the payload, and the
device pushes `0x02` when the active file changes on its own.

That's the whole feature. ~tens of bytes, one round-trip, sub-second.

## Your first switch

Preload two assets, then flip between them — no re-upload in sight:

```python
import asyncio
from e87_badge import E87Client

async def main():
    async with E87Client("46:8B:00:01:83:9C") as badge:
        # Upload once. Each call returns the device path it was stored under.
        idle   = await badge.send_gif("idle.gif")
        active = await badge.send_gif("active.gif")
        print("preloaded:", idle, active)

        # Later — and this is the fast part — just point at one:
        await badge.show_file(active)   # locks on, instantly
        await asyncio.sleep(2)
        await badge.show_file(idle)     # back to blinking, instantly

asyncio.run(main())
```

`send_gif` / `send_image` now **return the stored path** (also saved as
`badge.last_path`). Hand that path to `show_file` whenever you like — across
calls, across reconnects, across program runs. The asset lives on the badge.

### A reactive loop

Because each switch is a single command, you can drive the badge from live
events at interactive speed:

```python
async with E87Client(addr) as badge:
    idle   = await badge.send_image("eye_idle.png")
    active = await badge.send_image("eye_active.png")

    async for person_present in presence_events():   # your sensor stream
        await badge.show_file(active if person_present else idle)
```

No encoding, no chunking, no 30-second wait between reactions.

## From the command line

```console
$ e87 image eye_idle.png --address 46:8B:00:01:83:9C
Stored on device as: 啜20260610153000.jpg
Redisplay later with:  e87 show '啜20260610153000.jpg' --address 46:8B:00:01:83:9C

$ e87 image eye_active.png --address 46:8B:00:01:83:9C
Stored on device as: 啜20260610153012.jpg

# now flip between them — each of these is sub-second:
$ e87 show '啜20260610153012.jpg' --address 46:8B:00:01:83:9C
$ e87 show '啜20260610153000.jpg' --address 46:8B:00:01:83:9C

$ e87 current --address 46:8B:00:01:83:9C     # what's on screen now?
啜20260610153000.jpg

$ e87 ls --address 46:8B:00:01:83:9C          # everything stored (experimental)
啜20260610153000.jpg
啜20260610153012.jpg
```

## Is my badge supported?

This is the honest part. We know the **protocol** supports switch-by-reference
— it's right there in the SDK, two independent ways (the RCSP dial action above,
and a `SET_PUSH_DIAL` index command on the legacy channel). What we *can't* know
from static analysis is whether **your specific firmware build** wired those
opcodes up, because the stock Zrun app never sends them to the badge — it
re-uploads on every selection.

So we built a probe. It reads the current file, attempts a listing, and tries a
no-op switch to whatever is already showing — then tells you what answered:

```console
$ e87 probe --address 46:8B:00:01:83:9C     # actual result on V11.1.0.3
{
  "get_using_dial": { "supported": false, "error": "...RCSP status 0x02..." },
  "file_browse":    { "supported": true,  "files": [] },
  "set_using_dial": { "supported": false, "error": "...RCSP status 0x02..." }
}

Instant switching: NOT confirmed on this badge ❌
```

On the unit we measured, `file_browse` is accepted but the dial actions are
rejected — the badge speaks the file protocol but not the "switch displayed
file" command. A firmware that *does* implement it would instead report
`set_using_dial: { "supported": true }`.

Programmatically:

```python
async with E87Client(addr) as badge:
    report = await badge.probe_switching()
    if report["set_using_dial"]["supported"]:
        ...  # use show_file
```

If the probe comes back unsupported, nothing is lost — `show_file` raises
`E87ProtocolError`, and you fall back to the upload path you already have:

```python
from e87_badge import E87ProtocolError

try:
    await badge.show_file(active)
except E87ProtocolError:
    await badge.send_gif("active.gif")   # graceful fallback
```

## Design notes

- **Why a path, not an index?** The RCSP dial action addresses files by name
  in the badge's FAT filesystem, which is exactly what an upload returns. No
  bookkeeping of slot numbers; the path *is* the handle.
- **Sequence numbers.** Switch/query commands carry their own `opCodeSn`,
  managed by the client (`_next_sn`) independently of the upload state machine,
  so you can interleave switches and uploads freely.
- **`current_file()` decoding is liberal.** Firmware responses vary in framing
  (status byte present or not), so the parser pulls the trailing path-like run
  rather than assuming fixed offsets. Treat the result as advisory.
- **`list_files()` is the least-certain piece.** JieLi's file-browse uses a
  separate response encoding we only partially decode. You rarely need it —
  prefer the paths returned by your uploads.

## Under the hood

If you want to build commands yourself, the pure builders are in
[`e87_badge.gallery`](../src/e87_badge/gallery.py):

```python
from e87_badge import gallery

frame = gallery.build_set_using_dial_frame(sn=0x10, path="啜...jpg")
# -> FE DC BA C0 1A <len> 10 03 01 <utf8 path> EF
```

and the protocol provenance — every byte traced back to a decompiled SDK class —
is documented in [`protocol.md`](protocol.md) and the investigation writeup that
accompanies this feature.
