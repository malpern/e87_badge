"""Instant asset switching — display a *preloaded* file without re-uploading.

.. warning::

   **Tested on E87 firmware V11.1.0.3: NOT supported.** These commands were
   recovered from the Zrun APK's bundled JieLi watch SDK (``com.jieli.jl_rcsp``),
   and the badge *does* speak JieLi RCSP over AE01 (its file-upload opcodes match
   the SDK's command registry; every upload is committed as its own persistent
   file). But on the one firmware we have measured (**V11.1.0.3**) the badge
   **rejects the dial-action opcode** — `SET_USING_DIAL` and even `GET_USING_DIAL`
   return RCSP status ``0x02`` — which JieLi's own ``StateCode`` defines as
   ``STATUS_UNKNOWN_CMD`` (the firmware literally reports the command as unknown).
   So display-by-reference does not work and these calls raise
   :class:`~e87_badge.errors.E87ProtocolError`. The "watch dial" subsystem simply
   isn't wired up in this display-badge firmware; the badge always shows the most
   recently uploaded file. (File *browse*, cmd 0x0c, is accepted — so the
   filesystem is enumerable even though switching is not. The legacy "qix"
   command channel was also tested — SET_THEME/SET_PUSH_DIAL drew no response.)

   Kept in the library because (a) other/newer firmware may implement it, and
   (b) :func:`probe_switching` / ``e87 probe`` is the honest way to check any
   given unit. Always be ready to fall back to a normal re-upload.

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
    # RCSP response body is [status][opCodeSn][param...]; status 0 == success.
    status = ack.body[0] if ack.body else 0xFF
    if status != 0x00:
        raise E87ProtocolError(
            f"badge rejected the dial switch to {path!r} (RCSP status 0x{status:02x}). "
            "This firmware does not implement display-by-reference — observed on "
            "E87 V11.1.0.3, which returns status 0x02 for any dial action. "
            "Re-upload the asset instead."
        )


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
    # RCSP response body is [status][opCodeSn][param...]. status 0 == success;
    # E87 V11.1.0.3 returns 0x02 (dial subsystem unsupported).
    status = ack.body[0] if ack.body else 0xFF
    if status != 0x00:
        raise E87ProtocolError(
            f"badge rejected GET_USING_DIAL (RCSP status 0x{status:02x}); this "
            "firmware's dial subsystem is unsupported (E87 V11.1.0.3 returns 0x02)."
        )
    path = _extract_trailing_path(ack.body[2:])
    log.info("Current displayed file: %r (raw body=%s)", path, ack.body.hex())
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
