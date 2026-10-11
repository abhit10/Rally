FROM node:22-bookworm-slim AS dashboard
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements*.txt backend/
RUN pip install --no-cache-dir -r backend/requirements-vision.txt
COPY backend/ backend/
COPY --from=dashboard /ui/dist frontend/dist
ENV PYTHONPATH=/app/backend RACKET_DATA=/app/data RACKET_WEIGHTS=/app/weights
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
