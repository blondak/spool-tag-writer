<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import AppHeader from "./components/AppHeader.vue";
import InfoBoxStat from "./components/InfoBoxStat.vue";
import AppSidebar from "./components/AppSidebar.vue";
import ExtruderMappingCard from "./components/ExtruderMappingCard.vue";
import PreviewCard from "./components/PreviewCard.vue";
import PrusamentImportCard from "./components/PrusamentImportCard.vue";
import ResultsCard from "./components/ResultsCard.vue";
import SpoolWriterCard from "./components/SpoolWriterCard.vue";
import U1RfidPairingCard from "./components/U1RfidPairingCard.vue";
import WebNfcCard from "./components/WebNfcCard.vue";
import { SpoolTagWriterApi } from "./services/spoolTagWriterApi.js";
import { readTagViaWebNfc, writeTagViaWebNfc } from "./services/webNfc.js";
import { buildOverridePayload, createEmptyOverrides, formatSpoolLabel, getBrowserContext, stringifyOverrides } from "./utils/spoolUi.js";
import { applyTheme, getStoredTheme, resolveTheme, saveTheme, watchSystemTheme } from "./utils/theme.js";

const api = new SpoolTagWriterApi();
const ACTIVE_SCREEN_STORAGE_KEY = "spool-tag-writer.active-screen";
const EXTRUDER_MAPPING_STORAGE_KEY = "spool-tag-writer.extruder-mapping";
const DEFAULT_EXTRUDER_COUNT = 4;
const DEFAULT_PRINTER_RFID_CHANNEL = 0;
const SCREEN_LABELS = {
  extruders: "Extruder Mapping",
  "tag-tools": "Tag Tools",
};

const readStoredScreen = () => {
  if (typeof window === "undefined") {
    return "extruders";
  }

  return window.localStorage.getItem(ACTIVE_SCREEN_STORAGE_KEY) || "extruders";
};

const clampExtruderCount = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return DEFAULT_EXTRUDER_COUNT;
  }

  return Math.min(12, Math.max(1, Math.round(numeric)));
};

const toolNameForIndex = (index) => (index <= 0 ? "extruder" : `extruder${index}`);

const normalizeExtruderMapping = (value) => {
  const parsed = value && typeof value === "object" ? value : {};
  const count = clampExtruderCount(parsed.count ?? DEFAULT_EXTRUDER_COUNT);
  const assignments = {};
  const assignmentsSource = parsed.assignments && typeof parsed.assignments === "object" ? parsed.assignments : null;
  const slotsSource = Array.isArray(parsed.slots) ? parsed.slots : [];

  for (let index = 0; index < count; index += 1) {
    const toolName = toolNameForIndex(index);
    let rawValue = assignmentsSource ? assignmentsSource[toolName] : undefined;

    if ((rawValue === undefined || rawValue === null || rawValue === "") && slotsSource.length > 0) {
      const slot = slotsSource.find((item) => {
        if (!item || typeof item !== "object") {
          return false;
        }

        if (item.tool_name === toolName || item.toolName === toolName) {
          return true;
        }

        return Number(item.index) === index;
      });
      rawValue = slot?.spool_id ?? slot?.spoolId;
    }

    const normalizedValue = String(rawValue ?? "").trim();
    if (normalizedValue) {
      assignments[toolName] = normalizedValue;
    }
  }

  return {
    count,
    assignments,
  };
};

const hasExtruderMappingEntries = (mapping) =>
  mapping.count !== DEFAULT_EXTRUDER_COUNT || Object.keys(mapping.assignments).length > 0;

const readStoredExtruderMapping = () => {
  if (typeof window === "undefined") {
    return normalizeExtruderMapping({});
  }

  try {
    return normalizeExtruderMapping(JSON.parse(window.localStorage.getItem(EXTRUDER_MAPPING_STORAGE_KEY) || "{}"));
  } catch {
    return normalizeExtruderMapping({});
  }
};

const browserContext = getBrowserContext();
const theme = ref(getStoredTheme());
const resolvedTheme = ref(resolveTheme(theme.value));
const activeScreen = ref(readStoredScreen());
const storedExtruderMapping = readStoredExtruderMapping();

