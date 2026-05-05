from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from .config import Settings, get_settings
from .moonraker import (
    AGENT_STATUS_HEARTBEAT_INTERVAL_SECONDS,
    AGENT_STATUS_KEY,
    EXTRUDER_MAPPING_KEY,
    EXTRUDER_MAPPING_NAMESPACE,
    resolve_spoolman_url,
    serialize_agent_status,
    serialize_extruder_mapping,
    spool_id_for_tool,
    utc_now_iso,
)
from .nfc import build_nfc_backend
from .openspool import apply_openspool_overrides, build_openspool_payload
from .spoolman import SpoolmanClient


LOG = logging.getLogger("spool_tag_writer.moonraker_agent")


class MoonrakerAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.spoolman = SpoolmanClient(settings)
        self.nfc = build_nfc_backend(settings) if settings.local_nfc_enabled else None
        self._rpc_id = 0
        self._backlog: list[dict[str, Any]] = []
        self._last_active_tool: str | None = None
        self._status = serialize_agent_status({})

    def _next_rpc_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    async def _rpc_call(self, ws, method: str, params: dict[str, Any] | None = None) -> Any:
        rpc_id = self._next_rpc_id()
        await ws.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "method": method,
                    "params": params or {},
                }
            )
        )
        while True:
            message = json.loads(await ws.recv())
            if message.get("id") == rpc_id:
                if "error" in message:
                    raise RuntimeError(f"{method} failed: {message['error']}")
                return message.get("result")
            self._backlog.append(message)

    async def _send_event(self, ws, event_name: str, data: dict[str, Any]) -> None:
        await ws.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "connection.send_event",
                    "params": {"event": event_name, "data": data},
                }
            )
        )

    async def _send_result(self, ws, msg_id: Any, result: Any) -> None:
        await ws.send(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}))

    async def _send_error(self, ws, msg_id: Any, message: str) -> None:
        await ws.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32000, "message": message},
                }
            )
        )

    async def _run_gcode_script(self, ws, script: str) -> Any:
        return await self._rpc_call(ws, "printer.gcode.script", {"script": script})

    async def _respond_info(self, ws, message: str) -> None:
        safe_message = str(message).replace('"', "'").replace("\n", " ").strip()
        if not safe_message:
            return
        await self._run_gcode_script(ws, f'RESPOND TYPE=echo MSG="{safe_message}"')

    async def _subscribe_toolhead(self, ws) -> dict[str, Any]:
        result = await self._rpc_call(
            ws,
            "printer.objects.subscribe",
            {"objects": {"toolhead": ["extruder"]}},
        )
        return result if isinstance(result, dict) else {}

    async def _publish_status(self, ws, **updates: Any) -> dict[str, Any]:
        next_status = serialize_agent_status({**self._status, **updates})
        await self._rpc_call(
            ws,
            "server.database.post_item",
            {
                "namespace": EXTRUDER_MAPPING_NAMESPACE,
                "key": AGENT_STATUS_KEY,
                "value": next_status,
            },
        )
        self._status = next_status
        return next_status

    async def _heartbeat_loop(self, ws) -> None:
        while True:
            await asyncio.sleep(AGENT_STATUS_HEARTBEAT_INTERVAL_SECONDS)
            try:
                await self._publish_status(
                    ws,
                    connected=True,
                    last_seen_at=utc_now_iso(),
                )
            except Exception as exc:
                LOG.debug("Moonraker agent heartbeat update failed: %s", exc)

    @staticmethod
    def _extract_spool_id(params: Any) -> int | None:
        def pick_id(value: Any) -> int | None:
            if not isinstance(value, dict):
                return None
            for key in ("spool_id", "SPOOL_ID", "id"):
                if key in value and value[key] is not None:
                    try:
                        return int(value[key])
                    except (TypeError, ValueError):
                        return None
            for nested_key in ("arguments", "kwargs", "params"):
                nested = value.get(nested_key)
                nested_result = pick_id(nested)
                if nested_result is not None:
                    return nested_result
            return None

        if isinstance(params, dict):
            return pick_id(params)
        if isinstance(params, list):
            for item in params:
                found = pick_id(item)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _extract_overrides(params: Any) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        source: dict[str, Any] = {}

        def flatten(value: Any) -> None:
            if isinstance(value, dict):
                source.update(value)
                for nested_key in ("arguments", "kwargs", "params"):
                    flatten(value.get(nested_key))
            elif isinstance(value, list):
                for item in value:
                    flatten(item)

        flatten(params)

        mapping = {
            "type": "type",
            "color_hex": "color_hex",
            "brand": "brand",
            "min_temp": "min_temp",
            "max_temp": "max_temp",
            "bed_min_temp": "bed_min_temp",
            "bed_max_temp": "bed_max_temp",
            "subtype": "subtype",
            "TYPE": "type",
            "COLOR_HEX": "color_hex",
            "BRAND": "brand",
            "MIN_TEMP": "min_temp",
            "MAX_TEMP": "max_temp",
            "BED_MIN_TEMP": "bed_min_temp",
            "BED_MAX_TEMP": "bed_max_temp",
            "SUBTYPE": "subtype",
            # Backward compatibility:
            "min_temp_c": "min_temp",
            "max_temp_c": "max_temp",
            "bed_temp_c": "bed_min_temp",
            "BED_TEMP": "bed_min_temp",
        }

        for key, value in source.items():
            if value is None:
                continue
            text_value = str(value).strip()
            if not text_value:
                continue

            if key in {"BED_TEMP", "bed_temp_c"}:
                normalized["bed_min_temp"] = text_value
                normalized["bed_max_temp"] = text_value
                continue

            target_key = mapping.get(key)
            if not target_key:
                continue
            if target_key == "color_hex":
                normalized[target_key] = text_value.lstrip("#").upper()
            else:
                normalized[target_key] = text_value
        return normalized

    async def _resolve_active_spool_id(self, ws) -> int | None:
        result = await self._rpc_call(
            ws, "printer.objects.query", {"objects": {"spoolman": None}}
        )
        if not isinstance(result, dict):
            return None
        status = result.get("status")
        if not isinstance(status, dict):
            return None
        spoolman = status.get("spoolman")
        if not isinstance(spoolman, dict):
            return None
        for key in ("spool_id", "active_spool_id", "spool", "id"):
            value = spoolman.get(key)
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                continue
        return None

    async def _write_tag(
        self, spool_id: int, overrides: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if self.nfc is None:
            raise RuntimeError("Local NFC reader support is disabled.")
        spool = await self.spoolman.get_spool(spool_id)
        payload = build_openspool_payload(spool, self.settings.spoolman_url)
        payload = apply_openspool_overrides(payload, overrides)
        payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        write_result = self.nfc.write_openspool_payload(payload_json)
        readback = self.nfc.read_current_payload()
        return {
            "spool_id": spool_id,
            "payload_size": len(payload_json.encode("utf-8")),
            "overrides": overrides or {},
            "write_result": write_result,
            "readback": readback,
        }

    async def _get_fallback_mapping(self, ws) -> dict[str, Any]:
        try:
            result = await self._rpc_call(
                ws,
                "server.database.get_item",
                {
                    "namespace": EXTRUDER_MAPPING_NAMESPACE,
                    "key": EXTRUDER_MAPPING_KEY,
                },
            )
        except RuntimeError as exc:
            if "does not exist" in str(exc).casefold() or "404" in str(exc):
                return serialize_extruder_mapping({})
            raise
        value = result.get("value") if isinstance(result, dict) else result
        return serialize_extruder_mapping(value)

    async def _get_active_tool(self, ws) -> str | None:
        result = await self._rpc_call(
            ws,
            "printer.objects.query",
            {"objects": {"toolhead": ["extruder"]}},
        )
        if not isinstance(result, dict):
            return None
        status = result.get("status")
        if not isinstance(status, dict):
            return None
        toolhead = status.get("toolhead")
        if not isinstance(toolhead, dict):
            return None
        extruder = toolhead.get("extruder")
        if extruder is None:
            return None
        text = str(extruder).strip()
        return text or None

    async def _get_active_spool_id(self, ws) -> int | None:
        result = await self._rpc_call(ws, "server.spoolman.get_spool_id")
        if not isinstance(result, dict):
            return None
        value = result.get("spool_id")
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            return None
        return None

    async def _set_active_spool_id(self, ws, spool_id: int | None) -> int | None:
        result = await self._rpc_call(
            ws,
            "server.spoolman.post_spool_id",
            {"spool_id": spool_id} if spool_id is not None else {},
        )
        if not isinstance(result, dict):
            return None
        value = result.get("spool_id")
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            return None
        return None

    async def _sync_active_spool_from_mapping(
        self,
        ws,
        *,
        active_tool: str | None = None,
    ) -> dict[str, Any]:
        mapping = await self._get_fallback_mapping(ws)
        resolved_tool = active_tool if active_tool is not None else await self._get_active_tool(ws)
        target_spool_id = spool_id_for_tool(mapping, resolved_tool)
        current_spool_id = await self._get_active_spool_id(ws)
        active_spool_id = current_spool_id
        now = utc_now_iso()
        status_updates: dict[str, Any] = {
            "connected": True,
            "last_seen_at": now,
            "last_sync_at": now,
            "last_error": "",
            "last_error_at": "",
            "active_tool": resolved_tool,
            "target_spool_id": target_spool_id,
            "previous_spool_id": current_spool_id,
            "active_spool_id": current_spool_id,
            "sync_count": self._status.get("sync_count", 0) + 1,
        }

        if current_spool_id != target_spool_id:
            active_spool_id = await self._set_active_spool_id(ws, target_spool_id)
            status_updates["active_spool_id"] = active_spool_id
            status_updates["last_switch_at"] = now
            status_updates["switch_count"] = self._status.get("switch_count", 0) + 1
            LOG.info(
                "Active spool sync: tool=%s target_spool_id=%s previous_spool_id=%s new_spool_id=%s",
                resolved_tool,
                target_spool_id,
                current_spool_id,
                active_spool_id,
            )
        else:
            status_updates["active_spool_id"] = current_spool_id

        await self._publish_status(ws, **status_updates)

        self._last_active_tool = resolved_tool
        return {
            "active_tool": resolved_tool,
            "target_spool_id": target_spool_id,
            "previous_spool_id": current_spool_id,
            "active_spool_id": active_spool_id,
            "count": mapping["count"],
            "assignments": mapping["assignments"],
            "slots": mapping["slots"],
        }

    async def _handle_status_update(self, ws, message: dict[str, Any]) -> None:
        if message.get("method") != "notify_status_update":
            return

        params = message.get("params")
        if not isinstance(params, list) or not params:
            return
        status = params[0]
        if not isinstance(status, dict):
            return
        toolhead = status.get("toolhead")
        if not isinstance(toolhead, dict) or "extruder" not in toolhead:
            return

        extruder = toolhead.get("extruder")
        active_tool = str(extruder).strip() if extruder is not None else None
        if not active_tool:
            return
        if active_tool == self._last_active_tool:
            return

        try:
            await self._sync_active_spool_from_mapping(ws, active_tool=active_tool)
        except Exception as exc:
            LOG.warning("Automatic active spool sync failed for tool %s: %s", active_tool, exc)
            try:
                await self._publish_status(
                    ws,
                    connected=True,
                    last_seen_at=utc_now_iso(),
                    active_tool=active_tool,
                    last_error=str(exc),
                    last_error_at=utc_now_iso(),
                )
            except Exception as status_exc:
                LOG.debug("Moonraker agent status update failed after sync error: %s", status_exc)

    async def _show_fallback_mapping(self, ws) -> dict[str, Any]:
        mapping = await self._get_fallback_mapping(ws)
        lines = ["Spool Tag Writer fallback mapping:"]
        for slot in mapping.get("slots", []):
            if not isinstance(slot, dict):
                continue
            label = str(slot.get("label") or f"T{slot.get('index', '?')}")
            tool_name = str(slot.get("tool_name") or "?")
            spool_id = slot.get("spool_id")
            if spool_id:
                lines.append(f"{label} ({tool_name}) -> spool #{spool_id}")
            else:
                lines.append(f"{label} ({tool_name}) -> unassigned")

        for line in lines:
            await self._respond_info(ws, line)
        return mapping

    async def _handle_message(self, ws, message: dict[str, Any]) -> None:
        if message.get("method") == "notify_status_update":
            await self._handle_status_update(ws, message)
            return

        method = message.get("method")
        if method == self.settings.moonraker_show_mapping_agent_method or method == self.settings.moonraker_show_mapping_remote_method:
            msg_id = message.get("id")
            try:
                result = await self._show_fallback_mapping(ws)
                if msg_id is not None:
                    await self._send_result(ws, msg_id, result)
            except Exception as exc:
                error_text = str(exc)
                LOG.exception("Fallback mapping display request failed: %s", error_text)
                if msg_id is not None:
                    await self._send_error(ws, msg_id, error_text)
            return

        if method not in {
            self.settings.moonraker_agent_method,
            self.settings.moonraker_remote_method,
        }:
            return

        msg_id = message.get("id")
        params = message.get("params")
        try:
            spool_id = self._extract_spool_id(params)
            overrides = self._extract_overrides(params)
            if spool_id is None:
                spool_id = await self._resolve_active_spool_id(ws)
            if spool_id is None:
                raise RuntimeError(
                    "spool_id not provided and active spool could not be resolved from Moonraker."
                )
            result = await self._write_tag(spool_id, overrides=overrides)
            if msg_id is not None:
                await self._send_result(ws, msg_id, result)
            await self._send_event(ws, "spool_tag_writer.tag_written", result)
        except Exception as exc:
            error_text = str(exc)
            LOG.exception("Tag write request failed: %s", error_text)
            if msg_id is not None:
                await self._send_error(ws, msg_id, error_text)
            await self._send_event(
                ws,
                "spool_tag_writer.tag_write_error",
                {"error": error_text, "params": params},
            )

    async def _identify_and_register(self, ws) -> None:
        params: dict[str, Any] = {
            "client_name": self.settings.moonraker_client_name,
            "version": self.settings.moonraker_client_version,
            "type": "agent",
            "url": self.settings.moonraker_client_url,
        }
        if self.settings.moonraker_api_key:
            params["api_key"] = self.settings.moonraker_api_key
        await self._rpc_call(ws, "server.connection.identify", params)
        registered_methods = []
        if self.settings.local_nfc_enabled:
            await self._rpc_call(
                ws,
                "connection.register_remote_method",
                {"method_name": self.settings.moonraker_remote_method},
            )
            registered_methods.append(self.settings.moonraker_remote_method)
        await self._rpc_call(
            ws,
            "connection.register_remote_method",
            {"method_name": self.settings.moonraker_show_mapping_remote_method},
        )
        registered_methods.append(self.settings.moonraker_show_mapping_remote_method)
        LOG.info(
            "Connected to Moonraker, remote methods registered: %s",
            ", ".join(registered_methods),
        )

    async def run_forever(self) -> None:
        while True:
            heartbeat_task: asyncio.Task[None] | None = None
            try:
                async with websockets.connect(
                    self.settings.moonraker_ws_url,
                    open_timeout=10,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=4 * 1024 * 1024,
                ) as ws:
                    self._backlog.clear()
                    self._last_active_tool = None
                    await self._identify_and_register(ws)
                    await self._subscribe_toolhead(ws)
                    await self._publish_status(
                        ws,
                        connected=True,
                        connected_at=utc_now_iso(),
                        last_seen_at=utc_now_iso(),
                        last_error="",
                        last_error_at="",
                    )
                    heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))
                    await self._sync_active_spool_from_mapping(ws)
                    while True:
                        if self._backlog:
                            message = self._backlog.pop(0)
                        else:
                            message = json.loads(await ws.recv())
                        await self._handle_message(ws, message)
            except ConnectionClosed as exc:
                LOG.warning("Moonraker websocket disconnected: %s", exc)
            except Exception as exc:
                LOG.warning("Moonraker agent error: %s", exc)
            finally:
                if heartbeat_task is not None:
                    heartbeat_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await heartbeat_task
            await asyncio.sleep(2)

    async def close(self) -> None:
        await self.spoolman.close()


async def _run() -> None:
    settings = get_settings()
    settings.spoolman_url = await resolve_spoolman_url(settings)
    agent = MoonrakerAgent(settings)
    try:
        await agent.run_forever()
    finally:
        await agent.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(_run())


if __name__ == "__main__":
    main()
