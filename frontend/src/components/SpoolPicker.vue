<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

import { formatSpoolLabel } from "../utils/spoolUi.js";

const props = defineProps({
  spools: {
    type: Array,
    default: () => [],
  },
  modelValue: {
    type: [String, Number],
    default: "",
  },
  selectedLabel: {
    type: String,
    default: "",
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  inputId: {
    type: String,
    default: "spool-picker",
  },
  emptyLabel: {
    type: String,
    default: "Choose spool…",
  },
  searchPlaceholder: {
    type: String,
    default: "Search by ID, manufacturer, filament…",
  },
  noResultsLabel: {
    type: String,
    default: "No spools match the current search.",
  },
});

const emit = defineEmits(["update:modelValue"]);

const rootRef = ref(null);
const searchInputRef = ref(null);
const searchQuery = ref("");
const dropdownOpen = ref(false);

const formatRemainingWeight = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${Math.round(numeric)} g remaining` : "";
};

const buildSpoolSearchText = (spool) => {
  const filament = spool?.filament && typeof spool.filament === "object" ? spool.filament : {};

  return [
    spool?.id,
    spool?.name,
    spool?.manufacturer,
    spool?.remaining_weight,
    filament?.name,
    filament?.material,
    filament?.vendor?.name,
    filament?.vendor,
    filament?.manufacturer_name,
    filament?.manufacturer,
    filament?.brand,
    filament?.external_id,
  ]
    .filter((value) => value !== null && value !== undefined && String(value).trim())
    .join(" ")
    .toLowerCase();
};

const formatSpoolMeta = (spool) => {
  const filament = spool?.filament && typeof spool.filament === "object" ? spool.filament : {};
  const parts = [
    filament?.external_id ? `External ID ${filament.external_id}` : "",
    formatRemainingWeight(spool?.remaining_weight),
  ].filter(Boolean);

  return parts.join(" • ");
};

const selectedSpool = computed(() =>
  props.spools.find((spool) => String(spool.id) === String(props.modelValue)) || null,
);
const filteredSpools = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();

  if (!query) {
    return props.spools;
  }

  return props.spools.filter((spool) => buildSpoolSearchText(spool).includes(query));
});
const resolvedSelectedLabel = computed(
  () => props.selectedLabel || formatSpoolLabel(selectedSpool.value) || props.emptyLabel,
);
const pickerDisabled = computed(() => props.disabled || !props.spools.length);

const closeDropdown = () => {
  dropdownOpen.value = false;
  searchQuery.value = "";
};

const openDropdown = async () => {
  if (pickerDisabled.value) {
    return;
  }

  dropdownOpen.value = true;
  await nextTick();
  searchInputRef.value?.focus();
};

const toggleDropdown = async () => {
  if (dropdownOpen.value) {
    closeDropdown();
    return;
  }

  await openDropdown();
};

const selectSpool = (spoolId) => {
  emit("update:modelValue", String(spoolId));
  closeDropdown();
};

const handleDocumentPointerDown = (event) => {
  if (!dropdownOpen.value) {
    return;
  }

  if (!rootRef.value?.contains(event.target)) {
    closeDropdown();
  }
};

const handleSearchKeydown = (event) => {
  if (event.key === "Escape") {
    closeDropdown();
    return;
  }

  if (event.key === "Enter" && filteredSpools.value.length === 1) {
    selectSpool(filteredSpools.value[0].id);
  }
};

onMounted(() => {
  document.addEventListener("pointerdown", handleDocumentPointerDown);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", handleDocumentPointerDown);
});
</script>

<template>
  <div ref="rootRef" class="spool-picker">
    <button
      :id="inputId"
      type="button"
      class="form-select text-start spool-picker-toggle"
      :disabled="pickerDisabled"
      :aria-expanded="dropdownOpen ? 'true' : 'false'"
      @click="toggleDropdown"
    >
      <span class="spool-picker-selection">{{ resolvedSelectedLabel }}</span>
    </button>

    <div v-if="dropdownOpen" class="dropdown-menu show spool-picker-menu w-100">
      <div class="spool-picker-search border-bottom p-2">
        <div class="input-group input-group-sm">
          <span class="input-group-text">
            <i class="bi bi-search"></i>
          </span>
          <input
            ref="searchInputRef"
            v-model="searchQuery"
            class="form-control"
            :placeholder="searchPlaceholder"
            @keydown="handleSearchKeydown"
          />
          <button
            v-if="searchQuery"
            type="button"
            class="btn btn-outline-secondary"
            @click="searchQuery = ''"
          >
            <i class="bi bi-x-lg"></i>
          </button>
        </div>
        <div class="form-text mt-2 mb-0">{{ filteredSpools.length }} / {{ spools.length }} spools visible</div>
      </div>

      <div v-if="filteredSpools.length" class="spool-picker-list py-1">
        <button
          v-for="spool in filteredSpools"
          :key="spool.id"
          type="button"
          class="dropdown-item spool-picker-option"
          :class="{ active: String(spool.id) === String(modelValue) }"
          @click="selectSpool(spool.id)"
        >
          <span class="spool-picker-option-label">{{ formatSpoolLabel(spool) }}</span>
          <span v-if="formatSpoolMeta(spool)" class="spool-picker-option-meta">
            {{ formatSpoolMeta(spool) }}
          </span>
        </button>
      </div>

      <div v-else class="spool-picker-empty px-3 py-3 text-body-secondary small">
        {{ noResultsLabel }}
      </div>
    </div>
  </div>
</template>
