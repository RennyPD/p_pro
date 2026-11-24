# Nexo API (Fase 4 C). The same image runs three roles:
#   api      (default command)  uvicorn with several worker processes
#   migrate  alembic upgrade head, once per release, with the owner role
#   worker   python -m scripts.scheduler (emails, billing, reminders)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WEB_CONCURRENCY=2 \
    STORAGE_DIR=/data/storage

WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install -r requirements.lock

COPY alembic.ini main.py ./
COPY alembic/ ./alembic/
COPY app/ ./app/
COPY scripts/ ./scripts/

# Never run as root; local file storage (when not using S3) lives in /data.
RUN useradd --system --uid 10001 --home-dir /app nexo \
    && mkdir -p /data/storage \
    && chown -R nexo:nexo /data
USER nexo

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=4).status == 200 else 1)"

# Migrations are a separate step (service "migrate"), never at start-up:
# several replicas starting at once must not run them concurrently.
# FORWARDED_ALLOW_IPS: the address of your proxy/load balancer ("*" only if
# the container is unreachable except through it).
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\""]
