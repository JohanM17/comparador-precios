FROM python:3.12-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir hatchling
COPY pyproject.toml ./
COPY app ./app
RUN python -c "import tomllib, pathlib; \
d = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; \
pathlib.Path('/tmp/reqs.txt').write_text('\n'.join(d))" \
  && pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels . \
  && pip wheel --no-cache-dir --wheel-dir /build/wheels -r /tmp/reqs.txt \
  && rm -f /tmp/reqs.txt

FROM python:3.12-slim AS runtime
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
WORKDIR /app
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY app ./app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; \
p = os.environ.get('PORT', '8000'); \
urllib.request.urlopen(f'http://127.0.0.1:{p}/v1/salud')" || exit 1
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
