const EMPTY_OVERRIDES = Object.freeze({
  type: "",
  color_hex: "",
  brand: "",
  min_temp: "",
  max_temp: "",
  bed_min_temp: "",
  bed_max_temp: "",
  subtype: "",
});

const LOCALHOST_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

export const createEmptyOverrides = () => ({ ...EMPTY_OVERRIDES });

export const stringifyOverrides = (source = {}) => ({
  type: source.type ? String(source.type) : "",
  color_hex: source.color_hex ? String(source.color_hex) : "",
  brand: source.brand ? String(source.brand) : "",
  min_temp: source.min_temp ? String(source.min_temp) : "",
  max_temp: source.max_temp ? String(source.max_temp) : "",
  bed_min_temp: source.bed_min_temp ? String(source.bed_min_temp) : "",
  bed_max_temp: source.bed_max_temp ? String(source.bed_max_temp) : "",
  subtype: source.subtype ? String(source.subtype) : "",
});

export const buildOverridePayload = (overrides) => {
  const payload = {};

  for (const [key, value] of Object.entries(overrides)) {
    const normalized = String(value ?? "").trim();
    if (!normalized) {
      continue;
    }

    payload[key] = key === "color_hex" ? normalized.replace(/^#/, "").toUpperCase() : normalized;
  }

  return payload;
};

export const formatSpoolLabel = (spool) => {
  if (!spool) {
    return "";
  }

  const filament = spool?.filament && typeof spool.filament === "object" ? spool.filament : {};
  const filamentName = filament.name || spool.name || "unknown";
  const vendorName =
    spool.manufacturer ||
    filament.vendor?.name ||
    filament.vendor ||
    filament.manufacturer_name ||
    filament.manufacturer ||
    filament.brand ||
    "";
  const material = filament.material || "-";
  const labelCore = vendorName ? `${vendorName} / ${filamentName}` : filamentName;
  return `#${spool.id} - ${labelCore} (${material})`;
};

export const getBrowserContext = () => {
  if (typeof window === "undefined") {
    return {
      webNfcAvailable: false,
      secureContextOk: false,
    };
  }

  return {
    webNfcAvailable: "NDEFReader" in window,
    secureContextOk: window.isSecureContext || LOCALHOST_HOSTS.has(window.location.hostname),
  };
};
