# k3s deployment

This deployment runs `spool-tag-writer` in a home k3s cluster while the printer keeps running Moonraker and Klipper.

The same container image is used for both processes:
- `spool-tag-writer-web` serves FastAPI and the built Vue UI.
- `spool-tag-writer-agent` connects to Moonraker over websocket and performs active spool sync.

Published images support `linux/amd64`, `linux/arm64`, and `linux/arm/v7`. On Raspberry Pi 4/5 k3s nodes, Kubernetes pulls the matching variant automatically from the same image tag.

The agent must run as a single replica. Running multiple agents can race on the same Moonraker active spool state.

No persistent volume is required for the default deployment. Extruder fallback mapping is stored in Moonraker database, and spool metadata remains in Spoolman. If the pod restarts, the app reloads state from those services.

## Configure

Edit [configmap.yaml](configmap.yaml):
- set `MOONRAKER_HTTP_URL`
- set `MOONRAKER_WS_URL`
- set `MOONRAKER_CLIENT_URL`
- keep `LOCAL_NFC_ENABLED=false`
- keep `SPOOLMAN_SSL_VERIFY=true`
- set `SPOOLMAN_CA_BUNDLE=/etc/spool-tag-writer/tls/spoolman-ca.pem` if Spoolman uses a private CA

The published container image does not include `pyscard` or PC/SC packages. It is meant for U1 RFID over Moonraker, not direct USB NFC reader access inside the pod.

Edit [ingress.yaml](ingress.yaml) to match the hostname and ingress class used by your cluster. The default example assumes `spool-tag-writer.example.local`.

If Moonraker or Spoolman requires API keys, create a real secret from [secret.example.yaml](secret.example.yaml):

```bash
cp deploy/k3s/secret.example.yaml /tmp/spool-tag-writer-secret.yaml
vi /tmp/spool-tag-writer-secret.yaml
kubectl apply -f /tmp/spool-tag-writer-secret.yaml
```

If Spoolman uses a certificate signed by an internal CA, create a TLS CA secret from [tls-secret.example.yaml](tls-secret.example.yaml):

```bash
cp deploy/k3s/tls-secret.example.yaml /tmp/spool-tag-writer-tls.yaml
vi /tmp/spool-tag-writer-tls.yaml
kubectl apply -f /tmp/spool-tag-writer-tls.yaml
```

Then set `SPOOLMAN_CA_BUNDLE=/etc/spool-tag-writer/tls/spoolman-ca.pem` in [configmap.yaml](configmap.yaml). Avoid `SPOOLMAN_SSL_VERIFY=false` except for temporary troubleshooting.

## Deploy

With API key or TLS CA secrets, apply only the secret files you actually use:

```bash
kubectl apply -f deploy/k3s/namespace.yaml
kubectl apply -f /tmp/spool-tag-writer-secret.yaml
kubectl apply -f /tmp/spool-tag-writer-tls.yaml
kubectl apply -k deploy/k3s
```

Without secrets:

```bash
kubectl apply -k deploy/k3s
```

## Verify

```bash
kubectl -n spool-tag-writer get pods
kubectl -n spool-tag-writer logs deploy/spool-tag-writer-agent -f
kubectl -n spool-tag-writer port-forward svc/spool-tag-writer-web 8080:80
```

Open:

```text
http://127.0.0.1:8080/
```

The UI should show Moonraker sync state on the `Extruder Mapping` screen.
