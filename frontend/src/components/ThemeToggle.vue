<script setup>
import { computed } from "vue";

const props = defineProps({
  theme: {
    type: String,
    required: true,
  },
  resolvedTheme: {
    type: String,
    required: true,
  },
});

const emit = defineEmits(["change"]);

const options = [
  {
    value: "light",
    icon: "bi-sun-fill",
    label: "Light",
  },
  {
    value: "dark",
    icon: "bi-moon-stars-fill",
    label: "Dark",
  },
  {
    value: "auto",
    icon: "bi-circle-half",
    label: "Auto",
  },
];

const currentOption = computed(
  () => options.find((option) => option.value === props.theme) || options[2],
);
</script>

<template>
  <a class="nav-link" data-bs-toggle="dropdown" href="#" role="button" aria-label="Toggle theme">
    <i :class="['bi', currentOption.icon]"></i>
  </a>
  <ul class="dropdown-menu dropdown-menu-end" style="--bs-dropdown-min-width: 9rem">
    <li v-for="option in options" :key="option.value">
      <button
        type="button"
        class="dropdown-item d-flex align-items-center"
        :class="{ active: theme === option.value }"
        :aria-pressed="theme === option.value"
        @click="emit('change', option.value)"
      >
        <i :class="['bi', option.icon, 'me-2']"></i>
        {{ option.label }}
        <i
          class="bi bi-check-lg ms-auto"
          :class="theme === option.value ? '' : 'd-none'"
        ></i>
      </button>
    </li>
    <li><hr class="dropdown-divider" /></li>
    <li>
      <span class="dropdown-item-text small text-body-secondary">
        Active: {{ resolvedTheme }}
      </span>
    </li>
  </ul>
</template>
