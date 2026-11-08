# Nachschlag im Container: für alle mit compose.yml, mit Vorschaltdienst und Bildholer mit compose.pi.yml.

# --- Oberfläche bauen ---------------------------------------------------------------------------------------------
FROM node:22-slim AS oberflaeche
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/* && \
    git config --global url."https://github.com/".insteadOf "ssh://git@github.com/" && \
    git config --global --add url."https://github.com/".insteadOf "git@github.com:"
WORKDIR /bau
COPY version.json ./
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci --no-audit --no-fund
COPY frontend ./frontend
RUN cd frontend && npm run build

# --- Backend ------------------------------------------------------------------------------------------------------
FROM python:3.12-slim
LABEL org.opencontainers.image.title="Nachschlag" \
      org.opencontainers.image.source="https://github.com/HalloWelt42/nachschlag" \
      org.opencontainers.image.licenses="LicenseRef-Nachschlag-NC-1.0"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 NACHSCHLAG_DATEN=/app/daten HOME=/tmp
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
# Satz der Bücher als PDF (WIKI-45): Pango und HarfBuzz für WeasyPrint, Schriften mit und ohne Serifen (arm64 wie amd64)
RUN apt-get update && apt-get install -y --no-install-recommends git libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
        fonts-liberation2 fonts-dejavu-core && \
    pip install --no-cache-dir -r backend/requirements.txt && \
    apt-get purge -y git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
COPY version.json ./
COPY backend ./backend
COPY --from=oberflaeche /bau/frontend/dist ./frontend/dist
WORKDIR /app/backend
# Köpfe eines Vorschaltdienstes (Adresse des Aufrufers, HTTPS) gelten nur von dort, wo FORWARDED_ALLOW_IPS es sagt:
# ohne Vorschaltdienst von niemandem (sonst gäbe sich jeder als ein anderer Rechner aus); compose.pi.yml, wo Caddy davor
# steht und die App von außen nicht erreichbar ist, setzt "*"
ENV FORWARDED_ALLOW_IPS=127.0.0.1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning", "--proxy-headers"]
