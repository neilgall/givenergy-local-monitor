FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy pyproject.toml and install dependencies
RUN --mount=type=bind,source=pyproject.toml,target=pyproject.toml,readonly \
    --mount=type=bind,source=uv.lock,target=uv.lock,readonly \
    uv sync --frozen

FROM python:3.12-slim AS runtime

WORKDIR /app
COPY --from=builder /app /app

# Copy application
COPY givenergy_exporter.py .

# Expose Prometheus metrics port
EXPOSE 9100

# Run the exporter
CMD [".venv/bin/python3", "givenergy_exporter.py"]
