from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from .config import Settings


EXTRUDER_MAPPING_NAMESPACE = "spool_tag_writer"
EXTRUDER_MAPPING_KEY = "extruder_mapping"
AGENT_STATUS_KEY = "moonraker_agent_status"
DEFAULT_EXTRUDER_COUNT = 4
MAX_EXTRUDER_COUNT = 12
DEFAULT_FILAMENT_CHANNEL_COUNT = 4
MAX_FILAMENT_CHANNEL = DEFAULT_FILAMENT_CHANNEL_COUNT - 1
FILAMENT_DT_QUERY_DELAY_SECONDS = 0.25
AGENT_STATUS_HEARTBEAT_INTERVAL_SECONDS = 10
AGENT_STATUS_STALE_AFTER_SECONDS = 30


def tool_name_for_index(index: int) -> str:
    return "extruder" if index <= 0 else f"extruder{index}"


def clamp_extruder_count(value: Any) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return DEFAULT_EXTRUDER_COUNT
    return max(1, min(MAX_EXTRUDER_COUNT, numeric))


def parse_filament_channel(value: Any) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("RFID channel must be an integer between 0 and 3.") from exc
    if numeric < 0 or numeric > MAX_FILAMENT_CHANNEL:
        raise RuntimeError("RFID channel must be between 0 and 3.")
    return numeric


