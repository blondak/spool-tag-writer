import "bootstrap/dist/js/bootstrap.bundle.min.js";
import "admin-lte/dist/css/adminlte.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import "./assets/app.css";

import { createApp } from "vue";
import { setZXingModuleOverrides } from "vue-qrcode-reader";
import zxingReaderWasmUrl from "../../node_modules/zxing-wasm/dist/reader/zxing_reader.wasm?url";

import App from "./App.vue";
import { setupAdminLteBridge } from "./utils/adminLteBridge.js";
import { applyStoredTheme } from "./utils/theme.js";

setZXingModuleOverrides({
  locateFile: (path, prefix) => (path.endsWith("zxing_reader.wasm") ? zxingReaderWasmUrl : `${prefix || ""}${path}`),
});

applyStoredTheme();
createApp(App).mount("#app");
setupAdminLteBridge();
