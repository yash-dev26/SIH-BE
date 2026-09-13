# FreightIQ — Complete Setup & Run Guide

> **Scope:** Phase 1 project scaffolding/data modeling + Phase 2 ingestion and feature pipeline handoff.
>
> This README consolidates the setup, database initialization, reference/synthetic data seeding, Phase 2 task execution, and acceptance checks documented in the Phase 1 README and Phase 2 handoff notes.

---

## 1. Project Overview

FreightIQ is currently organized in phases. The Phase 1 stack provides a running local environment with:

- FastAPI API skeleton
- PostgreSQL/TimescaleDB
- Redis
- Celery worker infrastructure
- SQLAlchemy ORM models
- Alembic migrations
- Reference-data seed files
- Synthetic historical data generation

Phase 2 adds:

- Data ingestion connectors
- Synthetic fallback ingestion
- Data validation
- Data-quality logging
- Feature snapshots
- Feature-engineering pipelines
- Celery Beat ingestion scheduling
- The `get_training_panel()` contract handed to Phase 3

Phase 3 model training/inference is **not part of the current implementation described by these source documents**.

---

## 2. Repository Structure

The documented repository structure is:

```text
freightiq/
├── docker-compose.yml        # postgres+timescaledb, redis, api, worker
├── .env.example
└── backend/
    ├── pyproject.toml
    ├── Dockerfile
    ├── alembic/               # migration environment
    │   └── versions/
    │       ├── 0001_init_schema.py
    │       └── 0002_phase2_data_quality_and_feature_snapshots.py
    ├── app/
    │   ├── config.py          # Pydantic Settings, env-driven
    │   ├── celery_app.py      # Celery app instance
    │   ├── db/
    │   │   ├── models.py      # SQLAlchemy ORM models
    │   │   └── session.py
    │   ├── schemas/
    │   │   ├── port.py
    │   │   ├── vessel.py
    │   │   ├── contract.py
    │   │   ├── forecast.py
    │   │   └── recommendation.py
    │   ├── ingestion/
    │   │   ├── exceptions.py
    │   │   ├── models.py
    │   │   ├── lookups.py
    │   │   ├── synthetic.py
    │   │   ├── base_connector.py
    │   │   ├── connectors/
    │   │   │   ├── bdi_proxy_connector.py
    │   │   │   ├── bunker_price_connector.py
    │   │   │   ├── commodity_price_connector.py
    │   │   │   ├── ais_connector.py
    │   │   │   ├── port_congestion_connector.py
    │   │   │   └── tide_connector.py
    │   │   ├── validation/
    │   │   │   └── expectations.py
    │   │   └── tasks.py
    │   ├── features/
    │   │   ├── models.py
    │   │   ├── feature_store.py
    │   │   └── pipelines/
    │   │       ├── lag_features.py
    │   │       ├── seasonality_features.py
    │   │       ├── macro_features.py
    │   │       └── build_training_panel.py
    │   └── main.py            # FastAPI app, /health, /health/db
    ├── scripts/
    │   ├── seed_reference_data.py
    │   ├── synthetic_data_generator.py
    │   └── seed_synthetic_data.py
    └── seed_data/
        ├── vessel_classes.yaml
        ├── commodities.yaml
        ├── ports.yaml
        └── trade_lanes.yaml
```

---

## 3. Prerequisites

The documented local stack is Docker-based and consists of:

- PostgreSQL/TimescaleDB
- Redis
- FastAPI API
- Celery worker

The repository also expects the Python project/dependencies defined in `backend/pyproject.toml`.

Phase 2 additionally requires:

```text
numpy
geoalchemy2
```

`numpy` is used by the synthetic random-walk/seasonal generators, and `geoalchemy2` provides `WKTElement` for writing `ais_positions.location`. `geoalchemy2` may already be present transitively through the PostGIS/`Port.location` setup, so check before adding a duplicate pin.

---

## 4. Environment Configuration

From the repository root:

```bash
cp .env.example .env
```

Then configure `.env` according to the settings expected by `app/config.py`.

Phase 2 connector code assumes settings corresponding to:

```text
trading_economics_api_key
eia_api_key
aishub_api_key
marinetraffic_api_key
incois_api_key
use_synthetic_data
```

The exact environment-variable names and aliases are determined by the project's `Settings` implementation.

### Synthetic mode

The current Phase 2 implementation is designed to exercise the **synthetic fallback path** end-to-end.

