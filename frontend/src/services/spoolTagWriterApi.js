const OVERRIDE_KEYS = [
  "type",
  "color_hex",
  "brand",
  "min_temp",
  "max_temp",
  "bed_min_temp",
  "bed_max_temp",
  "subtype",
];

const toQueryString = (params = {}) => {
  const search = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined) {
      continue;
    }

    const normalized = String(value).trim();
    if (!normalized) {
      continue;
    }

    search.set(key, normalized);
  }

  return search.toString();
};

const extractErrorMessage = (payload, status) => {
  if (payload && typeof payload === "object") {
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail.trim();
    }

    return `Request failed (${status}).`;
  }

  if (typeof payload === "string" && payload.trim()) {
    return payload.trim();
  }

  return `Request failed (${status}).`;
};

export class SpoolTagWriterApi {
  async request(path, { method = "GET", params, body } = {}) {
    const query = params ? toQueryString(params) : "";
    const url = query ? `${path}?${query}` : path;
    const headers = {
      Accept: "application/json",
    };

    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    if (!response.ok) {
      throw new Error(extractErrorMessage(payload, response.status));
    }

    return payload;
  }

  getUiContext() {
    return this.request("/api/ui-context");
  }

  listSpools() {
    return this.request("/api/spools");
  }

  getExtruderMapping() {
    return this.request("/api/extruder-mapping");
  }

  updateExtruderMapping(mapping) {
    return this.request("/api/extruder-mapping", {
      method: "PUT",
      body: mapping,
    });
  }

  getMoonrakerSpoolSyncStatus() {
    return this.request("/api/moonraker/spool-sync-status");
  }

  getPrinterRfidChannel(channel, { refresh = true } = {}) {
    return this.request(`/api/printer/rfid/channels/${encodeURIComponent(channel)}`, {
      params: { refresh },
    });
  }

  assignSpoolLotNrFromPrinterRfid(spoolId, channel, { refresh = true } = {}) {
    return this.request(`/api/spools/${encodeURIComponent(spoolId)}/lot-nr/from-printer-rfid`, {
      method: "POST",
      params: {
        channel,
        refresh,
      },
    });
  }

  getOverrideDefaults(spoolId) {
    return this.request(`/api/spools/${encodeURIComponent(spoolId)}/overrides-defaults`);
  }

  previewSpool(spoolId, overrides = {}) {
    const hasOverrides = OVERRIDE_KEYS.some((key) => !!overrides[key]);
    const path = hasOverrides ? "/api/preview/with-overrides" : "/api/preview";

    return this.request(path, {
      method: "POST",
      params: {
        spool_id: spoolId,
        ...overrides,
      },
    });
  }

  writeSpool(spoolId, overrides = {}) {
    const hasOverrides = OVERRIDE_KEYS.some((key) => !!overrides[key]);
    const path = hasOverrides ? "/api/write/with-overrides" : "/api/write";

    return this.request(path, {
      method: "POST",
      params: {
        spool_id: spoolId,
        ...overrides,
      },
    });
  }

  readTag() {
    return this.request("/api/tag/read");
  }

  importPrusament(url) {
    return this.request("/api/import/prusament", {
      method: "POST",
      params: { url },
    });
  }

  createFilamentFromPrusament(url) {
    return this.request("/api/spoolman/filaments/create-from-prusament", {
      method: "POST",
      params: { url },
    });
  }

  createSpoolFromPrusament(url) {
    return this.request("/api/spoolman/spools/create-from-prusament", {
      method: "POST",
      params: { url },
    });
  }
}
