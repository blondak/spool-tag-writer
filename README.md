# spool-tag-writer

`spool-tag-writer` is a small web app for working with filament spools, NFC spool tags, and `Spoolman` from a browser UI. It is designed to run directly on a printer such as `Snapmaker U1` with `SnapmakerU1-Extended-Firmware`, while talking to local `Moonraker` and a remote or local NFC reader.

The application provides:
- spool selection and extruder-to-spool mapping
- OpenSpool tag preview, with optional local NFC write/readback tools
- Prusament import helpers
- a Moonraker-side agent for printer integration

## Install on Snapmaker U1

The recommended install target is the printer itself. The simplest production workflow is to install from a prebuilt GitHub release package, so the frontend build does not happen on the printer.

### 1. Enable SSH

On the printer:
- `Settings > Maintenance > Root Access > Open`

Then connect:

```bash
ssh root@<printer-ip>
touch /oem/.debug
```

### 2. Run the bootstrap installer

From the printer shell, install from a GitHub release asset:

```bash
curl -fsSL https://raw.githubusercontent.com/blondak/spool-tag-writer/main/scripts/u1-bootstrap.sh | bash -s -- \
  --github-release <version> \
```

Equivalent explicit package URL:

```text
https://github.com/blondak/spool-tag-writer/releases/download/<version>/spool-tag-writer-u1-<version>.tar.gz
```

The installer:
- downloads the packaged release
- creates the Python virtualenv
- installs dependencies
- installs the web and agent init scripts
- prepares the app for startup on the printer
- auto-detects `SPOOLMAN_URL` from Moonraker `[spoolman] server` when available

After a future firmware upgrade, recover the app with:

```bash
ssh root@<printer-ip> 'cd /home/lava/printer_data/apps/spool-tag-writer && ./scripts/u1-recover.sh'
```

### 3. Open the UI

By default the UI is available at:

```text
http://<printer-ip>:18080/
```

Logs are stored in:

```text
/home/lava/printer_data/system/spool-tag-writer/
```

## Update on the printer

To update an existing install to a newer packaged release:

```bash
cd /home/lava/printer_data/apps/spool-tag-writer
./scripts/u1-update.sh --github-release <version>
```

## Run in k3s

The app can also run in a home k3s cluster. The recommended k3s mode is:
- `LOCAL_NFC_ENABLED=false`
- web and agent as separate deployments
- exactly one agent replica
- Moonraker and Spoolman reached over the LAN

Container images are published to:

```text
ghcr.io/blondak/spool-tag-writer
```

Images are published as a multi-arch manifest for `linux/amd64`, `linux/arm64`, and `linux/arm/v7`, so Raspberry Pi 4/5 nodes can pull the same tag on 64-bit or 32-bit Raspberry Pi OS.

Example manifests are in [deploy/k3s](deploy/k3s).

The published container image intentionally excludes `pyscard` and PC/SC packages, so direct USB NFC reader access is disabled in the cluster image. Use U1 RFID over Moonraker, or run a separate reader-side bridge if a physical NFC reader must stay on another host.

The default k3s deployment does not need a persistent volume: fallback mapping is stored in Moonraker database and spool data stays in Spoolman.

## Klipper macro

Example Klipper macros are in [examples/printer_macro_spool_tag_writer.cfg](examples/printer_macro_spool_tag_writer.cfg).

The file includes:
- `WRITE_SPOOL_TAG` for writing the active or selected spool to NFC
- `SHOW_FALLBACK_MAPPING` for printing the current fallback extruder mapping into the Klipper console

`SHOW_FALLBACK_MAPPING` requires Klipper `[respond]` to be enabled.

## Notes

- `Moonraker` should typically stay on `ws://127.0.0.1:7125/websocket`.
- `Spoolman` can run on the printer or elsewhere on the network.
- `SPOOLMAN_URL=auto` tells the app to resolve the URL from Moonraker `[spoolman]`.
- For Spoolman behind custom TLS, keep `SPOOLMAN_SSL_VERIFY=true` and set `SPOOLMAN_CA_BUNDLE=/path/to/internal-ca.pem`.
- `LOCAL_NFC_ENABLED=false` hides and disables local NFC reader write/read flows.
- The default container image is intended for U1 RFID/Moonraker operation and does not include local PC/SC NFC dependencies.
- `GitHub Actions` builds the frontend on pushes and pull requests; tag builds also publish the packaged U1 release assets.

For detailed printer deployment notes, see [examples/u1/README.md](examples/u1/README.md).
