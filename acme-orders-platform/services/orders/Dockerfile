# syntax=docker/dockerfile:1

# ---- builder: install dependencies into an isolated prefix ----
FROM python:3.12.11-slim-bookworm AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime: only what is needed to run ----
FROM python:3.12.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Numeric UID/GID so Kubernetes can verify runAsNonRoot (it cannot resolve names).
RUN groupadd --system --gid 10001 app \
 && useradd  --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /install /usr/local
COPY app.py gunicorn.conf.py ./

USER 10001:10001
EXPOSE 8000

# Exec form: gunicorn is PID 1 and receives SIGTERM directly.
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
