# Snapmaker U1 Deployment

This deployment targets the `SnapmakerU1-Extended-Firmware` by `paxx12`.

Recommended layout on the printer:

```text
/home/lava/printer_data/apps/spool-tag-writer
```

Why this location:
- `/home/lava/printer_data` always persists across reboots.
- System-level changes in `/etc` only persist when `/oem/.debug` is enabled.
- Firmware upgrades clear persisted system changes and remove `/oem/.debug`, so init scripts must be reinstalled after an upgrade.

## 1. Enable SSH and persistence

On current custom firmware builds you can enable SSH from the printer UI:
- `Settings > Maintenance > Root Access > Open`

If you want the init scripts in `/etc/init.d` to survive reboots:

```bash
ssh root@<printer-ip>
touch /oem/.debug
```

## 2. Clone the app

```bash
ssh root@<printer-ip>
mkdir -p /home/lava/printer_data/apps
cd /home/lava/printer_data/apps
git clone https://github.com/blondak/spool-tag-writer.git spool-tag-writer
cd spool-tag-writer
cp examples/u1/.env.u1.example .env
```

Edit `.env`:
- keep `SPOOLMAN_URL=auto` to discover the URL from Moonraker `[spoolman]`
- keep `MOONRAKER_WS_URL=ws://127.0.0.1:7125/websocket`
- keep `LOCAL_NFC_ENABLED=false` unless you really want local NFC tag write/read tools in the UI
- keep `NFC_BACKEND=mock` unless you really attach an external PC/SC reader to the printer

## Bootstrap install

The recommended path is a prebuilt GitHub release asset, so the printer does not need to build the frontend:

```text
https://github.com/blondak/spool-tag-writer/releases/download/<version>/spool-tag-writer-u1-<version>.tar.gz
```

Bootstrap from that package:

```bash
curl -fsSL https://raw.githubusercontent.com/blondak/spool-tag-writer/main/scripts/u1-bootstrap.sh | bash -s -- \
  --github-release <version>
```

Equivalent explicit package URL:

```text
https://github.com/blondak/spool-tag-writer/releases/download/<version>/spool-tag-writer-u1-<version>.tar.gz
```

If you prefer to bootstrap directly from Git instead, you can still do:

```bash
curl -fsSL https://raw.githubusercontent.com/blondak/spool-tag-writer/main/scripts/u1-bootstrap.sh | bash -s -- \
  --repo-url https://github.com/blondak/spool-tag-writer.git \
  --ref main
```

Optional flags:
- `--spoolman-url http://spoolman.local:7912` to override Moonraker discovery
- `--app-port 18080`
- `--app-dir /home/lava/printer_data/apps/spool-tag-writer`
- `--force-env-update`

## 3. First install

```bash
cd /home/lava/printer_data/apps/spool-tag-writer
chmod +x scripts/u1-install.sh scripts/u1-update.sh
./scripts/u1-install.sh --install-services
```

This script:
- creates `.venv`
- installs Python dependencies
- builds the frontend when `npm` is available
- otherwise uses the prebuilt `app/static/dist` from the repository
- installs:
  - `/etc/init.d/S99spool-tag-writer-web`
  - `/etc/init.d/S99spool-tag-writer-agent`

## 4. Start and verify

```bash
/etc/init.d/S99spool-tag-writer-web status
/etc/init.d/S99spool-tag-writer-agent status
```

Open:

```text
http://<printer-ip>:18080/
```

Logs:

```text
/home/lava/printer_data/system/spool-tag-writer/web.log
/home/lava/printer_data/system/spool-tag-writer/agent.log
```

## Klipper macro integration

Example macros are provided in [../printer_macro_spool_tag_writer.cfg](../printer_macro_spool_tag_writer.cfg).

The file includes:
- `WRITE_SPOOL_TAG`
- `SHOW_FALLBACK_MAPPING`

`WRITE_SPOOL_TAG` requires `LOCAL_NFC_ENABLED=true` and a configured local or bridged NFC reader.

`SHOW_FALLBACK_MAPPING` calls the Moonraker agent and prints the current fallback mapping into the Klipper console, for example:

```text
Spool Tag Writer fallback mapping:
T0 (extruder) -> spool #29
T1 (extruder1) -> spool #26
T2 (extruder2) -> unassigned
T3 (extruder3) -> unassigned
```

Enable Klipper `[respond]` before using that macro, otherwise the console output will not be visible.

## 5. Update process from GitHub

Update the deployed checkout in place:

```bash
cd /home/lava/printer_data/apps/spool-tag-writer
./scripts/u1-update.sh
```

Update to a specific tag or branch:

```bash
cd /home/lava/printer_data/apps/spool-tag-writer
./scripts/u1-update.sh v0.2.0
```

Package-based update without building on the printer:

```bash
cd /home/lava/printer_data/apps/spool-tag-writer
./scripts/u1-update.sh --github-release <version>
```

The update script:
- fetches from `origin`
- checks out an optional target ref
- runs `git pull --ff-only`
- reinstalls Python dependencies
- rebuilds the frontend if `npm` exists
- otherwise reuses the committed `app/static/dist`
- compiles Python modules
- restarts both init services if they are installed

## GitHub Actions package flow

The repository contains `.github/workflows/u1-package.yml` that:
- builds the frontend in CI
- assembles a U1 deployment tarball with the built `app/static/dist`
- uploads the package as a workflow artifact on pushes and pull requests
- publishes the tarball and its `.sha256` as GitHub release assets on tags

Package version format:
- tag pipelines: `<tag>`
- default branch pipelines: `<branch-slug>-<short-sha>`

## Release discipline for U1 deployments

The printer may not have `npm`. For that reason the branch or tag deployed to the printer should contain a ready-to-serve frontend build in:

```text
app/static/dist
```

If you deploy straight from Git to the printer, either build the frontend on the target or use a branch/tag that already contains a ready-to-serve `app/static/dist`.

## After a firmware upgrade

Firmware upgrades keep `/home/lava/printer_data`, but remove persisted system changes and clear `/oem/.debug`.

Recover the app after the upgrade with one command:

```bash
ssh root@<printer-ip> 'cd /home/lava/printer_data/apps/spool-tag-writer && ./scripts/u1-recover.sh'
```
