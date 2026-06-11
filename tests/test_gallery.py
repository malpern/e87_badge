"""Offline byte-layout tests for the gallery / dial-switch command builders.

These pin the wire format reconstructed from the Zrun APK's JieLi SDK
(`ExternalFlashIOCtrlParam.toData() = [op][flag][payload]`, command opcode 26).
They do not touch hardware — they assert the exact bytes we put on the wire.
"""

from __future__ import annotations

from e87_badge import gallery
from e87_badge.const import (
    CMD_EXTERNAL_FLASH_IOCTRL,
    FLAG_COMMAND,
    FLAG_GET_USING_DIAL,
    FLAG_SET_USING_DIAL,
    OP_DIAL_ACTION,
)
from e87_badge.frame import parse_fe_frame


def test_dial_action_body_layout():
    body = gallery.build_dial_action_body(0x42, FLAG_SET_USING_DIAL, b"/abc")
    # [opCodeSn, op=3, flag=1, payload...]
    assert body == bytes((0x42, OP_DIAL_ACTION, FLAG_SET_USING_DIAL)) + b"/abc"


def test_set_using_dial_frame_roundtrips_through_fe_parser():
    path = "啜20260610153000.jpg"
    raw = gallery.build_set_using_dial_frame(0x10, path)
    frame = parse_fe_frame(raw)
    assert frame is not None
    assert frame.flag == FLAG_COMMAND
    assert frame.cmd == CMD_EXTERNAL_FLASH_IOCTRL  # 0x1a / 26
    # body = sn + op + flag + utf8(path)
    assert frame.body[0] == 0x10
    assert frame.body[1] == OP_DIAL_ACTION
    assert frame.body[2] == FLAG_SET_USING_DIAL
    assert frame.body[3:] == path.encode("utf-8")


def test_get_using_dial_frame_has_empty_payload():
    raw = gallery.build_get_using_dial_frame(0x07)
    frame = parse_fe_frame(raw)
    assert frame is not None
    assert frame.cmd == CMD_EXTERNAL_FLASH_IOCTRL
    assert frame.body == bytes((0x07, OP_DIAL_ACTION, FLAG_GET_USING_DIAL))


def test_extract_trailing_path_ascii():
    body = bytes((0x00, 0x05, OP_DIAL_ACTION, FLAG_GET_USING_DIAL)) + b"/photo1.jpg\x00\x00"
    assert gallery._extract_trailing_path(body) == "/photo1.jpg"


def test_extract_filename_runs_filters_to_files():
    body = b"\x01\x02hello.jpg\x00\x00world.avi\x07ab"
    names = gallery._extract_filename_runs(body)
    assert "hello.jpg" in names
    assert "world.avi" in names
    assert "ab" not in names  # too short / no extension
