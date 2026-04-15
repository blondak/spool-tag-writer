<script setup>
import ThemeToggle from "./ThemeToggle.vue";

defineProps({
  uiContext: {
    type: Object,
    required: true,
  },
  activeScreenLabel: {
    type: String,
    default: "",
  },
  activeSpoolLabel: {
    type: String,
    default: "",
  },
  theme: {
    type: String,
    required: true,
  },
  resolvedTheme: {
    type: String,
    required: true,
  },
});

const emit = defineEmits(["change-theme"]);
</script>

<template>
  <nav class="app-header navbar navbar-expand bg-body">
    <div class="container-fluid">
      <ul class="navbar-nav align-items-center">
        <li class="nav-item">
          <a class="nav-link" data-lte-toggle="sidebar" href="#" role="button" aria-label="Toggle sidebar">
            <i class="bi bi-list fs-4"></i>
          </a>
        </li>
        <li class="nav-item d-none d-xl-flex align-items-center">
          <span class="nav-link text-body-secondary">
            <i class="bi bi-grid-1x2 me-1"></i>
            {{ activeScreenLabel || "Spool Dashboard" }}
          </span>
        </li>
        <li class="nav-item d-none d-xxl-flex align-items-center">
          <span class="nav-link text-body-secondary">
            <i class="bi bi-layers-half me-1"></i>
            {{ activeSpoolLabel || "No spool selected" }}
          </span>
        </li>
      </ul>

      <ul class="navbar-nav ms-auto align-items-center">
        <li class="nav-item d-none d-sm-block">
          <span class="nav-link text-body-secondary">
            <i class="bi bi-cpu me-1"></i>
            {{ uiContext.nfc_backend || "unknown" }}
          </span>
        </li>
        <li class="nav-item d-none d-lg-block">
          <span class="nav-link text-body-secondary">
            <i class="bi bi-broadcast-pin me-1"></i>
            {{ uiContext.nfc_reader_name || "reader pending" }}
          </span>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="#" data-lte-toggle="fullscreen" aria-label="Toggle fullscreen">
            <i data-lte-icon="maximize" class="bi bi-arrows-fullscreen"></i>
            <i data-lte-icon="minimize" class="bi bi-fullscreen-exit" style="display: none"></i>
          </a>
        </li>
        <li class="nav-item dropdown">
          <ThemeToggle
            :theme="theme"
            :resolved-theme="resolvedTheme"
            @change="emit('change-theme', $event)"
          />
        </li>
      </ul>
    </div>
  </nav>
</template>
