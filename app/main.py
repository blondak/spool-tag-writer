from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .moonraker import (
    MoonrakerClient,
    is_agent_status_online,
    resolve_spoolman_url,
    spool_id_for_tool,
)
from .nfc import NfcError, build_nfc_backend
from .openspool import apply_openspool_overrides, build_openspool_payload
from .prusament import PrusamentImportError, import_prusament_url
from .spoolman import SpoolmanClient


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIST_DIR = STATIC_DIR / "dist"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.spoolman_url = await resolve_spoolman_url(settings)
    app.state.settings = settings
    app.state.moonraker = MoonrakerClient(settings)
    app.state.spoolman = SpoolmanClient(settings)
    app.state.nfc = build_nfc_backend(settings)
    yield
    await app.state.moonraker.close()
    await app.state.spoolman.close()


app = FastAPI(title="Spool Tag Writer", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

OVERRIDE_KEYS = (
    "type",
    "color_hex",
    "brand",
    "min_temp",
    "max_temp",
    "bed_min_temp",
    "bed_max_temp",
    "subtype",
)


def _normalize_override_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _describe_exception(exc: Exception) -> str:
    detail = str(exc).strip()
    return detail or exc.__class__.__name__


@app.exception_handler(Exception)
async def api_exception_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {_describe_exception(exc)}"},
        )

    return HTMLResponse("Internal Server Error", status_code=500)


