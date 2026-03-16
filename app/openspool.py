from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


CANONICAL_FILAMENT_TYPES = (
    "PLA",
    "ABS",
    "ASA",
    "ASA-CF",
    "PETG",
    "PCTG",
    "TPU",
    "TPU-AMS",
    "PC",
    "PA",
    "PA-CF",
    "PA-GF",
    "PA6-CF",
    "PLA-CF",
    "PET-CF",
    "PETG-CF",
    "PVA",
    "HIPS",
    "PLA-AERO",
    "PPS",
    "PPS-CF",
    "PPA-CF",
    "PPA-GF",
    "ABS-GF",
    "ASA-Aero",
    "PE",
    "PP",
    "EVA",
    "PHA",
    "BVOH",
    "PE-CF",
    "PP-CF",
    "PP-GF",
)

_NORMALIZED_CANONICAL_FILAMENT_TYPES = {
    re.sub(r"[^A-Z0-9]+", "", item.upper()): item for item in CANONICAL_FILAMENT_TYPES
}

_FILAMENT_TYPE_ALIASES = {
    "NYLON": "PA",
    "PACF": "PA-CF",
    "PAGF": "PA-GF",
    "NYLONCF": "PA-CF",
    "NYLONGF": "PA-GF",
    "NYLON6CF": "PA6-CF",
    "PA12CF": "PA-CF",
    "PAHTCF": "PA-CF",
    "PA6GF": "PA-GF",
    "PLAWOOD": "PLA",
    "PLASILK": "PLA",
    "MATTEPLA": "PLA",
    "TOUGHPLA": "PLA",
    "HIGHTEMPPLA": "PLA",
    "PET": "PETG",
    "TPU95A": "TPU",
    "TPU85A": "TPU",
    "TPE": "TPU",
    "BAMBUTPUFORAMS": "TPU-AMS",
    "TPUFORAMS": "TPU-AMS",
    "POLYCARBONATE": "PC",
    "POLYPROPYLENE": "PP",
    "POLYETHYLENE": "PE",
}

