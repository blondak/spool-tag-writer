<script setup>
import { computed } from "vue";
import CardHelpTooltip from "./CardHelpTooltip.vue";

const props = defineProps({
  available: {
    type: Boolean,
    default: false,
  },
  secureContextOk: {
    type: Boolean,
    default: false,
  },
  status: {
    type: String,
    default: "",
  },
  statusTone: {
    type: String,
    default: "secondary",
  },
  result: {
    type: Object,
    default: null,
  },
  busyRead: {
    type: Boolean,
    default: false,
  },
  busyWrite: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["read", "write"]);

const statusClass = computed(() => {
  const normalized = props.statusTone === "secondary" ? "info" : props.statusTone || "info";
  return `callout callout-${normalized}`;
});
const availabilityText = computed(() => {
  if (props.available && props.secureContextOk) {
    return "Android Chrome can read and write the tag directly in the browser.";
  }

  if (props.available) {
    return "Web NFC is available, but the page must run under HTTPS or localhost.";
  }

  return "This browser does not expose the Web NFC API.";
});
const helpHtml = computed(
  () => `<strong>Phone-side NDEF</strong><br>${availabilityText.value}`,
);

const prettyResult = computed(() => (props.result ? JSON.stringify(props.result, null, 2) : ""));
</script>

<template>
  <div id="web-nfc-panel" class="card card-outline card-info h-100">
    <div class="card-header">
      <h3 class="card-title">
        <i class="bi bi-phone me-2"></i>
        Web NFC
      </h3>
      <div class="card-tools">
        <CardHelpTooltip
          label="Web NFC help"
          :html="helpHtml"
        />
        <button type="button" class="btn btn-tool" data-lte-toggle="card-collapse" aria-label="Collapse card">
          <i data-lte-icon="expand" class="bi bi-plus-lg"></i>
          <i data-lte-icon="collapse" class="bi bi-dash-lg"></i>
        </button>
      </div>
    </div>

    <div class="card-body">
      <div class="row g-3 mb-4">
        <div class="col-12 col-md-6">
          <div class="info-box mb-0">
            <span class="info-box-icon" :class="available ? 'text-bg-success' : 'text-bg-secondary'">
              <i class="bi bi-phone-vibrate"></i>
            </span>
            <div class="info-box-content">
              <span class="info-box-text">Web NFC API</span>
              <span class="info-box-number">{{ available ? "Available" : "Unsupported" }}</span>
            </div>
          </div>
        </div>
        <div class="col-12 col-md-6">
          <div class="info-box mb-0">
            <span class="info-box-icon" :class="secureContextOk ? 'text-bg-success' : 'text-bg-warning'">
              <i class="bi bi-shield-lock"></i>
            </span>
            <div class="info-box-content">
              <span class="info-box-text">Secure Context</span>
              <span class="info-box-number">{{ secureContextOk ? "Ready" : "Required" }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="d-flex flex-wrap gap-2">
        <button
          type="button"
          class="btn btn-outline-info btn-icon"
          :disabled="!available || !secureContextOk || busyRead"
          @click="emit('read')"
        >
          <i class="bi bi-rss"></i>
          {{ busyRead ? "Waiting for tag…" : "Read with Phone" }}
        </button>

        <button
          type="button"
          class="btn btn-info btn-icon text-white"
          :disabled="!available || !secureContextOk || busyWrite"
          @click="emit('write')"
        >
          <i class="bi bi-nfc"></i>
          {{ busyWrite ? "Writing…" : "Write with Phone" }}
        </button>
      </div>

      <div v-if="status" :class="statusClass" class="mt-4">
        <p class="mb-0">{{ status }}</p>
      </div>

      <div v-if="result" class="card card-outline card-light mt-4 mb-0">
        <div class="card-header"><h3 class="card-title">Phone Read / Write Result</h3></div>
        <div class="card-body">
          <pre class="json-block">{{ prettyResult }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>
