<script setup>
import CardHelpTooltip from "./CardHelpTooltip.vue";
import SpoolPicker from "./SpoolPicker.vue";

const props = defineProps({
  spools: {
    type: Array,
    default: () => [],
  },
  selectedSpoolId: {
    type: String,
    default: "",
  },
  selectedSpoolLabel: {
    type: String,
    default: "",
  },
  overrides: {
    type: Object,
    required: true,
  },
  busy: {
    type: Boolean,
    default: false,
  },
  defaultsBusy: {
    type: Boolean,
    default: false,
  },
  previewBusy: {
    type: Boolean,
    default: false,
  },
  writeBusy: {
    type: Boolean,
    default: false,
  },
  readBusy: {
    type: Boolean,
    default: false,
  },
  localNfcEnabled: {
    type: Boolean,
    default: true,
  },
});

const emit = defineEmits([
  "update:selectedSpoolId",
  "update:overrides",
  "preview",
  "write",
  "read",
]);

const fields = [
  { key: "type", label: "Type", placeholder: "PLA" },
  { key: "brand", label: "Brand", placeholder: "Spectrum" },
  { key: "subtype", label: "Subtype", placeholder: "Wood" },
  { key: "color_hex", label: "Color HEX", placeholder: "RRGGBB" },
  { key: "min_temp", label: "Min Temp", placeholder: "190" },
  { key: "max_temp", label: "Max Temp", placeholder: "220" },
  { key: "bed_min_temp", label: "Bed Min", placeholder: "50" },
  { key: "bed_max_temp", label: "Bed Max", placeholder: "60" },
];

const updateOverride = (key, value) => {
  emit("update:overrides", {
    ...props.overrides,
    [key]: value,
  });
};
</script>

<template>
  <div id="writer-panel" class="card card-outline card-primary h-100">
    <div class="card-header">
      <h3 class="card-title">
        <i class="bi bi-upc-scan me-2"></i>
        {{ localNfcEnabled ? "NFC Tag Writer" : "Payload Builder" }}
      </h3>
      <div class="card-tools">
        <span class="badge text-bg-light">
          {{ defaultsBusy ? "Syncing defaults" : "Spoolman defaults" }}
        </span>
        <CardHelpTooltip
          label="OpenSpool Overrides help"
          html="<strong>OpenSpool Overrides</strong><br>Filled fields override the generated payload. Empty fields fall back to Spoolman values."
        />
        <button type="button" class="btn btn-tool" data-lte-toggle="card-collapse" aria-label="Collapse card">
          <i data-lte-icon="expand" class="bi bi-plus-lg"></i>
          <i data-lte-icon="collapse" class="bi bi-dash-lg"></i>
        </button>
        <button type="button" class="btn btn-tool" data-lte-toggle="card-maximize" aria-label="Maximize card">
          <i data-lte-icon="maximize" class="bi bi-fullscreen"></i>
          <i data-lte-icon="minimize" class="bi bi-fullscreen-exit"></i>
        </button>
      </div>
    </div>

    <div class="card-body">
      <div class="info-box mb-4">
        <span class="info-box-icon text-bg-primary shadow-sm">
          <i class="bi bi-disc-fill"></i>
        </span>
        <div class="info-box-content">
          <span class="info-box-text">Selected Spool</span>
          <span class="info-box-number">{{ selectedSpoolLabel || "No spool selected" }}</span>
          <span class="text-body-secondary small">
            {{ localNfcEnabled ? "Select a spool, tune the payload, then preview or write through the configured reader." : "Select a spool and tune the payload for preview or browser-based NFC workflows." }}
          </span>
        </div>
      </div>

      <div class="row g-3">
        <div class="col-12">
          <label class="form-label" for="spool-id">Spool</label>
          <SpoolPicker
            input-id="spool-id"
            :spools="spools"
            :model-value="selectedSpoolId"
            :selected-label="selectedSpoolLabel"
            :disabled="busy"
            @update:model-value="emit('update:selectedSpoolId', $event)"
          />
        </div>

        <div v-for="field in fields" :key="field.key" class="col-12 col-md-6 col-xl-3">
          <label class="form-label" :for="field.key">{{ field.label }}</label>
          <input
            :id="field.key"
            class="form-control"
            :value="overrides[field.key] || ''"
            :placeholder="field.placeholder"
            :disabled="busy || !selectedSpoolId"
            @input="updateOverride(field.key, $event.target.value)"
          />
        </div>
      </div>
    </div>

    <div class="card-footer bg-transparent">
      <div class="d-flex flex-wrap gap-2">
        <button
          type="button"
          class="btn btn-outline-primary btn-icon"
          :disabled="busy || !selectedSpoolId"
          @click="emit('preview')"
        >
          <i class="bi bi-eye"></i>
          {{ previewBusy ? "Preparing…" : "Preview Payload" }}
        </button>

        <button
          v-if="localNfcEnabled"
          type="button"
          class="btn btn-primary btn-icon"
          :disabled="busy || !selectedSpoolId"
          @click="emit('write')"
        >
          <i class="bi bi-disc"></i>
          {{ writeBusy ? "Writing…" : "Write Tag" }}
        </button>

        <button
          v-if="localNfcEnabled"
          type="button"
          class="btn btn-secondary btn-icon"
          :disabled="busy"
          @click="emit('read')"
        >
          <i class="bi bi-broadcast"></i>
          {{ readBusy ? "Reading…" : "Read Existing Tag" }}
        </button>
      </div>
    </div>
  </div>
</template>
