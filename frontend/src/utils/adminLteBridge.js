const APP_LOADED_CLASS = "app-loaded";
const HOLD_TRANSITION_CLASS = "hold-transition";
const SIDEBAR_COLLAPSE_CLASS = "sidebar-collapse";
const SIDEBAR_OPEN_CLASS = "sidebar-open";
const MAXIMIZED_CARD_CLASS = "maximized-card";
const WAS_COLLAPSED_CLASS = "was-collapsed";
const SIDEBAR_STORAGE_KEY = "lte.sidebar.state";

const DEFAULT_SIDEBAR_BREAKPOINT = 992;
const APP_LOADED_DELAY_MS = 400;
const HOLD_TRANSITION_DELAY_MS = 200;
const CARD_MAXIMIZE_DELAY_MS = 150;
const CARD_MINIMIZE_DELAY_MS = 10;
const CLEANUP_KEY = "__spoolTagWriterAdminLteCleanup";

const canUseDom = () => typeof window !== "undefined" && typeof document !== "undefined";

const getSidebarElement = () => document.querySelector(".app-sidebar");

const getSidebarConfig = () => {
  const sidebar = getSidebarElement();
  const breakpoint = Number(sidebar?.dataset.sidebarBreakpoint || DEFAULT_SIDEBAR_BREAKPOINT);

  return {
    sidebar,
    breakpoint: Number.isFinite(breakpoint) ? breakpoint : DEFAULT_SIDEBAR_BREAKPOINT,
    enablePersistence: sidebar?.dataset.enablePersistence === "true",
  };
};

const isMobileSidebar = (breakpoint) => window.innerWidth <= breakpoint;

const saveSidebarState = (state) => {
  try {
    window.localStorage?.setItem(SIDEBAR_STORAGE_KEY, state);
  } catch {
    // Ignore storage failures.
  }
};

const loadSidebarState = () => {
  try {
    return window.localStorage?.getItem(SIDEBAR_STORAGE_KEY) || "";
  } catch {
    return "";
  }
};

const collapseSidebar = () => {
  document.body.classList.remove(SIDEBAR_OPEN_CLASS);
  document.body.classList.add(SIDEBAR_COLLAPSE_CLASS);
};

const expandSidebar = (breakpoint) => {
  document.body.classList.remove(SIDEBAR_COLLAPSE_CLASS);

  if (isMobileSidebar(breakpoint)) {
    document.body.classList.add(SIDEBAR_OPEN_CLASS);
    return;
  }

  document.body.classList.remove(SIDEBAR_OPEN_CLASS);
};

const updateSidebarStateByResponsiveLogic = (breakpoint) => {
  if (isMobileSidebar(breakpoint)) {
    if (!document.body.classList.contains(SIDEBAR_OPEN_CLASS)) {
      collapseSidebar();
    }

    return;
  }

  document.body.classList.remove(SIDEBAR_OPEN_CLASS);

  if (!document.body.classList.contains(SIDEBAR_COLLAPSE_CLASS)) {
    expandSidebar(breakpoint);
  }
};

const initializeSidebar = () => {
  const { sidebar, breakpoint, enablePersistence } = getSidebarConfig();

  if (!sidebar) {
    return;
  }

  if (enablePersistence && !isMobileSidebar(breakpoint)) {
    const storedState = loadSidebarState();

    if (storedState === SIDEBAR_COLLAPSE_CLASS) {
      collapseSidebar();
      return;
    }

    if (storedState === SIDEBAR_OPEN_CLASS) {
      expandSidebar(breakpoint);
      return;
    }
  }

  updateSidebarStateByResponsiveLogic(breakpoint);
};

const toggleSidebar = () => {
  const { sidebar, breakpoint, enablePersistence } = getSidebarConfig();

  if (!sidebar) {
    return;
  }

  const nextState = document.body.classList.contains(SIDEBAR_COLLAPSE_CLASS)
    ? SIDEBAR_OPEN_CLASS
    : SIDEBAR_COLLAPSE_CLASS;

  if (nextState === SIDEBAR_OPEN_CLASS) {
    expandSidebar(breakpoint);
  } else {
    collapseSidebar();
  }

  if (enablePersistence) {
    saveSidebarState(nextState);
  }
};

const ensureSidebarOverlay = () => {
  const wrapper = document.querySelector(".app-wrapper");

  if (!wrapper || wrapper.querySelector(".sidebar-overlay")) {
    return;
  }

  const overlay = document.createElement("div");
  overlay.className = "sidebar-overlay";
  overlay.addEventListener("click", (event) => {
    event.preventDefault();
    collapseSidebar();
  });

  wrapper.append(overlay);
};

const toggleCardCollapse = (button) => {
  const card = button.closest(".card");

  if (!card) {
    return;
  }

  card.classList.toggle("collapsed-card");
};

