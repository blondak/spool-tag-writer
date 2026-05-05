from __future__ import annotations

import math
from typing import Any

import httpx

from .config import Settings


DEFAULT_MATERIAL_DENSITIES = {
    "PLA": 1.24,
    "PLA-CF": 1.25,
    "PLA-AERO": 1.0,
    "ABS": 1.04,
    "ABS-GF": 1.08,
    "ASA": 1.07,
    "ASA-CF": 1.1,
    "PETG": 1.27,
    "PETG-CF": 1.3,
    "PET-CF": 1.3,
    "PCTG": 1.23,
    "TPU": 1.21,
    "TPU-AMS": 1.21,
    "PC": 1.2,
    "PA": 1.14,
    "PA-CF": 1.15,
    "PA-GF": 1.2,
    "PA6-CF": 1.15,
    "PVA": 1.23,
    "BVOH": 1.21,
    "HIPS": 1.04,
    "PPS": 1.35,
    "PPS-CF": 1.36,
    "PPA-CF": 1.15,
    "PPA-GF": 1.2,
    "PE": 0.95,
    "PE-CF": 1.0,
    "PP": 0.9,
    "PP-CF": 0.95,
    "PP-GF": 1.02,
    "EVA": 0.95,
    "PHA": 1.25,
}


class SpoolmanClient:
    def __init__(self, settings: Settings) -> None:
        headers: dict[str, str] = {}
        if settings.spoolman_api_key:
            headers[settings.spoolman_api_header] = settings.spoolman_api_key
        ca_bundle = (settings.spoolman_ca_bundle or "").strip()
        verify: bool | str = ca_bundle if ca_bundle else settings.spoolman_ssl_verify
        self._client = httpx.AsyncClient(
            base_url=settings.spoolman_url.rstrip("/"),
            timeout=settings.request_timeout_seconds,
            headers=headers,
            verify=verify,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _describe_http_error(exc: httpx.HTTPError) -> str:
        message = str(exc).strip() or exc.__class__.__name__
        if "certificate verify failed" in message.lower() or "CERTIFICATE_VERIFY_FAILED" in message:
            return (
                f"{message}. Configure SPOOLMAN_CA_BUNDLE with the internal CA certificate PEM, "
                "or set SPOOLMAN_SSL_VERIFY=false only for temporary testing."
            )
        return message

    async def _first_ok(self, paths: list[str], *, params: dict[str, Any] | None = None) -> Any:
        last_exc: httpx.HTTPError | None = None
        for path in paths:
            try:
                response = await self._client.get(path, params=params)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                last_exc = exc
        if last_exc:
            raise RuntimeError(f"Spoolman request failed: {self._describe_http_error(last_exc)}") from last_exc
        raise RuntimeError("No compatible Spoolman endpoint found.")

    async def _first_post_ok(self, paths: list[str], payloads: list[dict[str, Any]]) -> Any:
        last_error_text: str | None = None
        for path in paths:
            for payload in payloads:
                try:
                    response = await self._client.post(path, json=payload)
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPError as exc:
                    response = getattr(exc, "response", None)
                    if response is not None:
                        last_error_text = (
                            f"Spoolman request failed: {exc}. "
                            f"Response body: {response.text}. "
                            f"Payload: {payload}"
                        )
                    else:
                        last_error_text = f"Spoolman request failed: {self._describe_http_error(exc)}. Payload: {payload}"
        if last_error_text:
            raise RuntimeError(last_error_text)
        raise RuntimeError("No compatible Spoolman endpoint found.")

    async def _first_patch_ok(self, paths: list[str], payload: dict[str, Any]) -> Any:
        last_error_text: str | None = None
        for path in paths:
            try:
                response = await self._client.patch(path, json=payload)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                response = getattr(exc, "response", None)
                if response is not None:
                    last_error_text = (
                        f"Spoolman request failed: {exc}. "
                        f"Response body: {response.text}. "
                        f"Payload: {payload}"
                    )
                else:
                    last_error_text = f"Spoolman request failed: {self._describe_http_error(exc)}. Payload: {payload}"
        if last_error_text:
            raise RuntimeError(last_error_text)
        raise RuntimeError("No compatible Spoolman endpoint found.")

    async def list_spools(self, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        data = await self._first_ok(["/api/v1/spool", "/api/v1/spools"], params=params)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "results", "data", "spools"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        raise RuntimeError("Unexpected spool list response format from Spoolman.")

    async def list_filaments(self) -> list[dict[str, Any]]:
        data = await self._first_ok(["/api/v1/filament", "/api/v1/filaments"])
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "results", "data", "filaments"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        raise RuntimeError("Unexpected filament list response format from Spoolman.")

    async def get_spool(self, spool_id: int) -> dict[str, Any]:
        data = await self._first_ok(
            [f"/api/v1/spool/{spool_id}", f"/api/v1/spools/{spool_id}"]
        )
        if isinstance(data, dict):
            return data
        raise RuntimeError("Unexpected spool detail response format from Spoolman.")

    async def find_spools_by_lot_nr(
        self,
        lot_nr: str,
        *,
        exclude_spool_id: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_lot_nr = self._normalize_lot_nr(lot_nr)
        if not normalized_lot_nr:
            return []

        spools = await self.list_spools(
            params={
                "allow_archived": "true",
                "lot_nr": normalized_lot_nr,
            }
        )
        matches: list[dict[str, Any]] = []
        for spool in spools:
            if not isinstance(spool, dict):
                continue
            if exclude_spool_id is not None and str(spool.get("id")) == str(exclude_spool_id):
                continue
            if normalized_lot_nr in self._split_lot_nr_tokens(spool.get("lot_nr")):
                matches.append(spool)
        return matches

    async def update_spool_lot_nr(self, spool_id: int, lot_nr: str | None) -> dict[str, Any]:
        normalized_lot_nr = self._join_lot_nr_tokens(self._split_lot_nr_tokens(lot_nr)) or None
        data = await self._first_patch_ok(
            [f"/api/v1/spool/{spool_id}", f"/api/v1/spools/{spool_id}"],
            {"lot_nr": normalized_lot_nr},
        )
        if isinstance(data, dict):
            return data
        raise RuntimeError("Unexpected spool update response format from Spoolman.")

    @classmethod
    def add_lot_nr_token(cls, current_lot_nr: Any, token: str) -> str | None:
        normalized_token = cls._normalize_lot_nr(token)
        if not normalized_token:
            return cls._join_lot_nr_tokens(cls._split_lot_nr_tokens(current_lot_nr)) or None

        tokens = cls._split_lot_nr_tokens(current_lot_nr)
        if normalized_token not in tokens:
            tokens.append(normalized_token)
        return cls._join_lot_nr_tokens(tokens) or None

    @classmethod
    def remove_lot_nr_token(cls, current_lot_nr: Any, token: str) -> str | None:
        normalized_token = cls._normalize_lot_nr(token)
        if not normalized_token:
            return cls._join_lot_nr_tokens(cls._split_lot_nr_tokens(current_lot_nr)) or None

        tokens = [item for item in cls._split_lot_nr_tokens(current_lot_nr) if item != normalized_token]
        return cls._join_lot_nr_tokens(tokens) or None

    async def list_vendors(self) -> list[dict[str, Any]]:
        data = await self._first_ok(["/api/v1/vendor", "/api/v1/vendors"])
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "results", "data", "vendors"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        raise RuntimeError("Unexpected vendor list response format from Spoolman.")

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip().casefold()

    @staticmethod
    def _normalize_lot_nr(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text:
            return ""

        normalized = text.casefold()
        if normalized.startswith("0x"):
            normalized = normalized[2:]
        normalized = normalized.replace(":", "").replace("-", "").replace(" ", "")
        if normalized and all(char in "0123456789abcdef" for char in normalized):
            return f"0x{normalized}"
        return text

    @classmethod
    def _split_lot_nr_tokens(cls, value: Any) -> list[str]:
        if value is None:
            return []

        raw_tokens = str(value).split(",")
        tokens: list[str] = []
        seen: set[str] = set()
        for raw_token in raw_tokens:
            normalized = cls._normalize_lot_nr(raw_token)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tokens.append(normalized)
        return tokens

    @staticmethod
    def _join_lot_nr_tokens(tokens: list[str]) -> str:
        return ",".join(str(token).strip() for token in tokens if str(token).strip())

    @staticmethod
    def _resolve_import_external_id(imported: dict[str, Any]) -> str:
        article_number = str(imported.get("article_number") or "").strip()
        product_name = str(imported.get("product_name") or "").strip()
        imported_external_id = str(imported.get("external_id") or "").strip()
        return article_number or product_name or imported_external_id

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).strip())
        except ValueError:
            return None

    @classmethod
    def _calculate_density(
        cls,
        *,
        weight_gross_g: Any,
        spool_weight_g: Any,
        length_m: Any,
        diameter_mm: Any,
    ) -> float | None:
        gross_weight = cls._to_float(weight_gross_g)
        empty_spool_weight = cls._to_float(spool_weight_g)
        length_m_value = cls._to_float(length_m)
        diameter_mm_value = cls._to_float(diameter_mm)
        if (
            gross_weight is None
            or length_m_value is None
            or diameter_mm_value is None
        ):
            return None
        _ = empty_spool_weight
        if gross_weight <= 0 or length_m_value <= 0 or diameter_mm_value <= 0:
            return None

        radius_cm = (diameter_mm_value / 10.0) / 2.0
        length_cm = length_m_value * 100.0
        volume_cm3 = math.pi * (radius_cm ** 2) * length_cm
        if volume_cm3 <= 0:
            return None
        return round(gross_weight / volume_cm3, 4)

    @classmethod
    def _find_external_ids(cls, value: Any) -> set[str]:
        matches: set[str] = set()
        if isinstance(value, dict):
            for key, item in value.items():
                normalized_key = cls._normalize_text(key)
                if normalized_key == "external_id" and item is not None:
                    normalized = cls._normalize_text(item)
                    if normalized:
                        matches.add(normalized)
                if normalized_key != "extra":
                    matches.update(cls._find_external_ids(item))
        elif isinstance(value, list):
            for item in value:
                matches.update(cls._find_external_ids(item))
        return matches

    @classmethod
    def _extract_vendor_name(cls, filament: dict[str, Any]) -> str:
        for key in ("vendor", "manufacturer"):
            value = filament.get(key)
            if isinstance(value, dict):
                name = value.get("name")
                if name:
                    return str(name)
            elif value:
                return str(value)
        return str(filament.get("brand") or "")

    async def find_filament_by_external_id_and_vendor(
        self,
        *,
        external_id: str,
        vendor_name: str,
    ) -> dict[str, Any] | None:
        normalized_external_id = self._normalize_text(external_id)
        normalized_vendor_name = self._normalize_text(vendor_name)
        if not normalized_external_id or not normalized_vendor_name:
            return None

        filaments = await self.list_filaments()
        for filament in filaments:
            if not isinstance(filament, dict):
                continue
            vendor_match = self._normalize_text(self._extract_vendor_name(filament))
            if vendor_match != normalized_vendor_name:
                continue
            if normalized_external_id in self._find_external_ids(filament):
                return filament
        return None

    async def find_vendor_by_name(self, vendor_name: str) -> dict[str, Any] | None:
        normalized_vendor_name = self._normalize_text(vendor_name)
        if not normalized_vendor_name:
            return None
        vendors = await self.list_vendors()
        for vendor in vendors:
            if not isinstance(vendor, dict):
                continue
            if self._normalize_text(vendor.get("name")) == normalized_vendor_name:
                return vendor
        return None

    async def ensure_vendor(self, vendor_name: str) -> dict[str, Any]:
        existing = await self.find_vendor_by_name(vendor_name)
        if existing is not None:
            return existing
        data = await self._first_post_ok(
            ["/api/v1/vendor", "/api/v1/vendors"],
            [{"name": vendor_name}],
        )
        if isinstance(data, dict):
            return data
        raise RuntimeError("Unexpected vendor create response format from Spoolman.")

    async def create_filament_from_prusament_import(
        self,
        imported: dict[str, Any],
    ) -> dict[str, Any]:
        brand = str(imported.get("brand") or "").strip()
        article_number = str(imported.get("article_number") or "").strip()
        product_name = str(imported.get("product_name") or "").strip()
        effective_external_id = self._resolve_import_external_id(imported)
        material = str(imported.get("type") or "").strip()
        color_hex = str(imported.get("color_hex") or "").strip()
        min_temp = str(imported.get("min_temp") or "").strip()
        max_temp = str(imported.get("max_temp") or "").strip()
        bed_min_temp = str(imported.get("bed_min_temp") or "").strip()
        bed_max_temp = str(imported.get("bed_max_temp") or "").strip()
        weight_gross_g = str(imported.get("weight_gross_g") or "").strip()
        spool_weight_g = str(imported.get("spool_weight_g") or "").strip()
        diameter_mm = str(imported.get("diameter_mm") or "").strip()
        length_m = str(imported.get("length_m") or "").strip()

        if not brand:
            raise RuntimeError("Prusament import does not contain a brand for filament creation.")
        if not product_name:
            raise RuntimeError("Prusament import does not contain product_name for filament creation.")
        if not material:
            raise RuntimeError("Prusament import does not contain type/material for filament creation.")

        lookup_external_id = effective_external_id
        existing = await self.find_filament_by_external_id_and_vendor(
            external_id=lookup_external_id,
            vendor_name=brand,
        ) if lookup_external_id else None
        if existing is not None:
            return existing

        vendor = await self.ensure_vendor(brand)
        vendor_id = vendor.get("id")
        if vendor_id is None:
            raise RuntimeError("Vendor create response from Spoolman does not contain an id.")

        try:
            diameter_value = float(diameter_mm) if diameter_mm else 1.75
        except ValueError:
            diameter_value = 1.75
        density_value = self._calculate_density(
            weight_gross_g=weight_gross_g,
            spool_weight_g=spool_weight_g,
            length_m=length_m,
            diameter_mm=diameter_value,
        )
        if density_value is None:
            density_value = DEFAULT_MATERIAL_DENSITIES.get(material, 1.24)
        payload = {
            "vendor_id": vendor_id,
            "name": product_name,
            "material": material,
            "diameter": diameter_value,
            "density": density_value,
        }
        payload["extra"] = {}
        if article_number:
            payload["article_number"] = article_number
        if effective_external_id:
            payload["external_id"] = effective_external_id
        if color_hex:
            payload["color_hex"] = color_hex
        if min_temp:
            try:
                payload["settings_extruder_temp"] = int(float(min_temp))
            except ValueError:
                pass
        if bed_min_temp:
            try:
                payload["settings_bed_temp"] = int(float(bed_min_temp))
            except ValueError:
                pass
        if weight_gross_g:
            try:
                payload["weight"] = float(weight_gross_g)
            except ValueError:
                pass
        if spool_weight_g:
            try:
                payload["spool_weight"] = float(spool_weight_g)
            except ValueError:
                pass
        if max_temp:
            payload["extra"]["max_temp"] = max_temp
        if bed_max_temp:
            payload["extra"]["bed_max_temp"] = bed_max_temp
        if not payload["extra"]:
            payload.pop("extra")

        data = await self._first_post_ok(
            ["/api/v1/filament", "/api/v1/filaments"],
            [payload],
        )
        if isinstance(data, dict):
            return data
        raise RuntimeError("Unexpected filament create response format from Spoolman.")

    async def create_spool_from_prusament_import(
        self,
        imported: dict[str, Any],
    ) -> dict[str, Any]:
        filament = await self.create_filament_from_prusament_import(imported)
        filament_id = filament.get("id")
        if filament_id is None:
            raise RuntimeError("Filament response from Spoolman does not contain an id.")

        weight_gross = self._to_float(imported.get("weight_gross_g"))
        payload: dict[str, Any] = {
            "filament_id": filament_id,
            "archived": False,
            "used_weight": 0,
        }
        if imported.get("source_url"):
            payload["comment"] = str(imported.get("source_url"))

        data = await self._first_post_ok(
            ["/api/v1/spool", "/api/v1/spools"],
            [payload],
        )
        if isinstance(data, dict):
            return {
                "filament": filament,
                "spool": data,
            }
        raise RuntimeError("Unexpected spool create response format from Spoolman.")
