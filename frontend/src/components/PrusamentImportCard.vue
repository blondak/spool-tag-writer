<script setup>
import { computed, ref } from "vue";
import { QrcodeStream } from "vue-qrcode-reader";
import CardHelpTooltip from "./CardHelpTooltip.vue";

const props = defineProps({
  status: {
    type: String,
    default: "",
  },
  statusTone: {
    type: String,
    default: "secondary",
  },
  matchMessage: {
    type: String,
    default: "",
  },
  matchTone: {
    type: String,
    default: "secondary",
  },
  result: {
    type: Object,
    default: null,
  },
  busyLoad: {
    type: Boolean,
    default: false,
  },
  busyCreateFilament: {
    type: Boolean,
    default: false,
  },
  busyCreateSpool: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["load-url", "create-filament", "create-spool"]);

const QR_FORMATS = ["qr_code"];

const url = ref("");
const scanActive = ref(false);
const localStatus = ref("");
const localTone = ref("secondary");
const localhostHosts = new Set(["localhost", "127.0.0.1", "::1"]);
const secureContextOk =
  typeof window !== "undefined" &&
  (window.isSecureContext || localhostHosts.has(window.location.hostname));
const hasCameraApi = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
const isFirefox =
  typeof navigator !== "undefined" && /firefox/i.test(navigator.userAgent || "");
const scannerConstraints = {
  facingMode: { ideal: "environment" },
};

const toneClass = (tone) => {
  const normalized = tone === "secondary" ? "info" : tone || "info";
  return `callout callout-${normalized}`;
};

const prettyResult = computed(() => (props.result ? JSON.stringify(props.result, null, 2) : ""));
const prettyOverrides = computed(() => {
  if (!props.result) {
    return "";
  }

  return JSON.stringify(
    {
      type: props.result.type || "",
      brand: props.result.brand || "",
      subtype: props.result.subtype || "",
      min_temp: props.result.min_temp || "",
      max_temp: props.result.max_temp || "",
      bed_min_temp: props.result.bed_min_temp || "",
      bed_max_temp: props.result.bed_max_temp || "",
      color_hex: props.result.color_hex || "",
    },
    null,
    2,
  );
});

const effectiveStatus = computed(() => localStatus.value || props.status);
const effectiveTone = computed(() => (localStatus.value ? localTone.value : props.statusTone));

const stopScan = () => {
  scanActive.value = false;
};

const getCameraPermissionMessage = async () => {
  const genericMessage = isFirefox
    ? "Firefox denied camera access. Even with site permission allowed, the operating system or another application may still be blocking the camera."
    : "Camera access was denied. The browser may already have camera access blocked for this site.";

  if (typeof navigator === "undefined" || !navigator.permissions?.query) {
    return `${genericMessage} Check browser site permissions, OS camera privacy settings, and whether another app is using the camera.`;
  }

  try {
    const permissionStatus = await navigator.permissions.query({ name: "camera" });

    if (permissionStatus.state === "denied") {
      return "Camera access is already blocked for this site in the browser, so no prompt was shown. Allow the camera in site settings and try again.";
    }

    if (permissionStatus.state === "prompt") {
      return "The browser blocked the camera request before showing a prompt. Check site permissions, browser privacy settings, or whether another policy is blocking camera access.";
    }

    if (permissionStatus.state === "granted") {
      return "Site permission is allowed, but Firefox or the operating system is still denying camera access. Check OS camera privacy settings, whether another app is using the camera, and then restart Firefox.";
    }
  } catch {
    return `${genericMessage} Check browser site permissions, OS camera privacy settings, and whether another app is using the camera.`;
  }

  return isFirefox
    ? "Firefox denied camera access even though the site may be allowed. Check Firefox camera permissions, OS privacy settings, and whether another app is using the camera."
    : "Camera access was denied by the browser. Check site permissions and try again.";
};

const describeScannerError = async (error) => {
  switch (error?.name) {
    case "InsecureContextError":
      return "Camera access requires HTTPS or localhost.";
    case "StreamApiNotSupportedError":
      return "This browser does not expose the camera API.";
    case "NotSupportedError":
      return "The QR polyfill could not start. Verify that the local ZXing assets are available.";
    case "NotAllowedError":
    case "SecurityError":
      return await getCameraPermissionMessage();
    case "NotFoundError":
    case "DevicesNotFoundError":
      return "No camera device is available for QR scanning.";
    case "NotReadableError":
    case "TrackStartError":
      return "The camera is busy or could not be started.";
    case "OverconstrainedError":
    case "ConstraintNotSatisfiedError":
      return "The browser could not open a suitable camera for QR scanning.";
    case "StreamLoadTimeoutError":
      return "The camera took too long to start.";
    default:
      return error?.message || "QR scanning failed.";
  }
};

const startScan = () => {
  if (!secureContextOk) {
    localStatus.value = "Camera access requires HTTPS or localhost.";
    localTone.value = "warning";
    return;
  }

  if (!hasCameraApi) {
    localStatus.value = "This browser does not expose the camera API.";
    localTone.value = "danger";
    return;
  }

  localStatus.value = "Starting camera. Hold the Prusament QR in frame.";
  localTone.value = "warning";
  scanActive.value = true;
};

const handleDetect = (detectedCodes) => {
  const scannedUrl = String(detectedCodes?.[0]?.rawValue || "").trim();

  if (!scannedUrl) {
    return;
  }

  url.value = scannedUrl;
  localStatus.value = "";
  stopScan();
  emit("load-url", scannedUrl);
};

const handleCameraOn = () => {
  localStatus.value = "Camera started. Hold the Prusament QR in frame.";
  localTone.value = "warning";
};

const handleScannerError = async (error) => {
  localStatus.value = await describeScannerError(error);
  localTone.value = "danger";
  stopScan();
};
</script>

<template>
  <div id="prusament-panel" class="card card-outline card-warning h-100">
    <div class="card-header">
      <h3 class="card-title">
        <i class="bi bi-qr-code-scan me-2"></i>
        Prusament Import
      </h3>
      <div class="card-tools">
        <CardHelpTooltip
          label="Prusament import help"
          html="<strong>QR + URL Workflow</strong><br>Load a <code>prusa.io/s/...</code> URL, scan a QR code, or create the missing Spoolman records directly from the dashboard."
        />
        <button type="button" class="btn btn-tool" data-lte-toggle="card-collapse" aria-label="Collapse card">
          <i data-lte-icon="expand" class="bi bi-plus-lg"></i>
          <i data-lte-icon="collapse" class="bi bi-dash-lg"></i>
        </button>
      </div>
    </div>

    <div class="card-body">
      <div class="row g-3">
        <div class="col-12">
          <label class="form-label" for="prusament-url">Prusament URL</label>
          <input
            id="prusament-url"
            v-model="url"
            class="form-control"
            placeholder="https://prusa.io/s/..."
          />
        </div>
      </div>

      <div class="d-flex flex-wrap gap-2 mt-4">
        <button type="button" class="btn btn-outline-primary btn-icon" :disabled="!url || busyLoad" @click="emit('load-url', url)">
          <i class="bi bi-cloud-download"></i>
          {{ busyLoad ? "Loading…" : "Load URL" }}
        </button>
        <button type="button" class="btn btn-outline-warning btn-icon" :disabled="scanActive" @click="startScan">
          <i class="bi bi-camera"></i>
          {{ scanActive ? "Camera Running" : "Scan QR" }}
        </button>
        <button type="button" class="btn btn-outline-secondary btn-icon" :disabled="!scanActive" @click="stopScan">
          <i class="bi bi-stop-circle"></i>
          Stop Camera
        </button>
        <button
          type="button"
          class="btn btn-outline-success btn-icon"
          :disabled="!url || busyCreateFilament"
          @click="emit('create-filament', url)"
        >
          <i class="bi bi-bezier2"></i>
          {{ busyCreateFilament ? "Creating…" : "Create Filament" }}
        </button>
        <button
          type="button"
          class="btn btn-success btn-icon"
          :disabled="!url || busyCreateSpool"
          @click="emit('create-spool', url)"
        >
          <i class="bi bi-box-seam"></i>
          {{ busyCreateSpool ? "Creating…" : "Create Spool" }}
        </button>
      </div>

      <div v-if="scanActive" class="mt-4">
        <QrcodeStream
          class="prusament-scanner"
          :paused="!scanActive"
          :constraints="scannerConstraints"
          :formats="QR_FORMATS"
          @camera-on="handleCameraOn"
          @detect="handleDetect"
          @error="handleScannerError"
        />
      </div>

      <div v-if="effectiveStatus" :class="toneClass(effectiveTone)" class="mt-4">
        <p class="mb-0">{{ effectiveStatus }}</p>
      </div>

      <div v-if="matchMessage" :class="toneClass(matchTone)" class="mt-3">
        <p class="mb-0">{{ matchMessage }}</p>
      </div>

      <div v-if="result" class="row g-3 mt-1">
        <div class="col-12 col-xl-6">
          <div class="card card-outline card-light h-100 mb-0">
            <div class="card-header"><h3 class="card-title">Imported Data</h3></div>
            <div class="card-body">
              <pre class="json-block">{{ prettyResult }}</pre>
            </div>
          </div>
        </div>
        <div class="col-12 col-xl-6">
          <div class="card card-outline card-light h-100 mb-0">
            <div class="card-header"><h3 class="card-title">Applied Overrides</h3></div>
            <div class="card-body">
              <pre class="json-block">{{ prettyOverrides }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
