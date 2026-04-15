<script setup>
import CardHelpTooltip from "./CardHelpTooltip.vue";
import SpoolPicker from "./SpoolPicker.vue";

const PRINTER_RFID_CHANNELS = [0, 1, 2, 3];

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
  printerRfidChannel: {
    type: Number,
    default: 0,
  },
  printerRfidStatus: {
    type: String,
    default: "",
  },
  printerRfidStatusTone: {
    type: String,
    default: "secondary",
  },
  printerRfidResult: {
    type: Object,
    default: null,
  },
  printerRfidSelectedSpoolId: {
    type: String,
    default: "",
  },
  printerRfidSelectedSpoolLabel: {
    type: String,
    default: "",
  },
  printerRfidReadBusy: {
    type: Boolean,
    default: false,
  },
  printerRfidAssignBusy: {
    type: Boolean,
    default: false,
  },
  busy: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits([
  "update:printerRfidChannel",
  "update:printerRfidSelectedSpoolId",
  "read-printer-rfid",
  "assign-printer-rfid-lot-nr",
]);

const statusBadgeClass = (tone) => {
  switch (tone) {
    case "success":
      return "text-bg-success";
    case "danger":
      return "text-bg-danger";
    case "warning":
      return "text-bg-warning";
    case "info":
      return "text-bg-info";
    default:
      return "text-bg-secondary";
  }
};

const printerRfidSummary = () => {
  const result = props.printerRfidResult;
  if (!result) {
    return "No U1 RFID read yet.";
  }

  if (result.card_uid) {
    return `UID ${result.card_uid}`;
  }

  return `No RFID UID detected on ${result.label || `T${props.printerRfidChannel}`}.`;
};

const printerRfidMeta = () => {
  const result = props.printerRfidResult;
  if (!result) {
    return "";
  }

  const parts = [result.vendor, result.manufacturer, result.main_type, result.sub_type].filter(Boolean);
  return parts.join(" · ");
};

const printerRfidMatchState = () => {
  const matches = Array.isArray(props.printerRfidResult?.matched_spools) ? props.printerRfidResult.matched_spools : [];
  if (!props.printerRfidResult?.card_uid) {
    return "";
  }
  if (matches.length === 1) {
    return `Matched spool #${matches[0].id}`;
  }
  if (matches.length > 1) {
    return `${matches.length} spools match this UID`;
  }
  return "No spool matched this UID";
};

const printerRfidMatchTone = () => {
  const matches = Array.isArray(props.printerRfidResult?.matched_spools) ? props.printerRfidResult.matched_spools : [];
  if (!props.printerRfidResult?.card_uid) {
    return "text-bg-secondary";
  }
  if (matches.length === 1) {
    return "text-bg-success";
  }
  return "text-bg-warning";
};
</script>

<template>
  <div class="card card-outline card-info h-100">
    <div class="card-header">
      <h3 class="card-title">
        <i class="bi bi-router me-2"></i>
        U1 RFID Pairing
      </h3>
      <div class="card-tools">
        <CardHelpTooltip
          label="U1 RFID pairing help"
          html="<strong>U1 RFID Pairing</strong><br>Read a card UID from a printer channel, try to match it to an existing spool, and optionally choose a spool manually before writing the UID back to Spoolman lot_nr."
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
      <div class="rfid-pairing-grid">
        <div class="rfid-pairing-controls">
          <label class="form-label mb-1" for="printer-rfid-channel">U1 RFID Channel</label>
          <select
            id="printer-rfid-channel"
            class="form-select"
            :value="printerRfidChannel"
            :disabled="busy || printerRfidReadBusy || printerRfidAssignBusy"
            @change="emit('update:printerRfidChannel', Number($event.target.value))"
          >
            <option v-for="channel in PRINTER_RFID_CHANNELS" :key="channel" :value="channel">
              T{{ channel }}
            </option>
          </select>
        </div>

        <div class="rfid-pairing-status">
          <div class="d-flex flex-wrap align-items-center gap-2 mb-1">
            <span class="badge" :class="statusBadgeClass(printerRfidStatusTone)">
              {{ printerRfidStatus || "Reader standby" }}
            </span>
            <span class="small text-body-secondary">{{ printerRfidSummary() }}</span>
          </div>
          <div v-if="printerRfidMeta()" class="small text-body-secondary">
            {{ printerRfidMeta() }}
          </div>
          <div v-if="printerRfidMatchState()" class="mt-2">
            <span class="badge" :class="printerRfidMatchTone()">
              {{ printerRfidMatchState() }}
            </span>
          </div>
        </div>

        <div class="rfid-pairing-actions">
          <button
            type="button"
            class="btn btn-outline-secondary btn-icon"
            :disabled="busy || printerRfidReadBusy || printerRfidAssignBusy"
            @click="emit('read-printer-rfid')"
          >
            <i class="bi bi-router"></i>
            {{ printerRfidReadBusy ? "Reading U1…" : "Read U1 RFID" }}
          </button>

          <button
            type="button"
            class="btn btn-outline-primary btn-icon"
            :disabled="busy || (!printerRfidSelectedSpoolId && !selectedSpoolId) || printerRfidAssignBusy || printerRfidReadBusy"
            @click="emit('assign-printer-rfid-lot-nr')"
          >
            <i class="bi bi-link-45deg"></i>
            {{ printerRfidAssignBusy ? "Saving…" : "Save UID To lot_nr" }}
          </button>
        </div>
      </div>

      <div class="mt-4">
        <label class="form-label mb-1" for="printer-rfid-spool-id">Spool For UID Write</label>
        <SpoolPicker
          input-id="printer-rfid-spool-id"
          :spools="spools"
          :model-value="printerRfidSelectedSpoolId"
          :selected-label="printerRfidSelectedSpoolLabel"
          :disabled="busy || printerRfidReadBusy || printerRfidAssignBusy"
          @update:model-value="emit('update:printerRfidSelectedSpoolId', $event)"
        />
      </div>
    </div>
  </div>
</template>