const uiContext = ref({
  nfc_backend: "",
  nfc_reader_name: "",
});
const spools = ref([]);
const selectedSpoolId = ref("");
const overrides = ref(createEmptyOverrides());
const preview = ref(null);
const result = ref(null);
const appAlert = ref(null);
const extruderCount = ref(storedExtruderMapping.count);
const extruderAssignments = ref({ ...storedExtruderMapping.assignments });
let extruderMappingSaveChain = Promise.resolve();

const loading = reactive({
  initializing: false,
  extruderU1Read: false,
  defaults: false,
  preview: false,
  write: false,
  read: false,
  prusamentLoad: false,
  prusamentCreateFilament: false,
  prusamentCreateSpool: false,
  webNfcRead: false,
  webNfcWrite: false,
  printerRfidRead: false,
  printerRfidAssign: false,
});

const prusament = reactive({
  status: "",
  statusTone: "secondary",
  matchMessage: "",
  matchTone: "secondary",
  result: null,
});

const webNfc = reactive({
  status: "",
  statusTone: "secondary",
  result: null,
});

const printerRfid = reactive({
  channel: DEFAULT_PRINTER_RFID_CHANNEL,
  status: "",
  statusTone: "secondary",
  result: null,
  selectedSpoolId: "",
});

const selectedSpool = computed(() =>
  spools.value.find((spool) => String(spool.id) === String(selectedSpoolId.value)) || null,
);
const selectedSpoolLabel = computed(() => formatSpoolLabel(selectedSpool.value));
const printerRfidSelectedSpool = computed(() =>
  spools.value.find((spool) => String(spool.id) === String(printerRfid.selectedSpoolId)) || null,
);
const printerRfidSelectedSpoolLabel = computed(() => formatSpoolLabel(printerRfidSelectedSpool.value));
const activeScreenLabel = computed(() => SCREEN_LABELS[activeScreen.value] || SCREEN_LABELS.extruders);
const extruderSlots = computed(() =>
  Array.from({ length: extruderCount.value }, (_, index) => {
    const toolName = index === 0 ? "extruder" : `extruder${index}`;
    const spoolId = String(extruderAssignments.value[toolName] || "");
    const mappedSpool = spools.value.find((spool) => String(spool.id) === spoolId) || null;

    return {
      index,
      label: `T${index}`,
      toolName,
      spoolId,
      spoolLabel: mappedSpool ? formatSpoolLabel(mappedSpool) : spoolId ? `#${spoolId} - unavailable` : "",
    };
  }),
);
const mappedExtruders = computed(() => extruderSlots.value.filter((slot) => slot.spoolId).length);
const writerBusy = computed(
  () => loading.initializing || loading.defaults || loading.preview || loading.write || loading.read,
);
const activeTransport = computed(() => {
  if (browserContext.webNfcAvailable && browserContext.secureContextOk) {
    return "Reader + Web NFC";
  }

  return "Reader only";
});
const previewSize = computed(() => (preview.value?.payload_size ? `${preview.value.payload_size} B` : "Not prepared"));
const appAlertToneClass = computed(() => {
  const tone = appAlert.value?.tone || "danger";
  const normalized = tone === "secondary" ? "info" : tone;
  return `callout-${normalized}`;
});
const appAlertHeading = computed(() => {
  const tone = appAlert.value?.tone || "danger";
  switch (tone) {
    case "success":
      return "Action completed";
    case "warning":
      return "Attention needed";
    case "info":
    case "secondary":
      return "Status update";
    default:
      return "Action failed";
  }
});
const appAlertIcon = computed(() => {
  const tone = appAlert.value?.tone || "danger";
  switch (tone) {
    case "success":
      return "bi bi-check-circle-fill";
    case "warning":
      return "bi bi-exclamation-circle-fill";
    case "info":
    case "secondary":
      return "bi bi-info-circle-fill";
    default:
      return "bi bi-exclamation-triangle-fill";
  }
});
const uiState = computed(() => (loading.initializing ? "Loading" : "Ready"));

const clearAppAlert = () => {
  appAlert.value = null;
};

const setAppAlert = (message, tone = "danger") => {
  appAlert.value = message ? { message, tone } : null;
};

const setPrusamentStatus = (message, tone = "secondary") => {
  prusament.status = message;
  prusament.statusTone = tone;
};

const setPrusamentMatch = (message, tone = "secondary") => {
  prusament.matchMessage = message;
  prusament.matchTone = tone;
};

