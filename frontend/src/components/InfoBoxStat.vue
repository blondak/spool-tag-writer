<script setup>
defineProps({
  icon: {
    type: String,
    required: true,
  },
  iconClass: {
    type: String,
    default: "text-bg-primary",
  },
  label: {
    type: String,
    required: true,
  },
  value: {
    type: String,
    required: true,
  },
  hint: {
    type: String,
    default: "",
  },
});
</script>

<template>
  <div class="info-box shadow-sm">
    <span class="info-box-icon" :class="iconClass">
      <i :class="icon"></i>
    </span>
    <div class="info-box-content">
      <span class="info-box-text">{{ label }}</span>
      <span class="info-box-number">{{ value }}</span>
      <span v-if="hint" class="text-body-secondary small">{{ hint }}</span>
    </div>
  </div>
</template>
