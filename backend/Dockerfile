FROM python:3.12-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir hatchling
COPY pyproject.toml ./
COPY app ./app
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels .
RUN pip wheel --no-cache-dir --wheel-dir /build/wheels -r \
  <(python -c "import tomllib; p=tomllib.load(open('pyproject.toml','rb')); print('\n'.join(p['project']['dependencies']))")

FROM python:3.12-slim AS runtime
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
WORKDIR /app
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY app ./app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/salud')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
