<script setup>
import { computed } from "vue";

import CardHelpTooltip from "./CardHelpTooltip.vue";

const props = defineProps({
  status: {
    type: Object,
    default: () => ({}),
  },
});

const formatToolLabel = (toolName) => {
  const normalized = String(toolName || "").trim();
  if (!normalized) {
    return "—";
  }
  if (normalized === "extruder") {
    return "T0";
  }
  const match = normalized.match(/^extruder(\d+)$/);
  if (match) {
    return `T${match[1]}`;
  }
  return normalized;
};

const formatTimestamp = (value) => {
  const text = String(value || "").trim();
  if (!text) {
    return "—";
  }

  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text;
  }

  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
};

const agentState = computed(() => {
  const agent = props.status?.agent || {};
  if (agent.online) {
    return { label: "Connected", badgeClass: "text-bg-success" };
  }
  if (agent.stale || agent.connected) {
    return { label: "No heartbeat", badgeClass: "text-bg-warning" };
  }
  return { label: "Offline", badgeClass: "text-bg-secondary" };
});

const spoolmanState = computed(() =>
  props.status?.spoolmanConnected
    ? { label: "Connected", badgeClass: "text-bg-success" }
    : { label: "Disconnected", badgeClass: "text-bg-warning" },
);

const syncState = computed(() =>
  props.status?.syncOk
    ? { label: "In sync", badgeClass: "text-bg-success" }
    : { label: "Mismatch", badgeClass: "text-bg-warning" },
);

const lastSyncSummary = computed(() => {
  const agent = props.status?.agent || {};
  const toolLabel = formatToolLabel(agent.activeTool || props.status?.activeTool);
  const targetSpoolId = agent.targetSpoolId ?? props.status?.mappedSpoolId ?? null;

  if (!toolLabel || toolLabel === "—") {
    return "No sync attempt recorded yet.";
  }
  if (targetSpoolId) {
    return `${toolLabel} -> #${targetSpoolId}`;
  }
  return `${toolLabel} -> clear active spool`;
});

const lastSwitchSummary = computed(() => {
  const agent = props.status?.agent || {};
  if (!agent.lastSwitchAt) {
    return "No active spool switch recorded yet.";
  }

  const previous = agent.previousSpoolId ? `#${agent.previousSpoolId}` : "none";
  const current = agent.activeSpoolId ? `#${agent.activeSpoolId}` : "none";
  const toolLabel = formatToolLabel(agent.activeTool);
  return `${toolLabel}: ${previous} -> ${current}`;
});
</script>

<template>
  <div class="card card-outline card-secondary h-100">
    <div class="card-header">
      <h3 class="card-title">
        <i class="bi bi-broadcast-pin me-2"></i>
        Moonraker Sync
      </h3>
      <div class="card-tools">
        <CardHelpTooltip
          label="Moonraker sync help"
          html="<strong>Moonraker Sync</strong><br>Shows whether the local agent is still connected to Moonraker, what active spool Moonraker currently exposes, and what the last automatic spool switch did."
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
      <div class="sync-status-grid">
        <div class="sync-status-item">
          <div class="sync-status-label">Agent</div>
          <div class="sync-status-value">
            <span class="badge" :class="agentState.badgeClass">{{ agentState.label }}</span>
          </div>
          <div class="sync-status-meta">Last heartbeat: {{ formatTimestamp(status.agent?.lastSeenAt) }}</div>
        </div>

        <div class="sync-status-item">
          <div class="sync-status-label">Spoolman</div>
          <div class="sync-status-value">
            <span class="badge" :class="spoolmanState.badgeClass">{{ spoolmanState.label }}</span>
          </div>
          <div class="sync-status-meta">Current tool: {{ formatToolLabel(status.activeTool) }}</div>
        </div>

        <div class="sync-status-item">
          <div class="sync-status-label">Active Spool</div>
          <div class="sync-status-value">
            <span class="badge" :class="syncState.badgeClass">
              {{ status.activeSpoolId ? `#${status.activeSpoolId}` : "—" }}
            </span>
          </div>
          <div class="sync-status-meta">Mapped spool: {{ status.mappedSpoolId ? `#${status.mappedSpoolId}` : "—" }}</div>
        </div>

        <div class="sync-status-item">
          <div class="sync-status-label">Last Sync</div>
          <div class="sync-status-value">{{ lastSyncSummary }}</div>
          <div class="sync-status-meta">{{ formatTimestamp(status.agent?.lastSyncAt) }}</div>
        </div>

        <div class="sync-status-item">
          <div class="sync-status-label">Last Switch</div>
          <div class="sync-status-value">{{ lastSwitchSummary }}</div>
          <div class="sync-status-meta">{{ formatTimestamp(status.agent?.lastSwitchAt) }}</div>
        </div>

        <div class="sync-status-item">
          <div class="sync-status-label">Counters</div>
          <div class="sync-status-value">
            {{ status.agent?.syncCount || 0 }} syncs / {{ status.agent?.switchCount || 0 }} switches
          </div>
          <div class="sync-status-meta">Connected since: {{ formatTimestamp(status.agent?.connectedAt) }}</div>
        </div>
      </div>

      <div v-if="status.agent?.lastError" class="callout callout-warning mt-3 mb-0">
        <h5 class="mb-2">
          <i class="bi bi-exclamation-triangle me-2"></i>
          Last Agent Error
        </h5>
        <p class="mb-1">{{ status.agent.lastError }}</p>
        <p class="mb-0 small text-body-secondary">{{ formatTimestamp(status.agent.lastErrorAt) }}</p>
      </div>
    </div>
  </div>
</template>
