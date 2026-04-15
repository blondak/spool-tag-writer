from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from .config import Settings


EXTRUDER_MAPPING_NAMESPACE = "spool_tag_writer"
EXTRUDER_MAPPING_KEY = "extruder_mapping"
DEFAULT_EXTRUDER_COUNT = 4
MAX_EXTRUDER_COUNT = 12


def tool_name_for_index(index: int) -> str:
    return "extruder" if index <= 0 else f"extruder{index}"


def clamp_extruder_count(value: Any) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return DEFAULT_EXTRUDER_COUNT
    return max(1, min(MAX_EXTRUDER_COUNT, numeric))


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

    async def get_server_config(self) -> dict[str, Any]:
        data = await self._request("GET", "/server/config")
        return data if isinstance(data, dict) else {}

    async def get_spoolman_server_url(self) -> str | None:
        return extract_spoolman_url_from_server_config(await self.get_server_config())

    async def save_extruder_mapping(self, mapping: dict[str, Any]) -> dict[str, Any]:
        normalized = serialize_extruder_mapping(mapping)
        data = await self._request(
            "POST",
            "/server/database/item",
            json_payload={
                "namespace": EXTRUDER_MAPPING_NAMESPACE,
                "key": EXTRUDER_MAPPING_KEY,
                "value": {
                    "count": normalized["count"],
                    "assignments": normalized["assignments"],
                },
            },
        )
        value = data.get("value") if isinstance(data, dict) else data
        return serialize_extruder_mapping(value)

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
            json_payload={"spool_id": spool_id},
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
