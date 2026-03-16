# spool-tag-writer

License: MIT

A Python application for:
- loading spools from Spoolman,
- building an OpenSpool JSON payload with `spoolman_id`,
- writing the payload to NTAG215 NFC tags via ACR122U,
- previewing data before writing and reading it back afterward,
- integrating with Moonraker/Fluidd through a remote method.

## Features
- Web UI (`/`) with spool selection:
  - `Preview NFC payload`,
  - `Write to NFC tag`,
  - optional overrides for `type`, `brand`, `subtype`, `min/max temp`, `bed min/max temp`, and `color_hex`,
  - automatic prefill of available values from Spoolman after changing the selected spool.
- Moonraker agent:
  - registers the `spool_tag_writer_write_spool_tag` remote method,
  - accepts `spool_id` or tries to resolve the active spool from Moonraker.
- Prusament import:
  - import spool data from a Prusament QR URL,
  - create filaments and spools in Spoolman,
  - prepare the newly created spool for NFC writing.
- API:
  - `GET /api/spools`
  - `GET /api/spools/{spool_id}`
  - `GET /api/spools/{spool_id}/overrides-defaults`
  - `POST /api/preview?spool_id=123`
  - `POST /api/write?spool_id=123`
  - `POST /api/preview/with-overrides?spool_id=123&type=PLA&min_temp=190&max_temp=220`
  - `POST /api/write/with-overrides?spool_id=123&bed_min_temp=50&bed_max_temp=60`
  - `GET /api/tag/read`
  - `POST /api/import/prusament?url=...`
  - `POST /api/spoolman/filaments/create-from-prusament?url=...`
  - `POST /api/spoolman/spools/create-from-prusament?url=...`

## OpenSpool format
Data is stored as an NDEF MIME record:
- MIME type: `application/json`
- Payload shape:
```json
{
  "protocol": "openspool",
  "version": "1.0",
  "type": "PLA",
  "color_hex": "946344",
  "brand": "Spectrum",
  "min_temp": "190",
  "max_temp": "220",
  "bed_min_temp": "50",
  "bed_max_temp": "60",
  "subtype": "Wood",
  "spoolman_id": "15"
}
```

## Quick start
Automatic installation:
```bash
./scripts/install.sh
```

Manual installation:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
- `APP_HOST`, `APP_PORT` for the web server bind address.
- `SPOOLMAN_URL` for your Spoolman URL.
- `NFC_BACKEND=pcsc` for a real ACR122U reader.
- Use `NFC_BACKEND=mock` for testing without hardware.
- `MOONRAKER_WS_URL` for the Moonraker websocket, usually `ws://127.0.0.1:7125/websocket`.

Run:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Web UI: `http://localhost:8080`

Moonraker agent:
```bash
python -m app.moonraker_agent
```

Simple script-based startup:
```bash
./scripts/run.sh web
./scripts/run.sh agent
./scripts/run.sh both
```

Optional environment variables:
- `APP_HOST`, `APP_PORT` (defaults from `.env`)
- `HOST`, `PORT` (runtime override for `APP_HOST/APP_PORT`)
- `RELOAD=1` to enable `--reload`
- `PYTHON`, `UVICORN` to override executable paths

## Codex session helper
To reconnect to the same Codex session in this project:
- Wrapper: `./scripts/codex`
- Save a specific session ID:
  - `./scripts/codex --set-session 019caa13-8e4b-77d2-8646-ea3d983239ec`
- Start it again (resume saved ID, otherwise fall back to `resume --last`):
  - `./scripts/codex`

If you want to run just `codex` in the current shell, load the alias:
```bash
source ./scripts/codex-alias.sh
```

## Fluidd integration via Moonraker
Fluidd does not provide a simple plugin API for a custom panel without a fork, but this works reliably through a macro:

1. Add the contents of:
   - `examples/printer_macro_spool_tag_writer.cfg`
2. Restart Klipper/Moonraker.
3. Run in Fluidd:
   - `WRITE_SPOOL_TAG` to let the agent try the active Moonraker spool,
   - or `WRITE_SPOOL_TAG SPOOL_ID=123`,
   - or with overrides:
     - `WRITE_SPOOL_TAG SPOOL_ID=123 TYPE=PLA BRAND=Spectrum SUBTYPE=Wood`
     - `WRITE_SPOOL_TAG MIN_TEMP=190 MAX_TEMP=220 BED_MIN_TEMP=50 BED_MAX_TEMP=60 COLOR_HEX=946344`

The macro calls the Moonraker remote method `spool_tag_writer_write_spool_tag`, registered by the agent.

Supported override parameters:
- `TYPE`, `BRAND`, `SUBTYPE`, `MIN_TEMP`, `MAX_TEMP`, `BED_MIN_TEMP`, `BED_MAX_TEMP`, `COLOR_HEX`
- The API variant uses: `type`, `brand`, `subtype`, `min_temp`, `max_temp`, `bed_min_temp`, `bed_max_temp`, `color_hex`

Moonraker HTTP API call without the macro:
```bash
curl -X POST http://127.0.0.1:7125/server/extensions/request \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "spool-tag-writer",
    "method": "spool_tag_writer.write_spool_tag",
    "arguments": {"spool_id": 123}
  }'
```

## Systemd examples
Prepared unit files:
- `examples/systemd/spool-tag-writer-web.service`
- `examples/systemd/spool-tag-writer-agent.service`

## Hardware notes
- ACR122U must be available through PC/SC.
- NTAG215 must be unlocked for writing.
- The application writes NDEF TLV into NTAG215 user memory pages `4..129`.
- Before writing, tag capacity is checked:
  - from the tag CC bytes when available,
  - and against the locally configured page range limit.
