# spool-tag-writer

`spool-tag-writer` is a small web app for working with filament spools, NFC spool tags, and `Spoolman` from a browser UI. It is designed to run directly on a printer such as `Snapmaker U1` with `SnapmakerU1-Extended-Firmware`, while talking to local `Moonraker` and a remote or local NFC reader.

The application provides:
- spool selection and extruder-to-spool mapping
- OpenSpool tag preview, write, and readback tools
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

## Notes

- `Moonraker` should typically stay on `ws://127.0.0.1:7125/websocket`.
- `Spoolman` can run on the printer or elsewhere on the network.
- `SPOOLMAN_URL=auto` tells the app to resolve the URL from Moonraker `[spoolman]`.
- The NFC reader can be local to the printer or moved to another machine via a dedicated bridge service.
- `GitHub Actions` builds the frontend on pushes and pull requests; tag builds also publish the packaged U1 release assets.

For detailed printer deployment notes, see [examples/u1/README.md](examples/u1/README.md).