const setWebNfcStatus = (message, tone = "secondary") => {
  webNfc.status = message;
  webNfc.statusTone = tone;
};

const setPrinterRfidStatus = (message, tone = "secondary") => {
  printerRfid.status = message;
  printerRfid.statusTone = tone;
};

const syncTheme = (nextTheme) => {
  theme.value = nextTheme;
  saveTheme(nextTheme);
  resolvedTheme.value = applyTheme(nextTheme);
};

const persistActiveScreen = () => {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(ACTIVE_SCREEN_STORAGE_KEY, activeScreen.value);
};

const persistExtruderMappingLocal = () => {
  if (typeof window === "undefined") {
    return;
  }

  const mapping = normalizeExtruderMapping({
    count: extruderCount.value,
    assignments: extruderAssignments.value,
  });

  window.localStorage.setItem(
    EXTRUDER_MAPPING_STORAGE_KEY,
    JSON.stringify(mapping),
  );
};

const replaceSpoolInList = (nextSpool) => {
  if (!nextSpool || typeof nextSpool !== "object" || nextSpool.id === undefined || nextSpool.id === null) {
    return;
  }

  const nextId = String(nextSpool.id);
  const nextList = [...spools.value];
  const existingIndex = nextList.findIndex((spool) => String(spool.id) === nextId);

  if (existingIndex >= 0) {
    nextList.splice(existingIndex, 1, nextSpool);
  } else {
    nextList.push(nextSpool);
  }

  nextList.sort((left, right) => Number(left.id || 0) - Number(right.id || 0));
  spools.value = nextList;
};

const applyExtruderMapping = (mapping, { persistLocal = true } = {}) => {
  const normalized = normalizeExtruderMapping(mapping);
  extruderCount.value = normalized.count;
  extruderAssignments.value = { ...normalized.assignments };

  if (persistLocal) {
    persistExtruderMappingLocal();
  }

  return normalized;
};

const queueExtruderMappingSave = (mapping) => {
  const snapshot = normalizeExtruderMapping(mapping);
  extruderMappingSaveChain = extruderMappingSaveChain
    .catch(() => undefined)
    .then(() => api.updateExtruderMapping(snapshot))
    .catch((error) => {
      setAppAlert(
        error.message || "Failed to save the extruder mapping to Moonraker. Browser fallback is still available.",
        "warning",
      );
    });
  return extruderMappingSaveChain;
};

const switchScreen = (screen) => {
  activeScreen.value = Object.hasOwn(SCREEN_LABELS, screen) ? screen : "extruders";
  persistActiveScreen();
};

const updateExtruderCount = (nextCount) => {
  const normalized = applyExtruderMapping({
    count: nextCount,
    assignments: extruderAssignments.value,
  });
  void queueExtruderMappingSave(normalized);
};

const updateExtruderSlot = ({ toolName, spoolId }) => {
  const nextAssignments = { ...extruderAssignments.value };

  if (spoolId) {
    nextAssignments[toolName] = String(spoolId);
  } else {
    delete nextAssignments[toolName];
  }

  const normalized = applyExtruderMapping({
    count: extruderCount.value,
    assignments: nextAssignments,
  });
  void queueExtruderMappingSave(normalized);
};

const applyPrinterRfidReadResult = (channel, response) => {
  printerRfid.channel = Number(channel);
  printerRfid.result = response;
  const matchedSpools = Array.isArray(response.matched_spools) ? response.matched_spools : [];

  if (matchedSpools.length === 1 && matchedSpools[0]?.id !== undefined && matchedSpools[0]?.id !== null) {
    printerRfid.selectedSpoolId = String(matchedSpools[0].id);
  } else {
    printerRfid.selectedSpoolId = "";
  }

  if (response.card_uid) {
    if (matchedSpools.length === 1) {
      setPrinterRfidStatus(
        `Loaded UID ${response.card_uid} from ${response.label || `T${channel}`} and matched one Spoolman spool.`,
        "success",
      );
    } else if (matchedSpools.length > 1) {
      setPrinterRfidStatus(
        `Loaded UID ${response.card_uid}, but multiple Spoolman spools match it. Select one manually.`,
        "warning",
      );
    } else {
      setPrinterRfidStatus(
        `Loaded UID ${response.card_uid} from ${response.label || `T${channel}`}. Select a spool for writing.`,
        "warning",
      );
    }
  } else {
    setPrinterRfidStatus(`No RFID UID was detected on ${response.label || `T${channel}`}.`, "warning");
  }

  return matchedSpools;
};

