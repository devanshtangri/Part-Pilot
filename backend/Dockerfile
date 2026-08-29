FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS frontend-builder

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
COPY backend/requirements.lock.txt /app/backend/requirements.lock.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.lock.txt

COPY backend /app/backend
COPY --from=frontend-builder /frontend/dist /app/frontend_dist
COPY THIRD_PARTY_NOTICES.md /app/third_party/THIRD_PARTY_NOTICES.md
COPY third_party/licenses /app/third_party/licenses
COPY third_party/debian-source-packages.txt /app/third_party/debian-source-packages.txt
COPY third_party/debian-source-files.tsv /app/third_party/debian-source-files.tsv

WORKDIR /app/backend

# Part Pilot listens on fixed container port 8000; Docker chooses the host-side mapping.
EXPOSE 8000

# PARTPILOT:CONTAINER_STARTUP_BOOTSTRAP:V812
# PARTPILOT:EXPLICIT_PROXY_BOUNDARY:V506
CMD ["sh", "-c", "python -m app.restore_bootstrap && python -m app.db.startup_bootstrap && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers"]
