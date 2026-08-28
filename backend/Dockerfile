FROM node:22-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY --from=frontend-builder /frontend/dist /app/frontend_dist

WORKDIR /app/backend

# Part Pilot listens on fixed container port 8000; Docker chooses the host-side mapping.
EXPOSE 8000

# PARTPILOT:CONTAINER_STARTUP_BOOTSTRAP:V812
# PARTPILOT:EXPLICIT_PROXY_BOUNDARY:V506
CMD ["sh", "-c", "python -m app.restore_bootstrap && python -m app.db.startup_bootstrap && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers"]