Real source fetch/scraping methods are intentionally stubbed at this stage, so API keys alone do not make those connectors live.

---

## 5. Start the Local Stack

From the repository root:

```bash
docker compose up -d
```

This starts the documented local services:

- PostgreSQL/TimescaleDB
- Redis
- API
- Celery worker

Check the API/database health endpoint:

```bash
curl localhost:8000/health/db
```

The FastAPI application exposes `/health` and `/health/db`.

---

## 6. Initialize the Database

Run the Alembic migrations from inside the API container:

```bash
docker compose exec api alembic upgrade head
```

This applies the Phase 1 schema and the Phase 2 migration.

### Phase 2 migration

Phase 2 adds:

```text
data_quality_log
feature_snapshots
```

The Phase 2 migration is:

```text
backend/alembic/versions/0002_phase2_data_quality_and_feature_snapshots.py
```

Its `down_revision` is expected to point to:

```text
0001_init_schema
```

If the Phase 1 migration in the actual repository uses a different revision ID, the Phase 2 migration must use that actual revision ID.

---

## 7. Seed Reference Data

After migrations:

```bash
docker compose exec api python scripts/seed_reference_data.py
```

The reference seed files are:

```text
backend/seed_data/
├── vessel_classes.yaml
├── commodities.yaml
├── ports.yaml
└── trade_lanes.yaml
```

This establishes the reference entities required by the rest of the system.

---

## 8. Seed Synthetic Historical Data

Seed five years of synthetic historical data:

```bash
docker compose exec api python scripts/seed_synthetic_data.py --years-of-history 5
```

Synthetic time-series rows are explicitly marked:

```text
data_provenance='synthetic'
```

so they are not presented with the same confidence as live data.

The documented Phase 1 acceptance state expects populated data for:

- `vessel_classes`
- `ports`
- `trade_lanes`
- `commodities`
- the five time-series tables
- `vessels`
- `ais_positions`
- `charter_contracts`
- `voyage_simulations`

Three output-oriented tables are intentionally empty at this stage:

- `model_registry`
- `forecasts`
- `recommendations`

Those are outputs of later phases and are not supposed to be populated with invented records.

---

## 9. Phase 2 Celery Configuration

Phase 2 requires one change to `backend/app/celery_app.py`.

If the Celery application currently has:

```python
include=[]
```

change it to:

```python
celery_app = Celery(
    "freightiq",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.ingestion.tasks"],
)
```

The purpose is to make the worker discover the ingestion tasks.

Nothing else in `celery_app.py` needs to change according to the Phase 2 notes.

`app/ingestion/tasks.py` registers its Beat schedule using:

```python
celery_app.conf.beat_schedule.update(...)
```

at import time, so the schedule becomes active once the module is included.

---

## 10. Phase 2 Ingestion Components

Phase 2 introduces the following ingestion components:

```text
backend/app/ingestion/
├── exceptions.py
├── models.py
├── lookups.py
├── synthetic.py
├── base_connector.py
├── connectors/
│   ├── bdi_proxy_connector.py
│   ├── bunker_price_connector.py
│   ├── commodity_price_connector.py
│   ├── ais_connector.py
│   ├── port_congestion_connector.py
│   └── tide_connector.py
├── validation/
│   └── expectations.py
└── tasks.py
```

Their documented roles are:

- `exceptions.py` — source/validation exceptions
- `models.py` — `data_quality_log`
- `lookups.py` — cached foreign-key lookups
- `synthetic.py` — synthetic fallback tier
- `base_connector.py` — connector orchestration
- `connectors/` — individual data-source connectors
- `validation/expectations.py` — Pandera schemas
- `tasks.py` — Celery tasks and Beat schedule registration

---

## 11. Phase 2 Feature Pipeline

Phase 2 also introduces:

```text
backend/app/features/
├── models.py
├── feature_store.py
└── pipelines/
    ├── lag_features.py
    ├── seasonality_features.py
    ├── macro_features.py
    └── build_training_panel.py
```

The key Phase 2 → Phase 3 interface is:

```python
get_training_panel()
```

from:

```text
app.features.pipelines.build_training_panel
```

This produces the training panel that Phase 3 can consume.

---

## 12. Run the Phase 2 Acceptance Check

There are two documented ways to exercise Phase 2.

### Option A — synchronous, no broker required

From the backend environment:

