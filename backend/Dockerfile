FROM python:3.11-slim

# System deps needed by psycopg (libpq), geoalchemy2/shapely (geos), and
# lightgbm/prophet/ortools build chains.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgeos-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
# Install deps first (without the local package) so this layer caches
# independently of application code changes.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