const loadExtruderSlotFromU1 = async (slot) => {
  if (!slot || typeof slot !== "object") {
    return;
  }

  loading.extruderU1Read = true;
  clearAppAlert();

  try {
    const response = await api.getPrinterRfidChannel(slot.index, { refresh: true });
    const matchedSpools = applyPrinterRfidReadResult(slot.index, response);

    if (!response.card_uid) {
      setAppAlert(`No RFID UID was detected on ${slot.label}.`, "warning");
      return;
    }

    if (matchedSpools.length === 1 && matchedSpools[0]?.id !== undefined && matchedSpools[0]?.id !== null) {
      updateExtruderSlot({
        toolName: slot.toolName,
        spoolId: matchedSpools[0].id,
      });
      setAppAlert(`Assigned ${slot.label} from U1 RFID to spool #${matchedSpools[0].id}.`, "success");
      return;
    }

    if (matchedSpools.length > 1) {
      setAppAlert(
        `${slot.label} RFID matched multiple spools. Use U1 RFID Pairing to choose one manually.`,
        "warning",
      );
      return;
    }

    setAppAlert(
      `${slot.label} RFID UID was not found in Spoolman lot_nr. Use U1 RFID Pairing to choose a spool manually.`,
      "warning",
    );
  } catch (error) {
    setAppAlert(error.message || `Failed to read U1 RFID for ${slot.label}.`);
  } finally {
    loading.extruderU1Read = false;
  }
};

const handlePrinterRfidChannelUpdate = (nextChannel) => {
  printerRfid.channel = Number(nextChannel);
  printerRfid.result = null;
  printerRfid.selectedSpoolId = "";
  setPrinterRfidStatus("", "secondary");
};

const handlePrinterRfidSelectedSpoolUpdate = (nextSpoolId) => {
  printerRfid.selectedSpoolId = String(nextSpoolId || "");
};

const applyImportedOverrides = (data) => {
  overrides.value = stringifyOverrides(data);
};

const syncPrusamentMatch = (data) => {
  const match = data?.spoolman_filament_match;

  if (match?.matched && match.filament) {
    setPrusamentMatch(
      `A matching Spoolman filament already exists: #${match.filament.id}.`,
      "success",
    );
    return;
  }

  if (data?.external_id) {
    setPrusamentMatch(
      `No Spoolman filament was found for external_id ${data.external_id} and vendor ${data.brand || "-"}.`,
      "warning",
    );
    return;
  }

  setPrusamentMatch("The import does not contain an external_id for Spoolman matching.", "secondary");
};

const loadDefaultsForSpool = async (spoolId) => {
  if (!spoolId) {
    overrides.value = createEmptyOverrides();
    return;
  }

  loading.defaults = true;

  try {
    const defaults = await api.getOverrideDefaults(spoolId);
    overrides.value = stringifyOverrides(defaults);
  } catch (error) {
    overrides.value = createEmptyOverrides();
    setAppAlert(error.message || "Failed to load override defaults.");
  } finally {
    loading.defaults = false;
  }
};

const refreshSpools = async ({ preferredSpoolId } = {}) => {
  const list = await api.listSpools();
  spools.value = list;

  if (!list.length) {
    selectedSpoolId.value = "";
    overrides.value = createEmptyOverrides();
    return;
  }

  const preferred = preferredSpoolId
    ? list.find((spool) => String(spool.id) === String(preferredSpoolId))
    : null;
  const nextSpool = preferred || list.find((spool) => String(spool.id) === String(selectedSpoolId.value)) || list[0];

  selectedSpoolId.value = String(nextSpool.id);
  await loadDefaultsForSpool(nextSpool.id);
};

