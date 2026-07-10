# syntax=docker/dockerfile:1
# Production image for tuck-it on Cloud Run.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# No system build deps needed: all requirements ship manylinux wheels
# (Django, whitenoise, gunicorn, nh3, httpx, ...). Add a builder stage only
# if a future dependency needs compiling.

# Install Python deps first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# App code.
COPY . .

# Bake static assets into the image. WhiteNoise's manifest storage (used when
# DEBUG=0) requires a collectstatic manifest to exist. collectstatic loads
# settings — which hard-require DATABASE_URL / SECRET_KEY / ALLOWED_HOSTS — but
# never touches the database, so throwaway build-time values are safe and are
# NOT used at runtime (Cloud Run injects the real env).
RUN DJANGO_DEBUG=0 \
    DJANGO_SECRET_KEY=build-time-placeholder-not-used-at-runtime \
    DJANGO_ALLOWED_HOSTS=localhost \
    DATABASE_URL=sqlite:///build-noop.sqlite3 \
    python manage.py collectstatic --noinput

# Run as an unprivileged user.
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

# Cloud Run routes traffic to $PORT (8080 by default) and sends SIGTERM on
# shutdown. Shell form + `exec` makes gunicorn PID 1 so it receives SIGTERM and
# drains in-flight requests gracefully (zero-downtime rollouts).
#
# NOTE: database migrations are NOT run here — they run as a separate deploy
# step (a Cloud Run Job / CI step) so scaled instances don't race, per the
# expand/contract migration discipline in docs/cloud-deployment-spec.md §5.
ENV PORT=8080
# JSON/exec form (satisfies the linter); the inner `exec` makes gunicorn PID 1
# so it receives SIGTERM directly, while `sh -c` expands $PORT.
CMD ["sh", "-c", "exec gunicorn tuckit.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60 --graceful-timeout 30 --access-logfile - --error-logfile -"]
