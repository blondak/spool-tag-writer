from __future__ import annotations

import codecs
import json
import re
from html import unescape
from typing import Any
from urllib.parse import urlparse

import httpx

from .openspool import _extract_canonical_filament_type


class PrusamentImportError(Exception):
    pass


_ALLOWED_HOSTS = {
    "prusa.io",
    "www.prusa.io",
    "prusament.com",
    "www.prusament.com",
}


def _normalize_import_url(url: str) -> str:
    normalized = url.strip()
    if not normalized:
        raise PrusamentImportError("Missing Prusament detail URL.")
    parsed = urlparse(normalized)
    if not parsed.scheme:
        normalized = f"https://{normalized}"
        parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        raise PrusamentImportError("Prusament URL must use http or https.")
    if (parsed.hostname or "").lower() not in _ALLOWED_HOSTS:
        raise PrusamentImportError("Only prusa.io and prusament.com URLs are supported.")
    return normalized


def _extract_script_blocks(html: str, script_type: str) -> list[str]:
    pattern = re.compile(
        rf"<script[^>]*type=[\"']{re.escape(script_type)}[\"'][^>]*>(.*?)</script>",
        re.IGNORECASE | re.DOTALL,
    )
    return [match.group(1).strip() for match in pattern.finditer(html)]


def _find_first_text(value: Any, keys: set[str]) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys and isinstance(item, str) and item.strip():
                return item.strip()
            found = _find_first_text(item, keys)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_first_text(item, keys)
            if found:
                return found
    return None


def _collect_json_candidates(html: str) -> dict[str, str]:
    candidates: dict[str, str] = {}

    for block in _extract_script_blocks(html, "application/ld+json"):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        name = _find_first_text(data, {"name"})
        brand = _find_first_text(data, {"brand", "manufacturer"})
        color = _find_first_text(data, {"color", "colorName"})
        if name:
            candidates.setdefault("name", name)
        if brand:
            candidates.setdefault("brand", brand)
        if color:
            candidates.setdefault("color_name", color)

    next_data_match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if next_data_match:
        try:
            data = json.loads(next_data_match.group(1))
        except json.JSONDecodeError:
            data = None
        if data is not None:
            name = _find_first_text(data, {"name", "displayName", "productName", "title"})
            color = _find_first_text(data, {"color", "colorName"})
            if name:
                candidates.setdefault("name", name)
            if color:
                candidates.setdefault("color_name", color)

    meta_patterns = {
        "name": r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']',
        "description": r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
    }
    for key, pattern in meta_patterns.items():
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            candidates.setdefault(key, unescape(match.group(1).strip()))

    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        candidates.setdefault("title", unescape(title_match.group(1).strip()))

    return candidates


def _extract_spool_data(html: str) -> dict[str, Any] | None:
    match = re.search(r"var\s+spoolData\s*=\s*", html, re.IGNORECASE)
    if not match:
        return None
    idx = match.end()
    while idx < len(html) and html[idx].isspace():
        idx += 1
    if idx >= len(html) or html[idx] not in {"'", '"'}:
        return None

    quote = html[idx]
    idx += 1
    chars: list[str] = []
    escaped = False
    while idx < len(html):
        ch = html[idx]
        if escaped:
            chars.append(ch)
            escaped = False
        elif ch == "\\":
            chars.append(ch)
            escaped = True
        elif ch == quote:
            break
        else:
            chars.append(ch)
        idx += 1
    else:
        return None

    raw = "".join(chars)
    candidates = [raw]
    try:
        unescaped = codecs.decode(raw, "unicode_escape")
    except Exception:
        unescaped = raw
    if unescaped != raw:
        candidates.append(unescaped)

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _strip_html(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_temp_range(text: str, keywords: tuple[str, ...]) -> tuple[str, str]:
    for keyword in keywords:
        pattern = re.compile(
            rf"{keyword}[^0-9]{{0,80}}(\d{{2,3}})\s*(?:-|to|–|—)\s*(\d{{2,3}})\s*°?\s*C",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            return match.group(1), match.group(2)
    return "", ""


def _derive_subtype(product_name: str, filament_type: str) -> str:
    if not product_name:
        return ""
    cleaned = re.sub(r"^\s*Prusament\s+", "", product_name, flags=re.IGNORECASE).strip()
    if not cleaned:
        return ""
    if filament_type and cleaned.upper().startswith(filament_type.upper()):
        cleaned = cleaned[len(filament_type) :].lstrip(" -")
    cleaned = re.sub(r"\s+\d+(?:[.,]\d+)?\s*kg\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\d+(?:[.,]\d+)?\s*g\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\d+(?:[.,]\d+)?\s*mm\s*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def parse_prusament_html(html: str, source_url: str) -> dict[str, Any]:
    candidates = _collect_json_candidates(html)
    spool_data = _extract_spool_data(html) or {}
    filament = spool_data.get("filament") if isinstance(spool_data.get("filament"), dict) else {}
    text = _strip_html(html)

    product_name = (
        filament.get("name")
        or candidates.get("name")
        or candidates.get("title")
        or candidates.get("description")
        or ""
    )
    filament_type = _extract_canonical_filament_type(
        filament.get("material"),
        product_name,
        candidates.get("description", ""),
        text,
    )
    min_temp = str(filament.get("he_min") or "")
    max_temp = str(filament.get("he_max") or "")
    bed_min_temp = str(filament.get("hb_min") or "")
    bed_max_temp = str(filament.get("hb_max") or "")
    if not min_temp or not max_temp:
        min_temp, max_temp = _extract_temp_range(
            text,
            ("nozzle", "print temperature", "extruder", "hotend"),
        )
    if not bed_min_temp or not bed_max_temp:
        bed_min_temp, bed_max_temp = _extract_temp_range(
            text,
            ("bed", "heatbed", "build plate"),
        )
    subtype = _derive_subtype(product_name, filament_type)

    return {
        "source": "prusament_qr",
        "source_url": source_url,
        "prusament_spool_data": spool_data,
        "external_id": str(spool_data.get("ff_goods_id") or ""),
        "article_number": str(
            spool_data.get("article_number")
            or filament.get("article_number")
            or filament.get("articleNumber")
            or ""
        ),
        "product_name": product_name,
        "brand": candidates.get("brand") or "Prusament",
        "type": filament_type,
        "subtype": subtype,
        "color_name": str(filament.get("color_name") or candidates.get("color_name", "")),
        "color_hex": str(filament.get("color_rgb") or "").lstrip("#").upper(),
        "min_temp": min_temp,
        "max_temp": max_temp,
        "bed_min_temp": bed_min_temp,
        "bed_max_temp": bed_max_temp,
        "weight_gross_g": str(spool_data.get("weight") or ""),
        "spool_weight_g": str(spool_data.get("spool_weight") or ""),
        "diameter_mm": str(spool_data.get("diameter") or ""),
        "length_m": str(spool_data.get("length") or ""),
    }


async def import_prusament_url(url: str, timeout: float) -> dict[str, Any]:
    normalized_url = _normalize_import_url(url)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.get(
                normalized_url,
                headers={"User-Agent": "spool-tag-writer/1.0 (+Prusament import)"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PrusamentImportError(f"Failed to fetch Prusament URL: {exc}") from exc

    parsed = parse_prusament_html(response.text, str(response.url))
    if not parsed["product_name"] and not parsed["type"]:
        raise PrusamentImportError("Could not extract filament data from the page.")
    return parsed
