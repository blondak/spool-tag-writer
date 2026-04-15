const STORAGE_KEY = "spool-tag-writer.theme";
const THEMES = new Set(["light", "dark", "auto"]);

const canUseDom = () => typeof window !== "undefined" && typeof document !== "undefined";

const normalizeTheme = (theme) => (THEMES.has(theme) ? theme : "auto");

export const getStoredTheme = () => {
  if (!canUseDom()) {
    return "auto";
  }

  return normalizeTheme(window.localStorage.getItem(STORAGE_KEY));
};

export const getSystemTheme = () => {
  if (!canUseDom() || !window.matchMedia) {
    return "light";
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

export const resolveTheme = (theme) => {
  const normalized = normalizeTheme(theme);
  return normalized === "auto" ? getSystemTheme() : normalized;
};

export const applyTheme = (theme) => {
  if (!canUseDom()) {
    return "light";
  }

  const resolvedTheme = resolveTheme(theme);
  document.documentElement.setAttribute("data-bs-theme", resolvedTheme);
  document.body.setAttribute("data-bs-theme", resolvedTheme);
  return resolvedTheme;
};

export const saveTheme = (theme) => {
  if (!canUseDom()) {
    return;
  }

  window.localStorage.setItem(STORAGE_KEY, normalizeTheme(theme));
};

export const applyStoredTheme = () => applyTheme(getStoredTheme());

export const watchSystemTheme = (callback) => {
  if (!canUseDom() || !window.matchMedia) {
    return () => {};
  }

  const query = window.matchMedia("(prefers-color-scheme: dark)");
  const handler = () => callback(query.matches ? "dark" : "light");

  if (query.addEventListener) {
    query.addEventListener("change", handler);
    return () => query.removeEventListener("change", handler);
  }

  query.addListener(handler);
  return () => query.removeListener(handler);
};