def _build_overrides(
    *,
    type_value: str | None = None,
    color_hex: str | None = None,
    brand: str | None = None,
    min_temp: str | None = None,
    max_temp: str | None = None,
    bed_min_temp: str | None = None,
    bed_max_temp: str | None = None,
    subtype: str | None = None,
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    raw_values = {
        "type": type_value,
        "color_hex": color_hex,
        "brand": brand,
        "min_temp": min_temp,
        "max_temp": max_temp,
        "bed_min_temp": bed_min_temp,
        "bed_max_temp": bed_max_temp,
        "subtype": subtype,
    }
    for key, raw_value in raw_values.items():
        value = _normalize_override_value(raw_value)
        if value is None:
            continue
        if key == "color_hex":
            overrides[key] = value.lstrip("#").upper()
        else:
            overrides[key] = value
    return overrides


def _stringify_override_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _extract_override_defaults(openspool_payload: dict[str, Any]) -> dict[str, str]:
    return {
        key: _stringify_override_value(openspool_payload.get(key))
        for key in OVERRIDE_KEYS
    }


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_spool_manufacturer(spool: dict[str, Any]) -> str:
    filament = spool.get("filament")
    if not isinstance(filament, dict):
        return ""

    for source in (filament.get("vendor"), filament.get("manufacturer")):
        if isinstance(source, dict):
            for key in ("name", "manufacturer", "brand"):
                text = _coerce_text(source.get(key))
                if text:
                    return text
        else:
            text = _coerce_text(source)
            if text:
                return text

    for key in ("manufacturer_name", "brand", "manufacturer"):
        text = _coerce_text(filament.get(key))
        if text:
            return text

    return _coerce_text(spool.get("manufacturer"))


def _serialize_spool_for_ui(spool: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(spool)
    manufacturer = _extract_spool_manufacturer(serialized)
    if manufacturer:
        serialized["manufacturer"] = manufacturer
    return serialized


async def _list_spools(request: Request) -> list[dict[str, Any]]:
    spools = await request.app.state.spoolman.list_spools()
    spools = [spool for spool in spools if isinstance(spool, dict)]
    spools.sort(key=lambda item: item.get("id", 0))
    return [_serialize_spool_for_ui(spool) for spool in spools]


async def _build_preview(
    request: Request, spool_id: int, overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    spool = await request.app.state.spoolman.get_spool(spool_id)
    payload = build_openspool_payload(spool, settings.spoolman_url)
    payload = apply_openspool_overrides(payload, overrides)
    payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return {
        "spool": spool,
        "payload": payload,
        "payload_json": payload_json,
        "payload_size": len(payload_json.encode("utf-8")),
        "overrides": overrides or {},
    }


async def _build_override_defaults(request: Request, spool_id: int) -> dict[str, str]:
    settings: Settings = request.app.state.settings
    spool = await request.app.state.spoolman.get_spool(spool_id)
    payload = build_openspool_payload(spool, settings.spoolman_url)
    return _extract_override_defaults(payload)


async def _write_preview_to_tag(
    request: Request, preview_data: dict[str, Any]
) -> dict[str, Any]:
    write_result = request.app.state.nfc.write_openspool_payload(preview_data["payload_json"])
    read_result = request.app.state.nfc.read_current_payload()
    return {
        "preview": preview_data,
        "write_result": write_result,
        "readback": read_result,
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    if FRONTEND_INDEX_FILE.exists():
        return FileResponse(FRONTEND_INDEX_FILE)

    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Spool Tag Writer</title>
          </head>
          <body>
            <main style="max-width:42rem;margin:4rem auto;font-family:system-ui,sans-serif;line-height:1.5;">
              <h1>Frontend build is missing</h1>
              <p>Run <code>npm install</code> and <code>npm run build</code> to generate the Vue/AdminLTE bundle.</p>
            </main>
          </body>
        </html>
        """,
        status_code=503,
    )


@app.get("/api/ui-context")
async def api_ui_context(request: Request):
    settings: Settings = request.app.state.settings
    return {
        "nfc_backend": settings.nfc_backend,
        "nfc_reader_name": settings.nfc_reader_name,
        "spoolman_url": settings.spoolman_url,
    }


@app.get("/api/spools")
async def api_spools(request: Request):
    try:
        return await _list_spools(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/extruder-mapping")
async def api_get_extruder_mapping(request: Request):
    try:
        return await request.app.state.moonraker.get_extruder_mapping()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/extruder-mapping")
async def api_put_extruder_mapping(request: Request, mapping: dict[str, Any]):
    try:
        return await request.app.state.moonraker.save_extruder_mapping(mapping)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/moonraker/spool-sync-status")
async def api_get_moonraker_spool_sync_status(request: Request):
    try:
        mapping = await request.app.state.moonraker.get_extruder_mapping()
        active_tool = await request.app.state.moonraker.get_active_tool()
        active_spool_id = await request.app.state.moonraker.get_active_spool_id()
        mapped_spool_id = spool_id_for_tool(mapping, active_tool)
        spoolman_status = await request.app.state.moonraker.get_spoolman_status()
        agent_status = await request.app.state.moonraker.get_agent_status()
        agent_online = is_agent_status_online(agent_status)
        return {
            "active_tool": active_tool,
            "active_spool_id": active_spool_id,
            "mapped_spool_id": mapped_spool_id,
            "sync_ok": active_spool_id == mapped_spool_id,
            "spoolman_connected": bool(spoolman_status.get("spoolman_connected")),
            "agent_status": {
                **agent_status,
                "online": agent_online,
                "stale": bool(agent_status.get("connected")) and not agent_online,
            },
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/printer/rfid/channels/{channel}")
async def api_get_printer_rfid_channel(
    request: Request,
    channel: int,
    refresh: bool = Query(True),
):
    try:
        rfid_channel = await request.app.state.moonraker.get_filament_detect_channel(
            channel,
            refresh=refresh,
        )
        matched_spools: list[dict[str, Any]] = []
        lot_nr = str(rfid_channel.get("card_uid") or "").strip()
        if lot_nr:
            matched_spools = [
                _serialize_spool_for_ui(spool)
                for spool in await request.app.state.spoolman.find_spools_by_lot_nr(lot_nr)
            ]
        return {
            **rfid_channel,
            "matched_spools": matched_spools,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/spools/{spool_id}/lot-nr/from-printer-rfid")
async def api_assign_spool_lot_nr_from_printer_rfid(
    request: Request,
    spool_id: int,
    channel: int = Query(...),
    refresh: bool = Query(True),
):
    try:
        rfid_channel = await request.app.state.moonraker.get_filament_detect_channel(
            channel,
            refresh=refresh,
        )
        lot_nr = str(rfid_channel.get("card_uid") or "").strip()
        if not lot_nr:
            raise RuntimeError(
                f"No RFID UID was detected on {rfid_channel.get('label') or f'channel {channel}'}."
            )

        cleared_spools: list[dict[str, Any]] = []
        existing_spools = await request.app.state.spoolman.find_spools_by_lot_nr(
            lot_nr,
            exclude_spool_id=spool_id,
        )
        for existing_spool in existing_spools:
            try:
                existing_id = int(existing_spool.get("id"))
            except (TypeError, ValueError):
                continue
            cleared = await request.app.state.spoolman.update_spool_lot_nr(existing_id, None)
            cleared_spools.append(_serialize_spool_for_ui(cleared))

        updated_spool = await request.app.state.spoolman.update_spool_lot_nr(spool_id, lot_nr)
        return {
            "spool": _serialize_spool_for_ui(updated_spool),
            "cleared_spools": cleared_spools,
            "rfid_channel": rfid_channel,
            "lot_nr": lot_nr,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/spools/{spool_id}")
async def api_spool(request: Request, spool_id: int):
    try:
        spool = await request.app.state.spoolman.get_spool(spool_id)
        return _serialize_spool_for_ui(spool)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/spools/{spool_id}/overrides-defaults")
async def api_spool_override_defaults(request: Request, spool_id: int):
    try:
        return await _build_override_defaults(request, spool_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/import/prusament")
async def api_import_prusament(
    request: Request,
    url: str = Query(...),
):
    try:
        imported = await import_prusament_url(
            url,
            timeout=request.app.state.settings.request_timeout_seconds,
        )
        filament_match = None
        external_id = str(imported.get("external_id") or "").strip()
        brand = str(imported.get("brand") or "").strip()
        if external_id and brand:
            filament_match = await request.app.state.spoolman.find_filament_by_external_id_and_vendor(
                external_id=external_id,
                vendor_name=brand,
            )
        imported["spoolman_filament_match"] = {
            "matched": filament_match is not None,
            "filament": filament_match,
        }
        return imported
    except PrusamentImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/spoolman/filaments/create-from-prusament")
async def api_create_spoolman_filament_from_prusament(
    request: Request,
    url: str = Query(...),
):
    try:
        imported = await import_prusament_url(
            url,
            timeout=request.app.state.settings.request_timeout_seconds,
        )
        created = await request.app.state.spoolman.create_filament_from_prusament_import(imported)
        return {
            "source_url": imported.get("source_url"),
            "external_id": imported.get("external_id"),
            "brand": imported.get("brand"),
            "created_filament": created,
        }
    except PrusamentImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/spoolman/spools/create-from-prusament")
async def api_create_spoolman_spool_from_prusament(
    request: Request,
    url: str = Query(...),
):
    try:
        imported = await import_prusament_url(
            url,
            timeout=request.app.state.settings.request_timeout_seconds,
        )
        created = await request.app.state.spoolman.create_spool_from_prusament_import(imported)
        return {
            "source_url": imported.get("source_url"),
            "external_id": imported.get("external_id"),
            "brand": imported.get("brand"),
            "filament": created.get("filament"),
            "spool": created.get("spool"),
        }
    except PrusamentImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/preview")
async def api_preview(request: Request, spool_id: int = Query(...)):
    try:
        return await _build_preview(request, spool_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/write")
async def api_write(request: Request, spool_id: int = Query(...)):
    try:
        preview_data = await _build_preview(request, spool_id)
        return {
            "spool_id": spool_id,
            **(await _write_preview_to_tag(request, preview_data)),
        }
    except (NfcError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/preview/with-overrides")
async def api_preview_with_overrides(
    request: Request,
    spool_id: int = Query(...),
    type_value: str | None = Query(None, alias="type"),
    color_hex: str | None = Query(None),
    brand: str | None = Query(None),
    min_temp: str | None = Query(None),
    max_temp: str | None = Query(None),
    bed_min_temp: str | None = Query(None),
    bed_max_temp: str | None = Query(None),
    subtype: str | None = Query(None),
):
    try:
        overrides = _build_overrides(
            type_value=type_value,
            color_hex=color_hex,
            brand=brand,
            min_temp=min_temp,
            max_temp=max_temp,
            bed_min_temp=bed_min_temp,
            bed_max_temp=bed_max_temp,
            subtype=subtype,
        )
        return await _build_preview(request, spool_id, overrides)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/write/with-overrides")
async def api_write_with_overrides(
    request: Request,
    spool_id: int = Query(...),
    type_value: str | None = Query(None, alias="type"),
    color_hex: str | None = Query(None),
    brand: str | None = Query(None),
    min_temp: str | None = Query(None),
    max_temp: str | None = Query(None),
    bed_min_temp: str | None = Query(None),
    bed_max_temp: str | None = Query(None),
    subtype: str | None = Query(None),
):
    try:
        overrides = _build_overrides(
            type_value=type_value,
            color_hex=color_hex,
            brand=brand,
            min_temp=min_temp,
            max_temp=max_temp,
            bed_min_temp=bed_min_temp,
            bed_max_temp=bed_max_temp,
            subtype=subtype,
        )
        preview_data = await _build_preview(request, spool_id, overrides)
        return {
            "spool_id": spool_id,
            **(await _write_preview_to_tag(request, preview_data)),
        }
    except (NfcError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/tag/read")
async def api_read_tag(request: Request):
    try:
        return request.app.state.nfc.read_current_payload()
    except (NfcError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=_describe_exception(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"NFC read failed: {_describe_exception(exc)}",
        ) from exc