def coerce_spool_id(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        numeric = int(text)
    except ValueError:
        return None
    return numeric if numeric > 0 else None


def _normalize_filament_detect_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.casefold() == "none" else text


def normalize_card_uid(value: Any) -> str:
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            try:
                numeric = int(item)
            except (TypeError, ValueError):
                return ""
            if numeric < 0 or numeric > 255:
                return ""
            parts.append(f"{numeric:02x}")
        return f"0x{''.join(parts)}" if parts else ""

    if isinstance(value, int):
        return "" if value <= 0 else f"0x{value:x}"

    text = str(value or "").strip()
    if not text or text == "0":
        return ""
    normalized = text.casefold()
    if normalized.startswith("0x"):
        normalized = normalized[2:]
    normalized = normalized.replace(":", "").replace("-", "").replace(" ", "")
    if not normalized or any(char not in "0123456789abcdef" for char in normalized):
        return ""
    return f"0x{normalized}"


def serialize_filament_detect_channel(channel: int, filament_detect: dict[str, Any]) -> dict[str, Any]:
    info_list = filament_detect.get("info")
    state_list = filament_detect.get("state")
    info = (
        info_list[channel]
        if isinstance(info_list, list) and channel < len(info_list) and isinstance(info_list[channel], dict)
        else {}
    )
    state = (
        state_list[channel]
        if isinstance(state_list, list) and channel < len(state_list)
        else None
    )
    card_uid = normalize_card_uid(info.get("CARD_UID"))
    return {
        "channel": channel,
        "label": f"T{channel}",
        "state": state,
        "present": bool(card_uid),
        "card_uid": card_uid,
        "card_uid_raw": info.get("CARD_UID"),
        "vendor": _normalize_filament_detect_text(info.get("VENDOR")),
        "manufacturer": _normalize_filament_detect_text(info.get("MANUFACTURER")),
        "main_type": _normalize_filament_detect_text(info.get("MAIN_TYPE")),
        "sub_type": _normalize_filament_detect_text(info.get("SUB_TYPE")),
        "official": bool(info.get("OFFICIAL")),
        "raw": info,
    }


def normalize_extruder_mapping(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    count = clamp_extruder_count(source.get("count"))
    assignments_source = source.get("assignments")
    assignments: dict[str, int] = {}

    if isinstance(assignments_source, dict):
        for index in range(count):
            tool_name = tool_name_for_index(index)
            spool_id = coerce_spool_id(assignments_source.get(tool_name))
            if spool_id is not None:
                assignments[tool_name] = spool_id
    else:
        slots = source.get("slots")
        if isinstance(slots, list):
            for slot in slots:
                if not isinstance(slot, dict):
                    continue
                tool_name = str(slot.get("tool_name") or slot.get("toolName") or "").strip()
                if not tool_name:
                    index = slot.get("index")
                    try:
                        tool_name = tool_name_for_index(int(index))
                    except (TypeError, ValueError):
                        continue
                spool_id = coerce_spool_id(slot.get("spool_id") or slot.get("spoolId"))
                if spool_id is not None:
                    assignments[tool_name] = spool_id

        if "count" not in source and slots:
            count = max(count, min(MAX_EXTRUDER_COUNT, len(slots)))

    filtered_assignments = {
        tool_name_for_index(index): assignments[tool_name_for_index(index)]
        for index in range(count)
        if tool_name_for_index(index) in assignments
    }

    return {
        "count": count,
        "assignments": filtered_assignments,
    }


def spool_id_for_tool(mapping: dict[str, Any], tool_name: str | None) -> int | None:
    if not tool_name:
        return None
    assignments = mapping.get("assignments")
    if not isinstance(assignments, dict):
        return None
    return coerce_spool_id(assignments.get(str(tool_name)))


def serialize_extruder_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_extruder_mapping(mapping)
    return {
        "count": normalized["count"],
        "assignments": normalized["assignments"],
        "slots": [
            {
                "index": index,
                "tool_name": tool_name_for_index(index),
                "label": f"T{index}",
                "spool_id": normalized["assignments"].get(tool_name_for_index(index)),
            }
            for index in range(normalized["count"])
        ],
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def serialize_agent_status(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}

    def normalize_counter(key: str) -> int:
        try:
            return max(0, int(source.get(key) or 0))
        except (TypeError, ValueError):
            return 0

    return {
        "connected": bool(source.get("connected")),
        "connected_at": str(source.get("connected_at") or "").strip(),
        "last_seen_at": str(source.get("last_seen_at") or "").strip(),
        "last_sync_at": str(source.get("last_sync_at") or "").strip(),
        "last_switch_at": str(source.get("last_switch_at") or "").strip(),
        "last_error": str(source.get("last_error") or "").strip(),
        "last_error_at": str(source.get("last_error_at") or "").strip(),
        "active_tool": str(source.get("active_tool") or "").strip(),
        "target_spool_id": coerce_spool_id(source.get("target_spool_id")),
        "previous_spool_id": coerce_spool_id(source.get("previous_spool_id")),
        "active_spool_id": coerce_spool_id(source.get("active_spool_id")),
        "sync_count": normalize_counter("sync_count"),
        "switch_count": normalize_counter("switch_count"),
    }


def is_agent_status_online(status: dict[str, Any], *, now: datetime | None = None) -> bool:
    if not status.get("connected"):
        return False
    last_seen_at = parse_timestamp(status.get("last_seen_at"))
    if last_seen_at is None:
        return False
    current_time = now or datetime.now(timezone.utc)
    return current_time - last_seen_at <= timedelta(seconds=AGENT_STATUS_STALE_AFTER_SECONDS)


def derive_moonraker_http_url(settings: Settings) -> str:
    override = str(getattr(settings, "moonraker_http_url", "") or "").strip()
    if override:
        return override.rstrip("/")

    parsed = urlparse(settings.moonraker_ws_url)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError("MOONRAKER_WS_URL is invalid and MOONRAKER_HTTP_URL is not set.")
    scheme = "https" if parsed.scheme == "wss" else "http"
    return f"{scheme}://{parsed.netloc}"


def should_discover_spoolman_url(settings: Settings) -> bool:
    configured = str(getattr(settings, "spoolman_url", "") or "").strip()
    return not configured or configured.casefold() == "auto"


def extract_spoolman_url_from_server_config(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    config = payload.get("config")
    if not isinstance(config, dict):
        return None
    spoolman = config.get("spoolman")
    if not isinstance(spoolman, dict):
        return None
    server_value = spoolman.get("server")
    if server_value is None:
        return None
    text = str(server_value).strip()
    return text.rstrip("/") if text else None


class MoonrakerClient:
    def __init__(self, settings: Settings) -> None:
        headers: dict[str, str] = {}
        if settings.moonraker_api_key:
            headers["X-Api-Key"] = settings.moonraker_api_key
        self._client = httpx.AsyncClient(
            base_url=derive_moonraker_http_url(settings),
            timeout=settings.request_timeout_seconds,
            headers=headers,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> Any:
        response = await self._client.request(
            method,
            path,
            params=params,
            json=json_payload,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "result" in payload:
            return payload["result"]
        return payload

    async def get_extruder_mapping(self) -> dict[str, Any]:
        try:
            data = await self._request(
                "GET",
                "/server/database/item",
                params={
                    "namespace": EXTRUDER_MAPPING_NAMESPACE,
                    "key": EXTRUDER_MAPPING_KEY,
                },
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return serialize_extruder_mapping({})
            raise RuntimeError(f"Moonraker database request failed: {exc}") from exc
        value = data.get("value") if isinstance(data, dict) else data
        return serialize_extruder_mapping(value)

    async def get_database_item(
        self,
        namespace: str,
        key: str,
        *,
        default: Any = None,
    ) -> Any:
        try:
            data = await self._request(
                "GET",
                "/server/database/item",
                params={"namespace": namespace, "key": key},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return default
            raise RuntimeError(f"Moonraker database request failed: {exc}") from exc
        return data.get("value") if isinstance(data, dict) else data

    async def save_database_item(self, namespace: str, key: str, value: Any) -> Any:
        data = await self._request(
            "POST",
            "/server/database/item",
            json_payload={
                "namespace": namespace,
                "key": key,
                "value": value,
            },
        )
        return data.get("value") if isinstance(data, dict) else data

    async def get_server_config(self) -> dict[str, Any]:
        data = await self._request("GET", "/server/config")
        return data if isinstance(data, dict) else {}

    async def get_spoolman_server_url(self) -> str | None:
        return extract_spoolman_url_from_server_config(await self.get_server_config())

    async def save_extruder_mapping(self, mapping: dict[str, Any]) -> dict[str, Any]:
        normalized = serialize_extruder_mapping(mapping)
        data = await self.save_database_item(
            EXTRUDER_MAPPING_NAMESPACE,
            EXTRUDER_MAPPING_KEY,
            {
                "count": normalized["count"],
                "assignments": normalized["assignments"],
            },
        )
        return serialize_extruder_mapping(data)

    async def get_agent_status(self) -> dict[str, Any]:
        value = await self.get_database_item(
            EXTRUDER_MAPPING_NAMESPACE,
            AGENT_STATUS_KEY,
            default={},
        )
        return serialize_agent_status(value)

    async def run_gcode_script(self, script: str) -> Any:
        return await self._request(
            "POST",
            "/printer/gcode/script",
            json_payload={"script": script},
        )

    async def refresh_filament_detect_channel(self, channel: int) -> None:
        validated_channel = parse_filament_channel(channel)
        await self.run_gcode_script(f"FILAMENT_DT_UPDATE CHANNEL={validated_channel}")
        await asyncio.sleep(FILAMENT_DT_QUERY_DELAY_SECONDS)
        await self.run_gcode_script(f"FILAMENT_DT_QUERY CHANNEL={validated_channel}")

    async def get_filament_detect_channels(
        self,
        *,
        refresh_channels: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        if refresh_channels:
            for channel in dict.fromkeys(parse_filament_channel(value) for value in refresh_channels):
                await self.refresh_filament_detect_channel(channel)

        data = await self._request("GET", "/printer/objects/query?filament_detect")
        if not isinstance(data, dict):
            raise RuntimeError("Unexpected Moonraker filament_detect response.")

        status = data.get("status")
        if not isinstance(status, dict):
            raise RuntimeError("Moonraker filament_detect response does not contain status.")

        filament_detect = status.get("filament_detect")
        if not isinstance(filament_detect, dict):
            raise RuntimeError("Moonraker did not expose the filament_detect object.")

        info_list = filament_detect.get("info")
        channel_count = (
            len(info_list)
            if isinstance(info_list, list) and info_list
            else DEFAULT_FILAMENT_CHANNEL_COUNT
        )
        return [
            serialize_filament_detect_channel(channel, filament_detect)
            for channel in range(channel_count)
        ]

    async def get_filament_detect_channel(
        self,
        channel: int,
        *,
        refresh: bool = False,
    ) -> dict[str, Any]:
        validated_channel = parse_filament_channel(channel)
        channels = await self.get_filament_detect_channels(
            refresh_channels=[validated_channel] if refresh else None
        )
        if validated_channel >= len(channels):
            raise RuntimeError(f"Moonraker returned only {len(channels)} RFID channels.")
        return channels[validated_channel]

    async def get_spoolman_status(self) -> dict[str, Any]:
        data = await self._request("GET", "/server/spoolman/status")
        return data if isinstance(data, dict) else {}

    async def get_active_spool_id(self) -> int | None:
        data = await self._request("GET", "/server/spoolman/spool_id")
        if not isinstance(data, dict):
            return None
        return coerce_spool_id(data.get("spool_id"))

    async def set_active_spool_id(self, spool_id: int | None) -> int | None:
        data = await self._request(
            "POST",
            "/server/spoolman/spool_id",
            json_payload={"spool_id": spool_id} if spool_id is not None else {},
        )
        if not isinstance(data, dict):
            return None
        return coerce_spool_id(data.get("spool_id"))

    async def get_active_tool(self) -> str | None:
        data = await self._request(
            "POST",
            "/printer/objects/query",
            json_payload={"objects": {"toolhead": ["extruder"]}},
        )
        if not isinstance(data, dict):
            return None
        status = data.get("status")
        if not isinstance(status, dict):
            return None
        toolhead = status.get("toolhead")
        if not isinstance(toolhead, dict):
            return None
        extruder_name = toolhead.get("extruder")
        if extruder_name is None:
            return None
        text = str(extruder_name).strip()
        return text or None

    async def sync_active_spool_from_mapping(self) -> dict[str, Any]:
        mapping = await self.get_extruder_mapping()
        active_tool = await self.get_active_tool()
        target_spool_id = spool_id_for_tool(mapping, active_tool)
        active_spool_id = await self.set_active_spool_id(target_spool_id)
        return {
            "active_tool": active_tool,
            "active_spool_id": active_spool_id,
            "count": mapping["count"],
            "assignments": mapping["assignments"],
            "slots": mapping["slots"],
        }


async def resolve_spoolman_url(settings: Settings) -> str:
    configured = str(getattr(settings, "spoolman_url", "") or "").strip()
    if configured and configured.casefold() != "auto":
        return configured.rstrip("/")

    moonraker = MoonrakerClient(settings)
    try:
        discovered = await moonraker.get_spoolman_server_url()
    finally:
        await moonraker.close()

    if discovered:
        return discovered

    raise RuntimeError(
        "SPOOLMAN_URL is not configured and Moonraker did not provide [spoolman] server. "
        "Set SPOOLMAN_URL explicitly or configure Moonraker [spoolman]."
    )
