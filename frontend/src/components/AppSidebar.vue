<script setup>
defineProps({
  activeScreen: {
    type: String,
    default: "extruders",
  },
  uiContext: {
    type: Object,
    required: true,
  },
  spoolsCount: {
    type: Number,
    default: 0,
  },
  selectedSpoolLabel: {
    type: String,
    default: "",
  },
  webNfcAvailable: {
    type: Boolean,
    default: false,
  },
  secureContextOk: {
    type: Boolean,
    default: false,
  },
  extruderCount: {
    type: Number,
    default: 4,
  },
  mappedExtruders: {
    type: Number,
    default: 0,
  },
});

const emit = defineEmits(["navigate"]);
</script>

<template>
  <aside
    class="app-sidebar bg-body-secondary shadow"
    data-bs-theme="dark"
    data-enable-persistence="true"
    data-sidebar-breakpoint="992"
  >
    <div class="sidebar-brand">
      <a href="#" class="brand-link" @click.prevent="emit('navigate', 'extruders')">
        <span class="brand-image brand-mark shadow-sm">
          <i class="bi bi-disc-fill"></i>
        </span>
        <span class="brand-text fw-light">Spool Tag Writer</span>
      </a>
    </div>

    <div class="sidebar-wrapper">
      <nav class="mt-2">
        <ul
          id="navigation"
          class="nav sidebar-menu flex-column"
          data-lte-toggle="treeview"
          role="navigation"
          aria-label="Main navigation"
          data-accordion="false"
        >
          <li class="nav-header">SCREENS</li>
          <li class="nav-item">
            <a href="#" class="nav-link" :class="{ active: activeScreen === 'extruders' }" @click.prevent="emit('navigate', 'extruders')">
              <i class="nav-icon bi bi-diagram-3"></i>
              <p>
                Extruder Mapping
                <span class="nav-badge badge text-bg-primary me-3">{{ mappedExtruders }}/{{ extruderCount }}</span>
              </p>
            </a>
          </li>
          <li class="nav-item">
            <a href="#" class="nav-link" :class="{ active: activeScreen === 'tag-tools' }" @click.prevent="emit('navigate', 'tag-tools')">
              <i class="nav-icon bi bi-upc-scan"></i>
              <p>
                Tag Tools
                <span class="nav-badge badge text-bg-secondary me-3">{{ spoolsCount }}</span>
              </p>
            </a>
          </li>

          <li class="nav-header">STATION</li>
          <li class="nav-item">
            <a href="#" class="nav-link" @click.prevent="emit('navigate', activeScreen)">
              <i class="nav-icon bi bi-broadcast-pin"></i>
              <p>{{ uiContext.nfc_reader_name || "Reader pending" }}</p>
            </a>
          </li>
          <li class="nav-item">
            <a href="#" class="nav-link" @click.prevent="emit('navigate', activeScreen)">
              <i class="nav-icon bi bi-hdd-stack"></i>
              <p>{{ uiContext.nfc_backend || "unknown" }} backend</p>
            </a>
          </li>
          <li class="nav-item">
            <a href="#" class="nav-link" @click.prevent="emit('navigate', 'tag-tools')">
              <i class="nav-icon bi bi-disc"></i>
              <p>{{ selectedSpoolLabel || "Choose a spool in the writer panel." }}</p>
            </a>
          </li>

          <li class="nav-header">CAPABILITIES</li>
          <li class="nav-item">
            <a href="#" class="nav-link" @click.prevent="emit('navigate', 'tag-tools')">
              <i class="nav-icon bi bi-phone"></i>
              <p>
                Web NFC
                <span class="nav-badge badge me-3" :class="webNfcAvailable ? 'text-bg-success' : 'text-bg-secondary'">
                  {{ webNfcAvailable ? "On" : "Off" }}
                </span>
              </p>
            </a>
          </li>
          <li class="nav-item">
            <a href="#" class="nav-link" @click.prevent="emit('navigate', 'tag-tools')">
              <i class="nav-icon bi bi-shield-lock"></i>
              <p>
                Secure Context
                <span class="nav-badge badge me-3" :class="secureContextOk ? 'text-bg-success' : 'text-bg-warning'">
                  {{ secureContextOk ? "Ready" : "Required" }}
                </span>
              </p>
            </a>
          </li>
        </ul>
      </nav>
    </div>
  </aside>
</template>