```bash
python -c "
from app.ingestion.tasks import run_all
print(run_all.run())
"
```

This exercises the same `run()` path without requiring a running Celery broker.

If executing from outside the API container, make sure the Python environment has the project installed and the backend is on the Python import path.

### Option B — Celery worker + Beat

Start the worker:

```bash
celery -A app.celery_app worker --loglevel=info &
```

Start Beat:

```bash
celery -A app.celery_app beat --loglevel=info &
```

Beat is responsible for the scheduled ingestion tasks registered by Phase 2.

---

## 13. Verify the Training Panel

After the Phase 2 ingestion/features path has run:

```bash
python -c "
from datetime import date
from app.features.pipelines.build_training_panel import get_training_panel
df = get_training_panel(date.today())
print(df.shape)
print(sorted(df.columns))
"
```

A successful run should print the resulting DataFrame shape and its sorted column names.

`get_training_panel()` is the documented handoff point from Phase 2 into Phase 3.

---

## 14. Recommended Complete Startup Sequence

For a fresh local environment, the documented sequence is:

### Step 1 — Configure environment

```bash
cp .env.example .env
```

### Step 2 — Start services

```bash
docker compose up -d
```

### Step 3 — Apply all migrations

```bash
docker compose exec api alembic upgrade head
```

### Step 4 — Seed reference data

```bash
docker compose exec api python scripts/seed_reference_data.py
```

### Step 5 — Seed five years of synthetic data

```bash
docker compose exec api python scripts/seed_synthetic_data.py --years-of-history 5
```

### Step 6 — Verify DB/API health

```bash
curl localhost:8000/health/db
```

### Step 7 — Ensure Celery imports Phase 2 tasks

Verify `backend/app/celery_app.py` contains:

```python
include=["app.ingestion.tasks"]
```

### Step 8 — Run Phase 2 ingestion

For a synchronous check:

```bash
python -c "
from app.ingestion.tasks import run_all
print(run_all.run())
"
```

Or start Celery:

```bash
celery -A app.celery_app worker --loglevel=info &
celery -A app.celery_app beat --loglevel=info &
```

### Step 9 — Verify feature-panel generation

```bash
python -c "
from datetime import date
from app.features.pipelines.build_training_panel import get_training_panel
df = get_training_panel(date.today())
print(df.shape)
print(sorted(df.columns))
"
```

---

## 15. Data Source / Synthetic Fallback Status

**Important:** the current Phase 2 implementation does not yet contain real API/scraper implementations.

The following connector methods are intentionally stubs:

- `_fetch_*`
- `_scrape_*`
- `_parse_*`

They raise `NotImplementedError` by design.

Therefore, the current acceptance path is based on the **synthetic fallback**.

Real API clients can later be wired into the individual connector methods without changing the overall connector architecture.

---

## 16. Important Phase 2 Modeling Assumptions

The Phase 2 implementation makes several explicit assumptions.

### 16.1 Declarative Base

`app/ingestion/models.py` and `app/features/models.py` attempt to import:

```python
from app.db.base import Base
```

and fall back to:

```python
from app.db.models import Base
```

If the project's actual declarative base lives elsewhere, those imports need to be adjusted.

### 16.2 Settings names

The connectors assume settings corresponding to the API keys and `use_synthetic_data` listed above. If the project's `Settings` class uses different attribute casing or aliases, connector code needs to be adjusted.

### 16.3 BDI proxy lane mapping

Composite BDI indices such as BCI/BPI/BSI/BHSI are not lane-specific, while `freight_rates` requires a non-null `trade_lane_id`.

The current connector therefore broadcasts each index to every seeded lane for the matching vessel class and tags the source as:

```text
trading_economics_proxy
```

This is a modeling choice, not a schema requirement, and should be revisited if it becomes misleading with real data.

### 16.4 AIS placeholder fleet

The synthetic AIS fallback uses three hardcoded placeholder IMO numbers because the Phase 1 `vessels` table was not described as having a seeded roster.

Once a real vessel roster exists, this should be replaced with a query against `vessels`.

### 16.5 Separate feature snapshot concepts

The new:

```text
feature_snapshots
```

table is distinct from the existing:

```text
Forecast.feature_snapshot
```

JSONB column. They serve different purposes.

---

## 17. Phase 1 Data Provenance

The reference-data provenance documented for Phase 1 is:

