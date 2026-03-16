from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Protocol

from .config import Settings
from .ndef_codec import (
    NdefError,
    decode_single_mime_record,
    encode_single_mime_record,
    encode_tlv_from_ndef_message,
    extract_ndef_message_from_tlv,
)


class NfcError(Exception):
    pass


class NfcBackend(Protocol):
    def write_openspool_payload(self, payload_json: str) -> dict[str, Any]: ...

    def read_current_payload(self) -> dict[str, Any]: ...


def _build_read_result(
    payload: bytes,
    mime_type: str,
    **extra: Any,
) -> dict[str, Any]:
    payload_text = payload.decode("utf-8", errors="replace")
    result: dict[str, Any] = {
        "status": "ok",
        "mime_type": mime_type,
        "payload_size": len(payload),
        "payload_text": payload_text,
        **extra,
    }
    try:
        result["payload_json"] = json.loads(payload_text)
    except json.JSONDecodeError:
        pass
    return result


class PcscAcr122uBackend:
    def __init__(self, settings: Settings) -> None:
        self.reader_name = settings.nfc_reader_name
        self.start_page = settings.ntag215_start_page
        self.end_page = settings.ntag215_end_page
        self.config_capacity_bytes = (self.end_page - self.start_page + 1) * 4

    def _reader(self):
        try:
            from smartcard.System import readers
        except Exception as exc:  # pragma: no cover - hardware dependency
            raise NfcError("pyscard is not available. Install pyscard and PC/SC drivers.") from exc

        available = readers()
        if not available:
            raise NfcError("No smartcard readers found.")
        for reader in available:
            if self.reader_name.lower() in str(reader).lower():
                return reader
        raise NfcError(
            f"Reader containing '{self.reader_name}' not found. Available readers: "
            + ", ".join(str(r) for r in available)
        )

    @staticmethod
    def _transmit(connection, apdu: list[int]) -> bytes:
        data, sw1, sw2 = connection.transmit(apdu)
        if (sw1, sw2) != (0x90, 0x00):
            raise NfcError(f"APDU failed ({sw1:02X} {sw2:02X}) for {apdu}")
        return bytes(data)

    def _connect(self):
        reader = self._reader()
        connection = reader.createConnection()
        connection.connect()
        return connection

    def _read_cc_capacity_bytes(self, connection) -> int | None:
        # Read pages 0..3 and inspect Capability Container on page 3.
        raw = self._transmit(connection, [0xFF, 0xB0, 0x00, 0x00, 0x10])
        if len(raw) < 16:
            raise NfcError("Failed to read tag header (CC).")
        cc = raw[12:16]
        if cc[0] != 0xE1:
            return None
        if cc[2] == 0x00:
            return None
        return cc[2] * 8

    def _effective_capacity_bytes(self, connection) -> tuple[int, int | None]:
        tag_capacity = self._read_cc_capacity_bytes(connection)
        if tag_capacity is None:
            return self.config_capacity_bytes, None
        return min(self.config_capacity_bytes, tag_capacity), tag_capacity

    def _write_tlv(self, connection, tlv_bytes: bytes, capacity_bytes: int) -> int:
        if len(tlv_bytes) > capacity_bytes:
            raise NfcError(
                "Data exceeds tag capacity: "
                f"{len(tlv_bytes)} bytes > {capacity_bytes} bytes"
            )

        page_count = math.ceil(len(tlv_bytes) / 4)
        max_pages = math.ceil(capacity_bytes / 4)
        if page_count > max_pages:
            raise NfcError(
                f"Data requires {page_count} pages but tag allows only {max_pages} pages."
            )
        data_padded = tlv_bytes.ljust(page_count * 4, b"\x00")

        for page_offset in range(page_count):
            page = self.start_page + page_offset
            if page > self.end_page:
                raise NfcError(
                    f"Write would exceed configured page limit ({self.end_page})."
                )
            chunk = data_padded[page_offset * 4 : page_offset * 4 + 4]
            apdu = [0xFF, 0xD6, 0x00, page, 0x04, *chunk]
            self._transmit(connection, apdu)
        return page_count

    def _read_user_memory(self, connection, capacity_bytes: int) -> bytes:
        memory = bytearray()
        bytes_left = capacity_bytes
        page = self.start_page

        while bytes_left > 0:
            apdu = [0xFF, 0xB0, 0x00, page, 0x10]
            chunk = self._transmit(connection, apdu)
            chunk_size = min(0x10, bytes_left)
            if len(chunk) < chunk_size:
                raise NfcError(
                    f"Read returned too few bytes ({len(chunk)} < {chunk_size})."
                )
            memory.extend(chunk[:chunk_size])
            bytes_left -= chunk_size
            page += 4
        return bytes(memory)

    def write_openspool_payload(self, payload_json: str) -> dict[str, Any]:
        payload_bytes = payload_json.encode("utf-8")
        message = encode_single_mime_record("application/json", payload_bytes)
        tlv = encode_tlv_from_ndef_message(message)
        connection = self._connect()
        try:
            capacity_bytes, tag_capacity_bytes = self._effective_capacity_bytes(connection)
            pages_written = self._write_tlv(connection, tlv, capacity_bytes)
            return {
                "status": "written",
                "payload_size": len(payload_bytes),
                "ndef_message_size": len(message),
                "tlv_size": len(tlv),
                "capacity_checked_bytes": capacity_bytes,
                "tag_cc_capacity_bytes": tag_capacity_bytes,
                "pages_written": pages_written,
            }
        finally:
            try:
                connection.disconnect()
            except Exception:
                pass

    def read_current_payload(self) -> dict[str, Any]:
        connection = self._connect()
        try:
            capacity_bytes, tag_capacity_bytes = self._effective_capacity_bytes(connection)
            memory = self._read_user_memory(connection, capacity_bytes)
            message = extract_ndef_message_from_tlv(memory)
            mime_type, payload = decode_single_mime_record(message)
            return _build_read_result(
                payload,
                mime_type,
                capacity_checked_bytes=capacity_bytes,
                tag_cc_capacity_bytes=tag_capacity_bytes,
            )
        except NdefError as exc:
            raise NfcError(f"Unable to decode tag content: {exc}") from exc
        finally:
            try:
                connection.disconnect()
            except Exception:
                pass