const initialize = async () => {
  loading.initializing = true;
  clearAppAlert();

  try {
    const [nextUiContext, spoolList, remoteExtruderMapping] = await Promise.all([
      api.getUiContext(),
      api.listSpools(),
      api.getExtruderMapping().catch(() => null),
    ]);
    uiContext.value = nextUiContext;
    spools.value = spoolList;

    const remoteMapping = remoteExtruderMapping ? normalizeExtruderMapping(remoteExtruderMapping) : null;
    if (remoteMapping && (!hasExtruderMappingEntries(remoteMapping) && hasExtruderMappingEntries(storedExtruderMapping))) {
      applyExtruderMapping(storedExtruderMapping);
      void queueExtruderMappingSave(storedExtruderMapping);
    } else if (remoteMapping) {
      applyExtruderMapping(remoteMapping);
    } else {
      applyExtruderMapping(storedExtruderMapping);
    }

    if (spoolList.length > 0) {
      selectedSpoolId.value = String(spoolList[0].id);
      await loadDefaultsForSpool(spoolList[0].id);
    }
  } catch (error) {
    setAppAlert(error.message || "Failed to initialize the dashboard.");
  } finally {
    loading.initializing = false;
  }
};

const handleSpoolSelection = async (nextSpoolId) => {
  clearAppAlert();
  preview.value = null;
  result.value = null;
  selectedSpoolId.value = String(nextSpoolId || "");
  await loadDefaultsForSpool(selectedSpoolId.value);
};

const openTagToolsForSpool = async (spoolId) => {
  if (!spoolId) {
    switchScreen("tag-tools");
    return;
  }

  if (String(spoolId) !== String(selectedSpoolId.value)) {
    await handleSpoolSelection(String(spoolId));
  }

  switchScreen("tag-tools");
};

const handleOverridesUpdate = (nextOverrides) => {
  clearAppAlert();
  overrides.value = stringifyOverrides(nextOverrides);
};

const runPreview = async () => {
  if (!selectedSpoolId.value) {
    setAppAlert("Select a spool first.");
    return;
  }

  loading.preview = true;
  clearAppAlert();

  try {
    preview.value = await api.previewSpool(selectedSpoolId.value, buildOverridePayload(overrides.value));
    result.value = null;
  } catch (error) {
    setAppAlert(error.message || "Failed to prepare the preview.");
  } finally {
    loading.preview = false;
  }
};

const runWrite = async () => {
  if (!selectedSpoolId.value) {
    setAppAlert("Select a spool first.");
    return;
  }

  loading.write = true;
  clearAppAlert();

  try {
    const response = await api.writeSpool(selectedSpoolId.value, buildOverridePayload(overrides.value));
    preview.value = response.preview;
    result.value = {
      write: response.write_result,
      read: response.readback,
    };
  } catch (error) {
    setAppAlert(error.message || "Writing the tag failed.");
  } finally {
    loading.write = false;
  }
};

const runReaderRead = async () => {
  loading.read = true;
  clearAppAlert();

  try {
    const readResult = await api.readTag();
    result.value = {
      ...(result.value || {}),
      read: readResult,
    };
  } catch (error) {
    setAppAlert(error.message || "Reading the tag failed.");
  } finally {
    loading.read = false;
  }
};

const readPrinterRfid = async () => {
  loading.printerRfidRead = true;
  clearAppAlert();
  setPrinterRfidStatus(`Refreshing RFID data from ${`T${printerRfid.channel}`}.`, "info");

  try {
    const response = await api.getPrinterRfidChannel(printerRfid.channel, { refresh: true });
    applyPrinterRfidReadResult(printerRfid.channel, response);
  } catch (error) {
    setPrinterRfidStatus(error.message || "Reading the printer RFID failed.", "danger");
  } finally {
    loading.printerRfidRead = false;
  }
};

const assignPrinterRfidLotNr = async () => {
  const targetSpoolId = String(printerRfid.selectedSpoolId || selectedSpoolId.value || "");
  if (!targetSpoolId) {
    setAppAlert("Select a spool for the RFID assignment first.");
    return;
  }

  loading.printerRfidAssign = true;
  clearAppAlert();
  setPrinterRfidStatus("Reading the selected U1 channel and updating Spoolman lot_nr.", "info");

  try {
    const response = await api.assignSpoolLotNrFromPrinterRfid(targetSpoolId, printerRfid.channel, {
      refresh: true,
    });
    printerRfid.result = response.rfid_channel || null;
    printerRfid.selectedSpoolId = response.spool?.id ? String(response.spool.id) : targetSpoolId;

    if (response.spool) {
      replaceSpoolInList(response.spool);
    }
    for (const clearedSpool of response.cleared_spools || []) {
      replaceSpoolInList(clearedSpool);
    }

    const clearedIds = (response.cleared_spools || [])
      .map((spool) => spool?.id)
      .filter((value) => value !== undefined && value !== null);
    const clearedMessage = clearedIds.length
      ? ` Removed from spool ${clearedIds.map((value) => `#${value}`).join(", ")} first.`
      : "";

    setPrinterRfidStatus(
      `Saved UID ${response.lot_nr || response.rfid_channel?.card_uid || ""} to lot_nr of spool #${targetSpoolId}.${clearedMessage}`,
      "success",
    );
  } catch (error) {
    setPrinterRfidStatus(error.message || "Saving the printer RFID to Spoolman failed.", "danger");
  } finally {
    loading.printerRfidAssign = false;
  }
};