- `seed_data/ports.yaml` contains a `source` field per port.
- Paradip and Visakhapatnam figures are citation-backed.
- Other port figures are marked `source: estimated`.
- Those provenance notes are folded into the ports' `notes` column.
- Trade-lane distances are placeholder approximations rather than calculated sea routes.
- Synthetic time-series data is marked with `data_provenance='synthetic'`.

The documented sea-route calculation using the `searoute` package is a Phase 2 ingestion task rather than part of the Phase 1 seed data.

---

## 18. Expected Phase 1 Database State

After:

```bash
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed_reference_data.py
docker compose exec api python scripts/seed_synthetic_data.py --years-of-history 5
```

the documented acceptance expectation is that the plausibly populated Phase 1 tables have rows.

The following are intentionally empty:

```text
model_registry
forecasts
recommendations
```

This is expected because they represent outputs from later phases:

- `model_registry` — trained/registered models
- `forecasts` — model-generated forecasts
- `recommendations` — optimization-engine recommendations

Their zero counts are therefore not considered an error in Phase 1.

---

## 19. What Is Not Implemented Yet

According to the source documents, the following are explicitly outside the current Phase 2 scope:

1. Real API/scraper implementations for the connector stubs.
2. Great Expectations — Pandera is used instead.
3. Model training.
4. Model inference.
5. Later forecasting/optimization outputs.

The Phase 2 handoff into model training is:

```python
get_training_panel()
```

---

## 20. Quick Reference — Commands

### Initial setup

```bash
cp .env.example .env
docker compose up -d
```

### Database

```bash
docker compose exec api alembic upgrade head
```

### Reference seed

```bash
docker compose exec api python scripts/seed_reference_data.py
```

### Synthetic history

```bash
docker compose exec api python scripts/seed_synthetic_data.py --years-of-history 5
```

### Health

```bash
curl localhost:8000/health/db
```

### Phase 2 synchronous acceptance

```bash
python -c "
from app.ingestion.tasks import run_all
print(run_all.run())
"
```

### Phase 2 Celery worker

```bash
celery -A app.celery_app worker --loglevel=info
```

### Phase 2 Celery Beat

```bash
celery -A app.celery_app beat --loglevel=info
```

### Training-panel check

```bash
python -c "
from datetime import date
from app.features.pipelines.build_training_panel import get_training_panel
df = get_training_panel(date.today())
print(df.shape)
print(sorted(df.columns))
"
```

---

## 21. Phase Roadmap / Handoff

The current documented progression is:

```text
Phase 1
  ↓
Project scaffolding
Database schema
Reference data
Synthetic historical data
  ↓
Phase 2
  ↓
Ingestion
Validation
Data quality logging
Feature snapshots
Feature engineering
Training panel
  ↓
Phase 3
  ↓
Model training / inference
  ↓
Later phases
  ↓
Forecasting / optimization / recommendations
```

The important Phase 2 contract is:

```text
app.features.pipelines.build_training_panel.get_training_panel()
```

which supplies the training panel for Phase 3.

---

## 22. Troubleshooting / Caveats

### Celery does not discover Phase 2 tasks

Verify:

```python
include=["app.ingestion.tasks"]
```

is present in `app/celery_app.py`.

### Migration fails at Phase 2

Check that the `down_revision` in:

```text
alembic/versions/0002_phase2_data_quality_and_feature_snapshots.py
```

matches the actual Phase 1 migration revision.

### Real APIs are not producing data

This is expected with the current Phase 2 implementation. The real fetch/scrape/parse methods are intentionally stubs and the acceptance path uses synthetic fallback data.

### Some output tables contain zero rows

The following being empty is expected at this stage:

```text
model_registry
forecasts
recommendations
```

They are intended to be populated by later phases rather than by the initial seed process.

---

## 23. Current Definition of Done

The documented Phase 1 + Phase 2 local setup is ready for the next phase when:

- Docker services are running.
- Alembic migrations reach `head`.
- Reference data has been seeded.
- Five years of synthetic history can be seeded.
- `/health/db` succeeds.
- Phase 2 ingestion can execute through `run_all.run()`.
- Celery worker/Beat can discover and schedule ingestion tasks.
- Synthetic fallback ingestion completes end-to-end.
- `get_training_panel(date.today())` returns a DataFrame and its shape/columns can be inspected.

At that point, Phase 2 has established the documented handoff into Phase 3 model training/inference.
