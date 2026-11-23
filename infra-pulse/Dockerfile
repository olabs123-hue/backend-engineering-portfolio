# Single-container demo: build React UI, then serve UI and FastAPI on the same origin.
FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
# Relative API paths work because the dashboard is served by FastAPI.
ENV VITE_API_URL=
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 INFRAPULSE_DB=/tmp/infrapulse.sqlite3
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=ui /ui/dist /app/frontend/dist
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["sh","-c","uvicorn backend.serve:app --host 0.0.0.0 --port ${PORT:-8000}"]