class MockNfcBackend:
    def __init__(self, settings: Settings) -> None:
        self.storage_path = Path(settings.mock_storage_file)

    def write_openspool_payload(self, payload_json: str) -> dict[str, Any]:
        payload_bytes = payload_json.encode("utf-8")
        message = encode_single_mime_record("application/json", payload_bytes)
        tlv = encode_tlv_from_ndef_message(message)
        self.storage_path.write_bytes(tlv)
        return {
            "status": "written",
            "payload_size": len(payload_bytes),
            "ndef_message_size": len(message),
            "tlv_size": len(tlv),
            "mock_file": str(self.storage_path),
        }

    def read_current_payload(self) -> dict[str, Any]:
        if not self.storage_path.exists():
            raise NfcError("Mock storage does not contain any data yet.")
        tlv = self.storage_path.read_bytes()
        try:
            message = extract_ndef_message_from_tlv(tlv)
            mime_type, payload = decode_single_mime_record(message)
            return _build_read_result(payload, mime_type)
        except NdefError as exc:
            raise NfcError(f"Unable to decode mock tag content: {exc}") from exc


def build_nfc_backend(settings: Settings) -> NfcBackend:
    backend = settings.nfc_backend.strip().lower()
    if backend == "mock":
        return MockNfcBackend(settings)
    if backend == "pcsc":
        return PcscAcr122uBackend(settings)
    raise NfcError(f"Unsupported NFC backend '{settings.nfc_backend}'. Use 'pcsc' or 'mock'.")
