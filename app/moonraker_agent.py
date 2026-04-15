from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from .config import Settings, get_settings
from .moonraker import resolve_spoolman_url
from .nfc import build_nfc_backend
from .openspool import apply_openspool_overrides, build_openspool_payload
from .spoolman import SpoolmanClient


LOG = logging.getLogger("spool_tag_writer.moonraker_agent")


class MoonrakerAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.spoolman = SpoolmanClient(settings)
        self.nfc = build_nfc_backend(settings)
        self._rpc_id = 0
        self._backlog: list[dict[str, Any]] = []

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

    async def _handle_message(self, ws, message: dict[str, Any]) -> None:
        method = message.get("method")
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
        await self._rpc_call(
            ws,
            "connection.register_remote_method",
            {"method_name": self.settings.moonraker_remote_method},
        )
        LOG.info(
            "Connected to Moonraker, remote method registered: %s",
            self.settings.moonraker_remote_method,
        )

    async def run_forever(self) -> None:
        while True:
            try:
                async with websockets.connect(
                    self.settings.moonraker_ws_url,
                    open_timeout=10,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=4 * 1024 * 1024,
                ) as ws:
                    self._backlog.clear()
                    await self._identify_and_register(ws)
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
