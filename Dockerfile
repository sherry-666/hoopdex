# One image for the web app: builds the React frontend, then serves it and the API
# from FastAPI. Railway sets PORT and DATABASE_URL.

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BALLSTATS_WEB_DIST=/app/web/dist
COPY pyproject.toml README.md ./
COPY ballstats ./ballstats
RUN pip install --no-cache-dir .
COPY --from=web /web/dist ./web/dist
EXPOSE 8000
CMD ["sh", "-c", "uvicorn ballstats.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
