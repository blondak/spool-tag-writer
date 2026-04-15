<script setup>
import { computed, ref, watch } from "vue";
import CardHelpTooltip from "./CardHelpTooltip.vue";

const props = defineProps({
  preview: {
    type: Object,
    default: null,
  },
  busy: {
    type: Boolean,
    default: false,
  },
});

const activeTab = ref("payload");
const prettyPayload = computed(() => (props.preview ? JSON.stringify(props.preview.payload, null, 2) : ""));
const prettyOverrides = computed(() => {
  if (!props.preview?.overrides || !Object.keys(props.preview.overrides).length) {
    return "";
  }

  return JSON.stringify(props.preview.overrides, null, 2);
});
const prettySpool = computed(() => (props.preview?.spool ? JSON.stringify(props.preview.spool, null, 2) : ""));

watch(
  () => [prettyPayload.value, prettyOverrides.value, prettySpool.value],
  ([nextPayload, nextOverrides, nextSpool]) => {
    const availableTabs = new Set();

    if (nextPayload) {
      availableTabs.add("payload");
    }
    if (nextOverrides) {
      availableTabs.add("overrides");
    }
    if (nextSpool) {
      availableTabs.add("spool");
    }

    if (availableTabs.has(activeTab.value)) {
      return;
    }

    if (availableTabs.has("payload")) {
      activeTab.value = "payload";
      return;
    }

    if (availableTabs.has("overrides")) {
      activeTab.value = "overrides";
      return;
    }

    if (availableTabs.has("spool")) {
      activeTab.value = "spool";
    }
  },
  { immediate: true },
);

const statusBadgeClass = computed(() => (props.busy ? "text-bg-warning" : "text-bg-light"));
const statusText = computed(() => (props.busy ? "Refreshing…" : "Ready to inspect"));
const helpHtml =
  "<strong>OpenSpool Preview</strong><br>The payload shown here comes from the API layer before any write operation is triggered.";

const currentContent = computed(() => {
  if (activeTab.value === "overrides" && prettyOverrides.value) {
    return prettyOverrides.value;
  }

  if (activeTab.value === "spool" && prettySpool.value) {
    return prettySpool.value;
  }

  return prettyPayload.value;
});
</script>

<template>
  <div id="preview-panel" class="card card-outline card-secondary h-100">
    <div class="card-header">
      <h3 class="card-title">
        <i class="bi bi-eye me-2"></i>
        Payload Preview
      </h3>
      <div class="card-tools">
        <span class="badge" :class="statusBadgeClass">{{ statusText }}</span>
        <CardHelpTooltip
          label="Preview help"
          :html="helpHtml"
        />
      </div>
    </div>

    <div class="card-body">
      <div v-if="preview">
        <div class="d-flex flex-wrap gap-2 mb-4">
          <span class="badge text-bg-light">
            <i class="bi bi-disc me-1"></i>
            Spool #{{ preview.spool?.id ?? "?" }}
          </span>
          <span class="badge text-bg-warning-subtle text-warning-emphasis">
            <i class="bi bi-hdd me-1"></i>
            {{ preview.payload_size }} bytes
          </span>
          <span class="badge text-bg-info-subtle text-info-emphasis">
            <i class="bi bi-filetype-json me-1"></i>
            application/json
          </span>
        </div>

        <ul class="nav nav-pills mb-3" role="tablist">
          <li class="nav-item">
            <button
              type="button"
              class="nav-link"
              :class="{ active: activeTab === 'payload' }"
              @click="activeTab = 'payload'"
            >
              Payload
            </button>
          </li>
          <li v-if="prettyOverrides" class="nav-item">
            <button
              type="button"
              class="nav-link"
              :class="{ active: activeTab === 'overrides' }"
              @click="activeTab = 'overrides'"
            >
              Overrides
            </button>
          </li>
          <li v-if="prettySpool" class="nav-item">
            <button
              type="button"
              class="nav-link"
              :class="{ active: activeTab === 'spool' }"
              @click="activeTab = 'spool'"
            >
              Spool
            </button>
          </li>
        </ul>

        <div class="card card-outline card-light mb-0">
          <div class="card-body p-0">
            <pre class="json-block">{{ currentContent }}</pre>
          </div>
        </div>
      </div>

      <div v-else class="callout callout-info mb-0">
        <h5 class="mb-2">No preview prepared yet</h5>
        <p class="mb-0">Use “Preview Payload”, create a spool from Prusament, or prepare a phone write to populate this panel.</p>
      </div>
    </div>
  </div>
</template>