const toggleCardMaximize = (button) => {
  const card = button.closest(".card");

  if (!card) {
    return;
  }

  const html = document.documentElement;

  if (card.classList.contains(MAXIMIZED_CARD_CLASS)) {
    card.style.height = "auto";
    card.style.width = "auto";
    card.style.transition = "all .15s";

    window.setTimeout(() => {
      html.classList.remove(MAXIMIZED_CARD_CLASS);
      card.classList.remove(MAXIMIZED_CARD_CLASS, WAS_COLLAPSED_CLASS);
    }, CARD_MINIMIZE_DELAY_MS);

    return;
  }

  card.style.height = `${card.offsetHeight}px`;
  card.style.width = `${card.offsetWidth}px`;
  card.style.transition = "all .15s";

  window.setTimeout(() => {
    html.classList.add(MAXIMIZED_CARD_CLASS);
    card.classList.add(MAXIMIZED_CARD_CLASS);

    if (card.classList.contains("collapsed-card")) {
      card.classList.add(WAS_COLLAPSED_CLASS);
    }
  }, CARD_MAXIMIZE_DELAY_MS);
};

const syncFullscreenButton = (button) => {
  const maximizeIcon = button.querySelector('[data-lte-icon="maximize"]');
  const minimizeIcon = button.querySelector('[data-lte-icon="minimize"]');
  const isFullscreen = !!document.fullscreenElement;

  if (maximizeIcon) {
    maximizeIcon.style.display = isFullscreen ? "none" : "block";
  }

  if (minimizeIcon) {
    minimizeIcon.style.display = isFullscreen ? "block" : "none";
  }
};

const syncFullscreenButtons = () => {
  document
    .querySelectorAll('[data-lte-toggle="fullscreen"]')
    .forEach((button) => syncFullscreenButton(button));
};

const toggleFullscreen = async (button) => {
  if (!document.fullscreenEnabled) {
    return;
  }

  if (document.fullscreenElement) {
    await document.exitFullscreen();
  } else {
    await document.documentElement.requestFullscreen();
  }

  syncFullscreenButton(button);
};

const setupResizeTransitions = () => {
  let transitionTimer = 0;

  const handleResize = () => {
    window.clearTimeout(transitionTimer);
    document.body.classList.add(HOLD_TRANSITION_CLASS);

    const { breakpoint } = getSidebarConfig();
    updateSidebarStateByResponsiveLogic(breakpoint);

    transitionTimer = window.setTimeout(() => {
      document.body.classList.remove(HOLD_TRANSITION_CLASS);
    }, HOLD_TRANSITION_DELAY_MS);
  };

  window.addEventListener("resize", handleResize);

  return () => {
    window.clearTimeout(transitionTimer);
    window.removeEventListener("resize", handleResize);
  };
};

const setupDocumentActions = () => {
  const handleClick = (event) => {
    const sidebarToggle = event.target.closest('[data-lte-toggle="sidebar"]');

    if (sidebarToggle) {
      event.preventDefault();
      toggleSidebar();
      return;
    }

    const fullscreenToggle = event.target.closest('[data-lte-toggle="fullscreen"]');

    if (fullscreenToggle) {
      event.preventDefault();
      void toggleFullscreen(fullscreenToggle);
      return;
    }

    const collapseToggle = event.target.closest('[data-lte-toggle="card-collapse"]');

    if (collapseToggle) {
      event.preventDefault();
      toggleCardCollapse(collapseToggle);
      return;
    }

    const maximizeToggle = event.target.closest('[data-lte-toggle="card-maximize"]');

    if (maximizeToggle) {
      event.preventDefault();
      toggleCardMaximize(maximizeToggle);
    }
  };

  document.addEventListener("click", handleClick);

  return () => {
    document.removeEventListener("click", handleClick);
  };
};

export const setupAdminLteBridge = () => {
  if (!canUseDom()) {
    return () => {};
  }

  if (typeof window[CLEANUP_KEY] === "function") {
    window[CLEANUP_KEY]();
  }

  ensureSidebarOverlay();
  initializeSidebar();
  syncFullscreenButtons();

  const cleanupResize = setupResizeTransitions();
  const cleanupActions = setupDocumentActions();
  const handleFullscreenChange = () => syncFullscreenButtons();

  document.body.classList.remove(HOLD_TRANSITION_CLASS);
  document.body.classList.remove(APP_LOADED_CLASS);
  document.addEventListener("fullscreenchange", handleFullscreenChange);

  const appLoadedTimer = window.setTimeout(() => {
    document.body.classList.add(APP_LOADED_CLASS);
  }, APP_LOADED_DELAY_MS);

  const cleanup = () => {
    window.clearTimeout(appLoadedTimer);
    cleanupResize();
    cleanupActions();
    document.removeEventListener("fullscreenchange", handleFullscreenChange);
  };

  window[CLEANUP_KEY] = cleanup;

  return cleanup;
};
