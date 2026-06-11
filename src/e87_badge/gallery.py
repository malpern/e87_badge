"""Instant asset switching — display a *preloaded* file without re-uploading.

.. warning::

   **Experimental / reverse-engineered, not yet confirmed on E87 firmware.**
   These commands were recovered from the Zrun APK's bundled JieLi watch SDK
   (``com.jieli.jl_rcsp``). The badge *speaks* JieLi RCSP over AE01 (its
   file-upload opcodes match the SDK's command registry), and every upload is
   committed as its own persistent file — so the architecture supports
   switch-by-reference. But the stock app never sends these particular opcodes
   to the badge (it re-uploads on every selection), so whether this specific
   firmware implements them can only be settled on hardware. Use
   :func:`probe_switching` (or ``e87 probe``) to find out, and treat a
   :class:`~e87_badge.errors.E87ProtocolError` from these calls as "this unit
   doesn't support it — fall back to re-upload."

Why it matters
--------------
A full image upload is ~5–15 s and an animation ~30–60 s. Switching between
two assets you already pushed should instead be a single ~tens-of-bytes
command — sub-second. That is the difference between "re-send active.gif every
time something happens" and "preload idle + active once, then flip instantly."

The wire format
---------------
The switch rides the same FE frame as the rest of the protocol
(:mod:`e87_badge.frame`)::

    FE DC BA | flag | cmd | len(2 BE) | body | EF

with ``cmd = CMD_EXTERNAL_FLASH_IOCTRL (0x1A / 26)`` and a body of::

    [ opCodeSn ][ op = OP_DIAL_ACTION (3) ][ action flag ][ payload... ]

The bytes after ``opCodeSn`` are exactly JieLi's
``ExternalFlashIOCtrlParam.toData() = [op][flag][payload]``. For a switch the
payload is the target file's path (ASCII/UTF-8); for a query it is empty.
"""

from __future__ import annotations

import logging

from .const import (
    CMD_EXTERNAL_FLASH_IOCTRL,
    CMD_FILE_BROWSE_START,
    CMD_FILE_BROWSE_STOP,
    FLAG_COMMAND,
    FLAG_GET_USING_DIAL,
    FLAG_SET_USING_DIAL,
    OP_DIAL_ACTION,
)
from .errors import E87ProtocolError
from .frame import build_fe_frame
from .notify import NotifyBus, wait_for_frame
from .protocol import Writer

log = logging.getLogger(__name__)


# ── Packet builders (pure, unit-testable) ───────────────────────────────────

def build_dial_action_body(sn: int, action_flag: int, payload: bytes = b"") -> bytes:
    """Return the FE-frame *body* for an External-Flash dial action.

    Layout: ``[opCodeSn, OP_DIAL_ACTION, action_flag, *payload]`` — i.e. the
    sequence byte followed by JieLi's ``ExternalFlashIOCtrlParam.toData()``.
    """
    return bytes((sn & 0xFF, OP_DIAL_ACTION, action_flag & 0xFF)) + bytes(payload)


def build_set_using_dial_frame(sn: int, path: str) -> bytes:
    """Full FE frame that switches the display to the stored file at ``path``."""
    body = build_dial_action_body(sn, FLAG_SET_USING_DIAL, path.encode("utf-8"))
    return build_fe_frame(FLAG_COMMAND, CMD_EXTERNAL_FLASH_IOCTRL, body)


def build_get_using_dial_frame(sn: int) -> bytes:
    """Full FE frame that asks the badge which file is currently displayed."""
    body = build_dial_action_body(sn, FLAG_GET_USING_DIAL)
    return build_fe_frame(FLAG_COMMAND, CMD_EXTERNAL_FLASH_IOCTRL, body)


# ── Async operations ────────────────────────────────────────────────────────

async def set_using_dial(
    write_ae01: Writer,
    bus: NotifyBus,
    sn: int,
    path: str,
    *,
    timeout: float = 8.0,
) -> None:
    """Switch the badge to the already-stored file at ``path`` (no re-upload).

    Raises :class:`E87ProtocolError` if the badge does not acknowledge — which
    on this firmware most likely means the dial-switch opcode is unsupported.
    """
    log.info("Switch display -> %r (cmd 0x%02x, SET_USING_DIAL)", path, CMD_EXTERNAL_FLASH_IOCTRL)
    await write_ae01(build_set_using_dial_frame(sn, path))
    try:
        ack = await wait_for_frame(
            bus,
            lambda f: f.cmd == CMD_EXTERNAL_FLASH_IOCTRL,
            timeout=timeout,
            label="ack SET_USING_DIAL (0x1a)",
        )
    except TimeoutError as exc:
        raise E87ProtocolError(
            f"badge did not acknowledge dial switch to {path!r}; this firmware "
            "likely does not implement RCSP SET_USING_DIAL — fall back to re-upload"
        ) from exc
    status = ack.body[1] if len(ack.body) >= 2 else 0xFF
    if status not in (0x00, 0x01):
        # status byte position can vary by firmware; log rather than hard-fail.
        log.warning("SET_USING_DIAL ack carried status 0x%02x (body=%s)", status, ack.body.hex())


