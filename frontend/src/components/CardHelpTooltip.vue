<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import Tooltip from "bootstrap/js/dist/tooltip";

const props = defineProps({
  html: {
    type: String,
    required: true,
  },
  placement: {
    type: String,
    default: "left",
  },
  label: {
    type: String,
    default: "Show help",
  },
});

const triggerRef = ref(null);
let tooltipInstance = null;

const mountTooltip = () => {
  if (!triggerRef.value) {
    return;
  }

  tooltipInstance = Tooltip.getOrCreateInstance(triggerRef.value, {
    html: true,
    placement: props.placement,
    title: props.html,
    trigger: "hover focus",
    customClass: "card-help-tooltip",
  });
};

const resetTooltip = () => {
  if (tooltipInstance) {
    tooltipInstance.dispose();
    tooltipInstance = null;
  }

  mountTooltip();
};

onMounted(mountTooltip);
onBeforeUnmount(() => {
  if (tooltipInstance) {
    tooltipInstance.dispose();
    tooltipInstance = null;
  }
});

watch(() => props.html, resetTooltip);
</script>

<template>
  <button
    ref="triggerRef"
    type="button"
    class="btn btn-tool text-body-secondary card-help-button"
    :aria-label="label"
  >
    <i class="bi bi-question-circle"></i>
  </button>
</template>