const importPrusament = async (url) => {
  loading.prusamentLoad = true;
  setPrusamentStatus("Loading data from the Prusament URL.", "info");
  setPrusamentMatch("", "secondary");

  try {
    const imported = await api.importPrusament(url);
    prusament.result = imported;
    applyImportedOverrides(imported);
    syncPrusamentMatch(imported);
    preview.value = null;
    result.value = null;
    setPrusamentStatus("Prusament data was loaded and applied to the override fields.", "success");
  } catch (error) {
    setPrusamentStatus(error.message || "Prusament import failed.", "danger");
  } finally {
    loading.prusamentLoad = false;
  }
};

const createPrusamentFilament = async (url) => {
  loading.prusamentCreateFilament = true;
  setPrusamentStatus("Creating a filament in Spoolman.", "info");
  setPrusamentMatch("", "secondary");

  try {
    const created = await api.createFilamentFromPrusament(url);
    prusament.result = created;
    setPrusamentStatus(
      `The filament is ready in Spoolman under ID ${created.created_filament?.id ?? "?"}.`,
      "success",
    );
  } catch (error) {
    setPrusamentStatus(error.message || "Creating the filament in Spoolman failed.", "danger");
  } finally {
    loading.prusamentCreateFilament = false;
  }
};

const createPrusamentSpool = async (url) => {
  loading.prusamentCreateSpool = true;
  setPrusamentStatus("Creating the filament and spool in Spoolman.", "info");
  setPrusamentMatch("", "secondary");

  try {
    const created = await api.createSpoolFromPrusament(url);
    prusament.result = created;

    if (created.spool?.id) {
      await refreshSpools({ preferredSpoolId: created.spool.id });
      preview.value = await api.previewSpool(created.spool.id, {});
    }

    setPrusamentStatus(`The spool is ready in Spoolman under ID ${created.spool?.id ?? "?"}.`, "success");
  } catch (error) {
    setPrusamentStatus(error.message || "Creating the spool in Spoolman failed.", "danger");
  } finally {
    loading.prusamentCreateSpool = false;
  }
};

const runWebNfcRead = async () => {
  if (!browserContext.webNfcAvailable || !browserContext.secureContextOk) {
    setWebNfcStatus("Web NFC is not available in this browser context.", "warning");
    return;
  }

  loading.webNfcRead = true;
  setWebNfcStatus("Hold the tag near your phone.", "info");

  try {
    webNfc.result = await readTagViaWebNfc();
    setWebNfcStatus("The tag was read successfully with your phone.", "success");
  } catch (error) {
    setWebNfcStatus(error.message || "Reading with the phone failed.", "danger");
  } finally {
    loading.webNfcRead = false;
  }
};

const runWebNfcWrite = async () => {
  if (!browserContext.webNfcAvailable || !browserContext.secureContextOk) {
    setWebNfcStatus("Web NFC is not available in this browser context.", "warning");
    return;
  }

  if (!selectedSpoolId.value) {
    setAppAlert("Select a spool first.");
    return;
  }

  loading.webNfcWrite = true;
  setWebNfcStatus("Preparing the payload and waiting for the tag.", "info");

  try {
    const preparedPreview = await api.previewSpool(selectedSpoolId.value, buildOverridePayload(overrides.value));
    preview.value = preparedPreview;
    webNfc.result = await writeTagViaWebNfc(preparedPreview);
    setWebNfcStatus("The tag was written successfully with your phone.", "success");
  } catch (error) {
    setWebNfcStatus(error.message || "Writing with the phone failed.", "danger");
  } finally {
    loading.webNfcWrite = false;
  }
};

