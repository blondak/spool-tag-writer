from __future__ import annotations

from typing import Any


class NdefError(Exception):
    pass


def encode_single_mime_record(mime_type: str, payload: bytes) -> bytes:
    type_bytes = mime_type.encode("ascii")
    if len(type_bytes) > 255:
        raise NdefError("MIME type is too long.")
    is_short = len(payload) <= 255
    header = 0x80 | 0x40 | 0x02  # MB, ME, TNF=MIME
    if is_short:
        header |= 0x10  # SR
        return bytes([header, len(type_bytes), len(payload)]) + type_bytes + payload
    return (
        bytes([header, len(type_bytes)])
        + len(payload).to_bytes(4, "big")
        + type_bytes
        + payload
    )


def decode_single_mime_record(message: bytes) -> tuple[str, bytes]:
    if len(message) < 3:
        raise NdefError("NDEF message is too short.")
    header = message[0]
    tnf = header & 0x07
    is_short = bool(header & 0x10)
    has_id = bool(header & 0x08)
    if tnf != 0x02:
        raise NdefError("Unsupported TNF. Expected MIME media record.")
    idx = 1
    type_len = message[idx]
    idx += 1
    if is_short:
        payload_len = message[idx]
        idx += 1
    else:
        if idx + 3 >= len(message):
            raise NdefError("NDEF long-record payload length is truncated.")
        payload_len = int.from_bytes(message[idx : idx + 4], "big")
        idx += 4

    if has_id:
        id_len = message[idx]
        idx += 1
    else:
        id_len = 0

    end_type = idx + type_len
    end_id = end_type + id_len
    end_payload = end_id + payload_len
    if end_payload > len(message):
        raise NdefError("NDEF record is truncated.")
    mime_type = message[idx:end_type].decode("ascii")
    payload = message[end_id:end_payload]
    return mime_type, payload


def encode_tlv_from_ndef_message(message: bytes) -> bytes:
    if len(message) < 0xFF:
        return b"\x03" + bytes([len(message)]) + message + b"\xFE"
    if len(message) > 0xFFFF:
        raise NdefError("NDEF message too large for TLV encoding.")
    return b"\x03\xFF" + len(message).to_bytes(2, "big") + message + b"\xFE"


def extract_ndef_message_from_tlv(memory: bytes) -> bytes:
    idx = 0
    while idx < len(memory):
        tag = memory[idx]
        idx += 1
        if tag == 0x00:  # NULL TLV
            continue
        if tag == 0xFE:  # Terminator TLV
            break
        if idx >= len(memory):
            break
        length = memory[idx]
        idx += 1
        if length == 0xFF:
            if idx + 1 >= len(memory):
                raise NdefError("Invalid extended TLV length.")
            length = (memory[idx] << 8) | memory[idx + 1]
            idx += 2
        if idx + length > len(memory):
            raise NdefError("TLV payload exceeds memory bounds.")
        value = memory[idx : idx + length]
        idx += length
        if tag == 0x03:
            return value
    raise NdefError("No NDEF TLV record found.")


def build_ndef_debug(message: bytes, payload: bytes, mime_type: str) -> dict[str, Any]:
    return {
        "mime_type": mime_type,
        "payload_size": len(payload),
        "message_size": len(message),
        "payload_preview_utf8": payload.decode("utf-8", errors="replace"),
        "payload_hex": payload.hex(),
    }
