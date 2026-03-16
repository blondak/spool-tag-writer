from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import Settings, get_settings
from .nfc import NfcError, build_nfc_backend
from .openspool import apply_openspool_overrides, build_openspool_payload
from .prusament import PrusamentImportError, import_prusament_url
from .spoolman import SpoolmanClient


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _spool_label(spool: dict[str, Any]) -> str:
    spool_id = spool.get("id", "?")
    filament = spool.get("filament") if isinstance(spool.get("filament"), dict) else {}
    filament_name = filament.get("name") or spool.get("name") or "unknown"
    material = filament.get("material") or "-"
    return f"#{spool_id} - {filament_name} ({material})"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.spoolman = SpoolmanClient(settings)
    app.state.nfc = build_nfc_backend(settings)
    yield
    await app.state.spoolman.close()


app = FastAPI(title="Spool Tag Writer", lifespan=lifespan)

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


def _empty_override_form() -> dict[str, str]:
    return {key: "" for key in OVERRIDE_KEYS}


def _normalize_form_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _parse_overrides(overrides_form: dict[str, str | None]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for key in OVERRIDE_KEYS:
        value = _normalize_form_value(overrides_form.get(key))
        if value is None:
            continue
        if key == "color_hex":
            overrides[key] = value.lstrip("#").upper()
        else:
            overrides[key] = value
    return overrides


def _form_override_values(
    type_value: str | None = None,
    color_hex: str | None = None,
    brand: str | None = None,
    min_temp: str | None = None,
    max_temp: str | None = None,
    bed_min_temp: str | None = None,
    bed_max_temp: str | None = None,
    subtype: str | None = None,
) -> dict[str, str]:
    values = {
        "type": type_value or "",
        "color_hex": color_hex or "",
        "brand": brand or "",
        "min_temp": min_temp or "",
        "max_temp": max_temp or "",
        "bed_min_temp": bed_min_temp or "",
        "bed_max_temp": bed_max_temp or "",
        "subtype": subtype or "",
    }
    return values


def _stringify_override_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _extract_override_defaults(
    spool: dict[str, Any], openspool_payload: dict[str, Any]
) -> dict[str, str]:
    _ = spool
    defaults = _empty_override_form()
    for key in OVERRIDE_KEYS:
        defaults[key] = _stringify_override_value(openspool_payload.get(key))
    return defaults


async def _list_spools(request: Request) -> list[dict[str, Any]]:
    spools = await request.app.state.spoolman.list_spools()
    spools = [spool for spool in spools if isinstance(spool, dict)]
    spools.sort(key=lambda item: item.get("id", 0))
    return spools


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
    return _extract_override_defaults(spool, payload)


async def _render_index(
    request: Request,
    *,
    spools: list[dict[str, Any]],
    error: str | None = None,
    result: dict[str, Any] | None = None,
    preview: dict[str, Any] | None = None,
    selected_spool_id: int | None = None,
    overrides_form: dict[str, str] | None = None,
    status_code: int = 200,
):
    return TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {
            "spools": spools,
            "error": error,
            "result": result,
            "preview": preview,
            "selected_spool_id": selected_spool_id,
            "spool_label": _spool_label,
            "settings": request.app.state.settings,
            "overrides_form": overrides_form or _empty_override_form(),
        },
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    error = None
    spools: list[dict[str, Any]] = []
    try:
        spools = await _list_spools(request)
    except Exception as exc:
        error = str(exc)
    return await _render_index(request, spools=spools, error=error)


@app.post("/preview", response_class=HTMLResponse)
async def preview(
    request: Request,
    spool_id: int = Form(...),
    type_value: str | None = Form(None, alias="type"),
    color_hex: str | None = Form(None),
    brand: str | None = Form(None),
    min_temp: str | None = Form(None),
    max_temp: str | None = Form(None),
    bed_min_temp: str | None = Form(None),
    bed_max_temp: str | None = Form(None),
    subtype: str | None = Form(None),
):
    overrides_form = _form_override_values(
        type_value=type_value,
        color_hex=color_hex,
        brand=brand,
        min_temp=min_temp,
        max_temp=max_temp,
        bed_min_temp=bed_min_temp,
        bed_max_temp=bed_max_temp,
        subtype=subtype,
    )
    try:
        spools = await _list_spools(request)
    except Exception:
        spools = []
    try:
        overrides = _parse_overrides(overrides_form)
        preview_data = await _build_preview(request, spool_id, overrides)
    except Exception as exc:
        return await _render_index(
            request,
            spools=spools,
            error=str(exc),
            selected_spool_id=spool_id,
            overrides_form=overrides_form,
            status_code=400,
        )
    return await _render_index(
        request,
        spools=spools,
        preview=preview_data,
        selected_spool_id=spool_id,
        overrides_form=overrides_form,
    )


@app.post("/write", response_class=HTMLResponse)
async def write_tag(
    request: Request,
    spool_id: int = Form(...),
    type_value: str | None = Form(None, alias="type"),
    color_hex: str | None = Form(None),
    brand: str | None = Form(None),
    min_temp: str | None = Form(None),
    max_temp: str | None = Form(None),
    bed_min_temp: str | None = Form(None),
    bed_max_temp: str | None = Form(None),
    subtype: str | None = Form(None),
):
    overrides_form = _form_override_values(
        type_value=type_value,
        color_hex=color_hex,
        brand=brand,
        min_temp=min_temp,
        max_temp=max_temp,
        bed_min_temp=bed_min_temp,
        bed_max_temp=bed_max_temp,
        subtype=subtype,
    )
    try:
        spools = await _list_spools(request)
    except Exception:
        spools = []
    try:
        overrides = _parse_overrides(overrides_form)
        preview_data = await _build_preview(request, spool_id, overrides)
        write_result = request.app.state.nfc.write_openspool_payload(preview_data["payload_json"])
        read_result = request.app.state.nfc.read_current_payload()
    except (NfcError, RuntimeError, ValueError) as exc:
        return await _render_index(
            request,
            spools=spools,
            error=str(exc),
            selected_spool_id=spool_id,
            overrides_form=overrides_form,
            status_code=400,
        )
    return await _render_index(
        request,
        spools=spools,
        result={"write": write_result, "read": read_result},
        preview=preview_data,
        selected_spool_id=spool_id,
        overrides_form=overrides_form,
    )


@app.post("/read", response_class=HTMLResponse)
async def read_tag(request: Request):
    try:
        spools = await _list_spools(request)
    except Exception:
        spools = []
    try:
        read_result = request.app.state.nfc.read_current_payload()
    except NfcError as exc:
        return await _render_index(
            request,
            spools=spools,
            error=str(exc),
            overrides_form=_empty_override_form(),
            status_code=400,
        )
    return await _render_index(
        request,
        spools=spools,
        result={"read": read_result},
        overrides_form=_empty_override_form(),
    )


@app.get("/api/spools")
async def api_spools(request: Request):
    try:
        return await _list_spools(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/spools/{spool_id}")
async def api_spool(request: Request, spool_id: int):
    try:
        return await request.app.state.spoolman.get_spool(spool_id)
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
        write_result = request.app.state.nfc.write_openspool_payload(preview_data["payload_json"])
        read_result = request.app.state.nfc.read_current_payload()
        return {
            "spool_id": spool_id,
            "preview": preview_data,
            "write_result": write_result,
            "readback": read_result,
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
        overrides_form = _form_override_values(
            type_value=type_value,
            color_hex=color_hex,
            brand=brand,
            min_temp=min_temp,
            max_temp=max_temp,
            bed_min_temp=bed_min_temp,
            bed_max_temp=bed_max_temp,
            subtype=subtype,
        )
        overrides = _parse_overrides(overrides_form)
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
        overrides_form = _form_override_values(
            type_value=type_value,
            color_hex=color_hex,
            brand=brand,
            min_temp=min_temp,
            max_temp=max_temp,
            bed_min_temp=bed_min_temp,
            bed_max_temp=bed_max_temp,
            subtype=subtype,
        )
        overrides = _parse_overrides(overrides_form)
        preview_data = await _build_preview(request, spool_id, overrides)
        write_result = request.app.state.nfc.write_openspool_payload(preview_data["payload_json"])
        read_result = request.app.state.nfc.read_current_payload()
        return {
            "spool_id": spool_id,
            "preview": preview_data,
            "write_result": write_result,
            "readback": read_result,
        }
    except (NfcError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/tag/read")
async def api_read_tag(request: Request):
    try:
        return request.app.state.nfc.read_current_payload()
    except NfcError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
