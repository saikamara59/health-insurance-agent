# ── Backend ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS backend

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY healthflow/ healthflow/
COPY seed.py .
COPY scripts/ scripts/

# Generate seed data
RUN python scripts/refresh_data.py --seed-only

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "healthflow.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ── Frontend ─────────────────────────────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend

# Install deps
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Build
COPY frontend/ .
RUN npm run build


# ── Frontend Serve ───────────────────────────────────────────────────────────
FROM nginx:alpine AS frontend

# Copy built assets
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html

# Nginx config for SPA routing + API proxy
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80


# ── Combined (single-container deploy: Fly.io demo) ──────────────────────────
# Backend image + built frontend dist served by FastAPI as static files.
# Entrypoint runs the API and seeds the demo broker + clients on first start
# (idempotent). Local dev still uses the `backend` + `frontend` stages via
# docker-compose; this stage is only built for Fly.io.
FROM backend AS combined

# Frontend dist baked in at /app/frontend/dist — main.py picks it up.
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# Demo entrypoint script (idempotent seed on first start).
COPY scripts/demo_entrypoint.sh /app/demo_entrypoint.sh
RUN chmod +x /app/demo_entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/demo_entrypoint.sh"]