let stopSystemThemeWatcher = () => {};

onMounted(() => {
  resolvedTheme.value = applyTheme(theme.value);
  stopSystemThemeWatcher = watchSystemTheme(() => {
    if (theme.value === "auto") {
      resolvedTheme.value = applyTheme(theme.value);
    }
  });
  initialize();
});

onBeforeUnmount(() => {
  stopSystemThemeWatcher();
});
</script>

<template>
  <div class="app-wrapper">
    <AppHeader
      :ui-context="uiContext"
      :active-screen-label="activeScreenLabel"
      :active-spool-label="selectedSpoolLabel"
      :theme="theme"
      :resolved-theme="resolvedTheme"
      @change-theme="syncTheme"
    />

    <AppSidebar
      :active-screen="activeScreen"
      :ui-context="uiContext"
      :spools-count="spools.length"
      :selected-spool-label="selectedSpoolLabel"
      :web-nfc-available="browserContext.webNfcAvailable"
      :secure-context-ok="browserContext.secureContextOk"
      :extruder-count="extruderCount"
      :mapped-extruders="mappedExtruders"
      @navigate="switchScreen"
    />

    <main class="app-main">
      <div class="app-content-header">
        <div class="container-fluid">
          <div class="row">
            <div class="col-sm-6">
              <h3 class="mb-0">{{ activeScreenLabel }}</h3>
            </div>
            <div class="col-sm-6">
              <ol class="breadcrumb float-sm-end">
                <li class="breadcrumb-item">
                  <a href="#" @click.prevent="switchScreen('extruders')">Dashboard</a>
                </li>
                <li class="breadcrumb-item active" aria-current="page">{{ activeScreenLabel }}</li>
              </ol>
            </div>
          </div>
          <div v-if="appAlert" class="callout mt-3 mb-0" :class="appAlertToneClass">
            <h5 class="mb-2">
              <i :class="[appAlertIcon, 'me-2']"></i>
              {{ appAlertHeading }}
            </h5>
            <p class="mb-0">{{ appAlert.message }}</p>
          </div>
        </div>
      </div>

      <div class="app-content">
        <div class="container-fluid">
          <template v-if="activeScreen === 'extruders'">
            <div class="row g-4 mb-1">
              <div class="col-12 col-md-6 col-xl-3">
                <InfoBoxStat
                  icon="bi bi-diagram-3"
                  icon-class="text-bg-primary"
                  label="Configured Extruders"
                  :value="String(extruderCount)"
                  hint="Synced to Moonraker DB"
                />
              </div>
              <div class="col-12 col-md-6 col-xl-3">
                <InfoBoxStat
                  icon="bi bi-check2-circle"
                  icon-class="text-bg-success"
                  label="Assigned Slots"
                  :value="String(mappedExtruders)"
                  :hint="`${extruderCount - mappedExtruders} still empty`"
                />
              </div>
              <div class="col-12 col-md-6 col-xl-3">
                <InfoBoxStat
                  icon="bi bi-collection"
                  icon-class="text-bg-info"
                  label="Available Spools"
                  :value="String(spools.length)"
                  hint="Fetched from Spoolman"
                />
              </div>
              <div class="col-12 col-md-6 col-xl-3">
                <InfoBoxStat
                  icon="bi bi-lightning-charge"
                  icon-class="text-bg-warning"
                  label="UI State"
                  :value="uiState"
                  hint="Primary operator screen"
                />
              </div>
            </div>

            <div class="row g-3">
              <div class="col-12">
                <ExtruderMappingCard
                  :spools="spools"
                  :slots="extruderSlots"
                  :extruder-count="extruderCount"
                  :assigned-count="mappedExtruders"
                  :busy="loading.initializing"
                  :u1-read-busy="loading.extruderU1Read"
                  @update:extruder-count="updateExtruderCount"
                  @update:slot-spool="updateExtruderSlot"
                  @load-from-u1="loadExtruderSlotFromU1"
                  @open-tag-tools="openTagToolsForSpool"
                />
              </div>
            </div>
          </template>

          <template v-else>
            <div class="row g-4 mb-1">
              <div class="col-12 col-md-6 col-xl-3">
                <InfoBoxStat
                  icon="bi bi-collection"
                  icon-class="text-bg-primary"
                  label="Available Spools"
                  :value="String(spools.length)"
                  hint="Fetched from Spoolman"
                />
              </div>
              <div class="col-12 col-md-6 col-xl-3">
                <InfoBoxStat
                  icon="bi bi-disc"
                  icon-class="text-bg-success"
                  label="Selected Spool"
                  :value="selectedSpoolId || '—'"
                  :hint="selectedSpoolLabel || 'No spool selected'"
                />
              </div>
              <div class="col-12 col-md-6 col-xl-3">
                <InfoBoxStat
                  icon="bi bi-file-earmark-code"
                  icon-class="text-bg-info"
                  label="Prepared Payload"
                  :value="previewSize"
                  hint="OpenSpool JSON"
                />
              </div>
              <div class="col-12 col-md-6 col-xl-3">
                <InfoBoxStat
                  icon="bi bi-lightning-charge"
                  icon-class="text-bg-warning"
                  label="UI State"
                  :value="uiState"
                  :hint="activeTransport"
                />
              </div>
            </div>

            <div class="row g-3">
              <div class="col-12 col-xxl-5">
                <div class="row g-3">
                  <div class="col-12">
                    <U1RfidPairingCard
                      :spools="spools"
                      :selected-spool-id="selectedSpoolId"
                      :selected-spool-label="selectedSpoolLabel"
                      :printer-rfid-channel="printerRfid.channel"
                      :printer-rfid-status="printerRfid.status"
                      :printer-rfid-status-tone="printerRfid.statusTone"
                      :printer-rfid-result="printerRfid.result"
                      :printer-rfid-selected-spool-id="printerRfid.selectedSpoolId"
                      :printer-rfid-selected-spool-label="printerRfidSelectedSpoolLabel"
                      :printer-rfid-read-busy="loading.printerRfidRead"
                      :printer-rfid-assign-busy="loading.printerRfidAssign"
                      :busy="loading.initializing"
                      @update:printer-rfid-channel="handlePrinterRfidChannelUpdate"
                      @update:printer-rfid-selected-spool-id="handlePrinterRfidSelectedSpoolUpdate"
                      @read-printer-rfid="readPrinterRfid"
                      @assign-printer-rfid-lot-nr="assignPrinterRfidLotNr"
                    />
                  </div>

                  <div class="col-12">
                    <PrusamentImportCard
                      :status="prusament.status"
                      :status-tone="prusament.statusTone"
                      :match-message="prusament.matchMessage"
                      :match-tone="prusament.matchTone"
                      :result="prusament.result"
                      :busy-load="loading.prusamentLoad"
                      :busy-create-filament="loading.prusamentCreateFilament"
                      :busy-create-spool="loading.prusamentCreateSpool"
                      @load-url="importPrusament"
                      @create-filament="createPrusamentFilament"
                      @create-spool="createPrusamentSpool"
                    />
                  </div>
                </div>
              </div>

              <div class="col-12 col-xxl-7">
                <SpoolWriterCard
                  :spools="spools"
                  :selected-spool-id="selectedSpoolId"
                  :selected-spool-label="selectedSpoolLabel"
                  :overrides="overrides"
                  :busy="writerBusy"
                  :defaults-busy="loading.defaults"
                  :preview-busy="loading.preview"
                  :write-busy="loading.write"
                  :read-busy="loading.read"
                  @update:selected-spool-id="handleSpoolSelection"
                  @update:overrides="handleOverridesUpdate"
                  @preview="runPreview"
                  @write="runWrite"
                  @read="runReaderRead"
                />
              </div>

              <div class="col-12 col-xl-5">
                <WebNfcCard
                  :available="browserContext.webNfcAvailable"
                  :secure-context-ok="browserContext.secureContextOk"
                  :status="webNfc.status"
                  :status-tone="webNfc.statusTone"
                  :result="webNfc.result"
                  :busy-read="loading.webNfcRead"
                  :busy-write="loading.webNfcWrite"
                  @read="runWebNfcRead"
                  @write="runWebNfcWrite"
                />
              </div>

              <div class="col-12 col-xl-7">
                <PreviewCard :preview="preview" :busy="loading.preview || loading.webNfcWrite" />
              </div>

              <div class="col-12">
                <ResultsCard :result="result" />
              </div>
            </div>
          </template>
        </div>
      </div>
    </main>
  </div>
</template>