def _first_non_null(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _to_color_hex(value: Any) -> str:
    text = _to_text(value).strip()
    if text.startswith("#"):
        text = text[1:]
    return text.upper()


def _normalize_filament_token(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", _to_text(value).strip().upper())


def _derive_filament_subtype(name: Any, filament_type: str, brand: Any = None) -> str:
    cleaned = _to_text(name).strip()
    if not cleaned:
        return ""
    brand_text = _to_text(brand).strip()
    if brand_text:
        cleaned = re.sub(rf"^\s*{re.escape(brand_text)}\s+", "", cleaned, flags=re.IGNORECASE)
    if filament_type and cleaned.upper().startswith(filament_type.upper()):
        cleaned = cleaned[len(filament_type) :].lstrip(" -")
    cleaned = re.sub(r"\s+\d+(?:[.,]\d+)?\s*kg\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\d+(?:[.,]\d+)?\s*g\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\d+(?:[.,]\d+)?\s*mm\s*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _extract_canonical_filament_type(*values: Any) -> str:
    raw_values = [_to_text(value).strip() for value in values if _to_text(value).strip()]
    for raw in raw_values:
        normalized = _normalize_filament_token(raw)
        if normalized in _NORMALIZED_CANONICAL_FILAMENT_TYPES:
            return _NORMALIZED_CANONICAL_FILAMENT_TYPES[normalized]
        if normalized in _FILAMENT_TYPE_ALIASES:
            return _FILAMENT_TYPE_ALIASES[normalized]

    combined = " ".join(raw_values).upper()
    checks = (
        (("ASA", "CF"), "ASA-CF"),
        (("ASA", "AERO"), "ASA-Aero"),
        (("ABS", "GF"), "ABS-GF"),
        (("PETG", "CF"), "PETG-CF"),
        (("PET", "CF"), "PET-CF"),
        (("PLA", "CF"), "PLA-CF"),
        (("PLA", "AERO"), "PLA-AERO"),
        (("PPS", "CF"), "PPS-CF"),
        (("PPA", "CF"), "PPA-CF"),
        (("PPA", "GF"), "PPA-GF"),
        (("PA6", "CF"), "PA6-CF"),
        (("PA", "CF"), "PA-CF"),
        (("PA", "GF"), "PA-GF"),
        (("NYLON", "CF"), "PA-CF"),
        (("NYLON", "GF"), "PA-GF"),
        (("PE", "CF"), "PE-CF"),
        (("PP", "CF"), "PP-CF"),
        (("PP", "GF"), "PP-GF"),
        (("TPU", "AMS"), "TPU-AMS"),
        (("BVOH",), "BVOH"),
        (("PVA",), "PVA"),
        (("HIPS",), "HIPS"),
        (("PCTG",), "PCTG"),
        (("PETG",), "PETG"),
        (("TPU",), "TPU"),
        (("ABS",), "ABS"),
        (("ASA",), "ASA"),
        (("PLA",), "PLA"),
        (("PPS",), "PPS"),
        (("NYLON",), "PA"),
        (("PA",), "PA"),
        (("PC",), "PC"),
        (("PP",), "PP"),
        (("PE",), "PE"),
        (("EVA",), "EVA"),
        (("PHA",), "PHA"),
    )
    for needles, canonical in checks:
        if all(needle in combined for needle in needles):
            return canonical

    return raw_values[0] if raw_values else ""


def build_openspool_payload(spool: dict[str, Any], spoolman_url: str) -> dict[str, Any]:
    _ = spoolman_url
    filament = spool.get("filament") if isinstance(spool.get("filament"), dict) else {}
    vendor = filament.get("vendor") if isinstance(filament.get("vendor"), dict) else {}
    filament_extra = filament.get("extra") if isinstance(filament.get("extra"), dict) else {}
    bed_temp_common = _first_non_null(filament, "bed_temperature", "bedTemperature")
    brand = _to_text(
        _first_non_null(vendor, "name", "brand", "manufacturer")
        or _first_non_null(filament, "brand", "manufacturer")
    )
    filament_type = _extract_canonical_filament_type(
        _first_non_null(filament, "material", "material_name", "type"),
        _first_non_null(filament, "name", "filament_name"),
        _first_non_null(filament, "subtype", "sub_type", "variant"),
    )

    payload = {
        "protocol": "openspool",
        "version": "1.0",
        "type": filament_type,
        "color_hex": _to_color_hex(_first_non_null(filament, "color_hex", "colorHex")),
        "brand": brand,
        "min_temp": _to_text(
            _first_non_null(
                filament,
                "min_temperature",
                "minTemperature",
                "temperature_min",
                "temperatureMin",
                "print_temperature_min",
                "settings_extruder_temp",
            )
        ),
        "max_temp": _to_text(
            _first_non_null(
                filament_extra,
                "max_temp",
                "maxTemperature",
                "max_temperature",
            )
            or _first_non_null(
                filament,
                "max_temperature",
                "maxTemperature",
                "temperature_max",
                "temperatureMax",
                "print_temperature_max",
            )
        ),
        "bed_min_temp": _to_text(
            _first_non_null(
                filament,
                "bed_min_temperature",
                "bedTemperatureMin",
                "bed_temperature_min",
                "settings_bed_temp",
            )
            or bed_temp_common
        ),
        "bed_max_temp": _to_text(
            _first_non_null(
                filament_extra,
                "bed_max_temp",
                "bedTemperatureMax",
                "bed_max_temperature",
                "bed_temperature_max",
            )
            or bed_temp_common
        ),
        "subtype": _to_text(
            _first_non_null(filament, "subtype", "sub_type", "variant")
            or _derive_filament_subtype(
                _first_non_null(filament, "name", "filament_name"),
                filament_type,
                brand,
            )
            or ""
        ),
        "spoolman_id": _to_text(spool.get("id")),
    }
    return payload


def apply_openspool_overrides(
    payload: dict[str, Any], overrides: dict[str, Any] | None
) -> dict[str, Any]:
    if not overrides:
        return payload

    out = deepcopy(payload)
    mapping = {
        "type": "type",
        "color_hex": "color_hex",
        "brand": "brand",
        "min_temp": "min_temp",
        "max_temp": "max_temp",
        "bed_min_temp": "bed_min_temp",
        "bed_max_temp": "bed_max_temp",
        "subtype": "subtype",
    }
    for key, value in overrides.items():
        if value is None:
            continue
        target_key = mapping.get(key)
        if not target_key:
            continue
        if target_key == "color_hex":
            out[target_key] = _to_color_hex(value)
        elif target_key == "type":
            out[target_key] = _extract_canonical_filament_type(value)
        else:
            out[target_key] = _to_text(value)
    return out
