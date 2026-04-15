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
git clone https://github.com/<your-org>/<your-repo>.git spool-tag-writer
cd spool-tag-writer
cp examples/u1/.env.u1.example .env
```

Edit `.env`:
- set `SPOOLMAN_URL`
- keep `MOONRAKER_WS_URL=ws://127.0.0.1:7125/websocket`
- keep `NFC_BACKEND=mock` unless you really attach an external PC/SC reader to the printer

## Bootstrap install from Git

If the project is hosted on GitLab and you want the printer to install from a prebuilt package, use the GitLab Generic Package Registry URL produced by CI:

```text
https://gitlab.com/api/v4/projects/<project-id>/packages/generic/spool-tag-writer-u1/<version>/spool-tag-writer-u1-<version>.tar.gz
```

Bootstrap from that package:

```bash
curl -fsSL https://gitlab.com/<namespace>/<project>/-/raw/main/scripts/u1-bootstrap.sh | bash -s -- \
  --package-url https://gitlab.com/api/v4/projects/<project-id>/packages/generic/spool-tag-writer-u1/v1.0.0/spool-tag-writer-u1-v1.0.0.tar.gz \
  --spoolman-url http://spoolman.local:7912
```

For private GitLab projects add a header, for example:

```bash
  --package-header "PRIVATE-TOKEN: <token>"
```

If you prefer to bootstrap directly from Git instead, you can still do:

```bash
curl -fsSL https://gitlab.com/<namespace>/<project>/-/raw/main/scripts/u1-bootstrap.sh | bash -s -- \
  --repo-url https://gitlab.com/<namespace>/<project>.git \
  --ref main \
  --spoolman-url http://spoolman.local:7912
```

GitHub variant:

```bash
curl -fsSL https://raw.githubusercontent.com/<org>/<repo>/main/scripts/u1-bootstrap.sh | bash -s -- \
  --repo-url https://github.com/<org>/<repo>.git \
  --ref main \
  --spoolman-url http://spoolman.local:7912
```

Optional flags:
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
./scripts/u1-update.sh \
  --package-url https://gitlab.com/api/v4/projects/<project-id>/packages/generic/spool-tag-writer-u1/v1.0.0/spool-tag-writer-u1-v1.0.0.tar.gz
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

## GitLab CI package flow

The repository contains `.gitlab-ci.yml` that:
- builds the frontend in CI
- assembles a U1 deployment tarball with the built `app/static/dist`
- publishes the tarball and its `.sha256` to GitLab Generic Package Registry on tags and on the default branch

Package version format:
- tag pipelines: `<tag>`
- default branch pipelines: `<branch-slug>-<short-sha>`

## Release discipline for U1 deployments

The printer may not have `npm`. For that reason the branch or tag deployed to the printer should contain a ready-to-serve frontend build in:

```text
app/static/dist
```

If you deploy straight from GitHub to the printer, treat `app/static/dist` as a release artifact and push it together with the backend changes for the branch/tag used on U1.

## After a firmware upgrade

Firmware upgrades keep `/home/lava/printer_data`, but remove persisted system changes and clear `/oem/.debug`.

Run this again after the upgrade:

```bash
ssh root@<printer-ip>
touch /oem/.debug
cd /home/lava/printer_data/apps/spool-tag-writer
./scripts/u1-install.sh --install-services
```
