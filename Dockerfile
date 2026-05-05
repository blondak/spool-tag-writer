FROM node:22-bookworm-slim AS frontend

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY frontend ./frontend
COPY vite.config.js ./
RUN npm run build

FROM python:3.12-slim-bookworm AS pydeps

WORKDIR /app

COPY requirements-container.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements-container.txt

FROM python:3.12-slim-bookworm AS runtime

ENV APP_HOST=0.0.0.0 \
    APP_PORT=8080 \
    LOCAL_NFC_ENABLED=false \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=pydeps /opt/venv /opt/venv
COPY app ./app
COPY scripts ./scripts
COPY --from=frontend /app/app/static/dist ./app/static/dist

RUN useradd --system --create-home --home-dir /home/app spooltag \
    && chown -R spooltag:spooltag /app

USER spooltag

EXPOSE 8080

CMD ["scripts/run.sh", "web"]