async def get_using_dial(
    write_ae01: Writer,
    bus: NotifyBus,
    sn: int,
    *,
    timeout: float = 8.0,
) -> str:
    """Return the path of the file currently displayed, or '' if none/unknown."""
    await write_ae01(build_get_using_dial_frame(sn))
    ack = await wait_for_frame(
        bus,
        lambda f: f.cmd == CMD_EXTERNAL_FLASH_IOCTRL,
        timeout=timeout,
        label="ack GET_USING_DIAL (0x1a)",
    )
    # Response body: [status?][opCodeSn][op][flag][path...]; be liberal and pull
    # the trailing printable run as the path.
    body = ack.body
    path = _extract_trailing_path(body)
    log.info("Current displayed file: %r (raw body=%s)", path, body.hex())
    return path


async def list_files(
    write_ae01: Writer,
    bus: NotifyBus,
    sn: int,
    *,
    timeout: float = 8.0,
) -> list[str]:
    """EXPERIMENTAL: ask the badge to enumerate stored files (RCSP file-browse).

    The JieLi file-browse subsystem has its own response encoding that this
    helper only partially decodes; in practice you rarely need it, because
    :meth:`E87Client.send_image` already returns the committed path of each
    upload. Provided mainly so :func:`probe_switching` can report whether the
    firmware answers a browse request at all.
    """
    # PathData for the root: type=folder(0), readNum=10, startIndex=1,
    # devHandler=0, path-cluster list length=0.
    path_data = bytes((0x00, 0x0A, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00))
    body = bytes((sn & 0xFF,)) + path_data
    await write_ae01(build_fe_frame(FLAG_COMMAND, CMD_FILE_BROWSE_START, body))
    names: list[str] = []
    try:
        ack = await wait_for_frame(
            bus,
            lambda f: f.cmd in (CMD_FILE_BROWSE_START, CMD_FILE_BROWSE_STOP),
            timeout=timeout,
            label="file-browse response (0x0c/0x0d)",
        )
        names = _extract_filename_runs(ack.body)
    except TimeoutError as exc:
        raise E87ProtocolError(
            "badge did not answer RCSP file-browse (0x0c); this firmware likely "
            "does not implement directory listing"
        ) from exc
    finally:
        # Best-effort close the browse session.
        try:
            await write_ae01(
                build_fe_frame(FLAG_COMMAND, CMD_FILE_BROWSE_STOP, bytes((sn & 0xFF,)))
            )
        except Exception:  # pragma: no cover
            pass
    return names


# ── helpers ─────────────────────────────────────────────────────────────────

def _extract_trailing_path(body: bytes) -> str:
    """Pull the trailing run of path-like bytes out of a response body."""
    # Walk back from the end collecting printable / common-filename bytes.
    out = bytearray()
    for b in reversed(body):
        if b in (0x00,):
            if out:
                break
            continue
        if 0x20 <= b < 0x7F or b >= 0x80:  # ascii printable or multibyte (utf-8/16)
            out.append(b)
        else:
            break
    raw = bytes(reversed(out))
    for enc in ("utf-8", "utf-16-le"):
        try:
            return raw.decode(enc).strip("\x00").strip()
        except Exception:
            continue
    return raw.decode("ascii", "ignore").strip()


def _extract_filename_runs(body: bytes, min_len: int = 3) -> list[str]:
    """Best-effort: extract filename-looking substrings from a browse response."""
    names: list[str] = []
    cur = bytearray()
    for b in body:
        if 0x20 <= b < 0x7F:
            cur.append(b)
        else:
            if len(cur) >= min_len:
                names.append(cur.decode("ascii", "ignore"))
            cur = bytearray()
    if len(cur) >= min_len:
        names.append(cur.decode("ascii", "ignore"))
    # Keep things that look like files (have a dot extension).
    return [n for n in names if "." in n]
