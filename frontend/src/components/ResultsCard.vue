<script setup>
import { computed, ref, watch } from "vue";
import CardHelpTooltip from "./CardHelpTooltip.vue";

const props = defineProps({
  result: {
    type: Object,
    default: null,
  },
});

const activeTab = ref("write");
const prettyWrite = computed(() => (props.result?.write ? JSON.stringify(props.result.write, null, 2) : ""));
const prettyRead = computed(() => (props.result?.read ? JSON.stringify(props.result.read, null, 2) : ""));
const prettyPayload = computed(() => {
  const payload = props.result?.read?.payload_json;

  if (!payload) {
    return "";
  }

  return JSON.stringify(payload, null, 2);
});

watch(
  () => [prettyWrite.value, prettyRead.value, prettyPayload.value],
  ([nextWrite, nextRead, nextPayload]) => {
    const availableTabs = new Set();

    if (nextWrite) {
      availableTabs.add("write");
    }
    if (nextRead) {
      availableTabs.add("read");
    }
    if (nextPayload) {
      availableTabs.add("payload");
    }

    if (availableTabs.has(activeTab.value)) {
      return;
    }

    if (availableTabs.has("write")) {
      activeTab.value = "write";
      return;
    }

    if (availableTabs.has("read")) {
      activeTab.value = "read";
      return;
    }

    if (availableTabs.has("payload")) {
      activeTab.value = "payload";
    }
  },
  { immediate: true },
);

const statusBadgeClass = computed(() => (props.result ? "text-bg-success" : "text-bg-light"));
const statusText = computed(() => (props.result ? "Reader telemetry" : "Waiting for reader"));
const helpHtml =
  "<strong>Write / Readback</strong><br>Results from the backend reader stay isolated from the visual components and are rendered here once the API replies.";

const currentContent = computed(() => {
  if (activeTab.value === "read" && prettyRead.value) {
    return prettyRead.value;
  }

  if (activeTab.value === "payload" && prettyPayload.value) {
    return prettyPayload.value;
  }

  return prettyWrite.value;
});
</script>

<template>
  <div id="results-panel" class="card card-outline card-success">
    <div class="card-header">
      <h3 class="card-title">
        <i class="bi bi-journal-code me-2"></i>
        Write / Readback
      </h3>
      <div class="card-tools">
        <span class="badge" :class="statusBadgeClass">{{ statusText }}</span>
        <CardHelpTooltip
          label="Readback help"
          :html="helpHtml"
        />
      </div>
    </div>

    <div class="card-body">
      <div v-if="result">
        <ul class="nav nav-pills mb-3" role="tablist">
          <li v-if="prettyWrite" class="nav-item">
            <button
              type="button"
              class="nav-link"
              :class="{ active: activeTab === 'write' }"
              @click="activeTab = 'write'"
            >
              Write
            </button>
          </li>
          <li v-if="prettyRead" class="nav-item">
            <button
              type="button"
              class="nav-link"
              :class="{ active: activeTab === 'read' }"
              @click="activeTab = 'read'"
            >
              Read
            </button>
          </li>
          <li v-if="prettyPayload" class="nav-item">
            <button
              type="button"
              class="nav-link"
              :class="{ active: activeTab === 'payload' }"
              @click="activeTab = 'payload'"
            >
              Decoded Payload
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
        <h5 class="mb-2">No backend reader result yet</h5>
        <p class="mb-0">Write a tag or read an existing one through the configured NFC backend to inspect the response here.</p>
      </div>
    </div>
  </div>
</template>
