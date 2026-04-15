<script setup>
import CardHelpTooltip from "./CardHelpTooltip.vue";
import SpoolPicker from "./SpoolPicker.vue";

defineProps({
  spools: {
    type: Array,
    default: () => [],
  },
  slots: {
    type: Array,
    default: () => [],
  },
  extruderCount: {
    type: Number,
    default: 4,
  },
  assignedCount: {
    type: Number,
    default: 0,
  },
  busy: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits([
  "update:extruderCount",
  "update:slotSpool",
  "open-tag-tools",
]);

const extruderCountOptions = Array.from({ length: 12 }, (_, index) => index + 1);
</script>

<template>
  <div id="extruder-mapping-panel" class="card card-outline card-primary h-100">
    <div class="card-header">
      <h3 class="card-title">
        <i class="bi bi-diagram-3 me-2"></i>
        Extruder Mapping
      </h3>
      <div class="card-tools">
        <div class="extruder-count-addon input-group input-group-sm">
          <span class="input-group-text">Extruders</span>
          <select
            id="extruder-count"
            class="form-select form-select-sm"
            :value="extruderCount"
            :disabled="busy"
            @change="emit('update:extruderCount', Number($event.target.value))"
          >
            <option v-for="count in extruderCountOptions" :key="count" :value="count">
              {{ count }}
            </option>
          </select>
        </div>
        <span class="badge text-bg-light">{{ assignedCount }} / {{ extruderCount }} assigned</span>
        <CardHelpTooltip
          label="Extruder mapping help"
          html="<strong>Extruder Mapping</strong><br>Assign a default spool to each extruder. This screen is the primary fallback when the printer cannot identify the loaded spool from RFID."
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
      <div class="callout callout-info mb-4">
        <h5 class="mb-2">Fallback assignment</h5>
        <p class="mb-0">
          Use this as the primary operator screen. If the printer cannot identify a spool from RFID,
          the assigned extruder spool can still be used for Moonraker or Spoolman automation later.
        </p>
      </div>

      <div class="list-group list-group-flush">
        <div v-for="slot in slots" :key="slot.toolName" class="list-group-item px-0 py-3">
          <div class="extruder-slot-row">
            <div class="extruder-slot-label">
              <span class="badge text-bg-primary">{{ slot.label }}</span>
              <div class="text-body-secondary small mt-2">{{ slot.toolName }}</div>
            </div>

            <div class="extruder-slot-picker">
              <label class="form-label visually-hidden" :for="`extruder-slot-${slot.index}`">
                {{ slot.label }} spool
              </label>
              <SpoolPicker
                :input-id="`extruder-slot-${slot.index}`"
                :spools="spools"
                :model-value="slot.spoolId"
                :selected-label="slot.spoolLabel"
                :disabled="busy"
                @update:model-value="emit('update:slotSpool', { toolName: slot.toolName, spoolId: $event })"
              />
            </div>

            <div class="extruder-slot-actions">
              <span class="badge" :class="slot.spoolId ? 'text-bg-success' : 'text-bg-secondary'">
                {{ slot.spoolId ? "Assigned" : "Unassigned" }}
              </span>

              <div class="btn-group">
                <button
                  type="button"
                  class="btn btn-outline-secondary btn-sm"
                  :disabled="busy || !slot.spoolId"
                  @click="emit('open-tag-tools', slot.spoolId)"
                >
                  <i class="bi bi-upc-scan"></i>
                </button>
                <button
                  type="button"
                  class="btn btn-outline-danger btn-sm"
                  :disabled="busy || !slot.spoolId"
                  @click="emit('update:slotSpool', { toolName: slot.toolName, spoolId: '' })"
                >
                  <i class="bi bi-x-lg"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
