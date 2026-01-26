# Performance Testing with Locust

This directory contains performance/load tests for the Satellite Migration API.

## Prerequisites

Install Locust:
```bash
pip install locust
```

## Running Tests

### Interactive Mode (Web UI)

Start the API server, then run:

```bash
cd /path/to/satellite-data
locust -f backend/tests/performance/locustfile.py --host=http://localhost:8000
```

Open http://localhost:8089 in your browser to configure and start the test.

### Headless Mode (CLI)

For CI/CD or scripted tests:

```bash
# 100 users, spawn rate 10/s, run for 60 seconds
locust -f backend/tests/performance/locustfile.py \
    --host=http://localhost:8000 \
    --headless \
    -u 100 \
    -r 10 \
    -t 60s
```

### With HTML Report

```bash
locust -f backend/tests/performance/locustfile.py \
    --host=http://localhost:8000 \
    --headless \
    -u 100 \
    -r 10 \
    -t 60s \
    --html=locust_report.html
```

## User Types

The test simulates three types of users:

### 1. AnonymousUser (weight: 3)
- No API key
- Rate limited to 100 req/min
- Simulates casual visitors

**Tasks:**
- Health checks
- List/view regions
- Get metrics
- View map tiles

### 2. AuthenticatedUser (weight: 1)
- Uses API key header
- Rate limited to 1000 req/min
- Simulates power users

**Tasks:**
- All anonymous tasks
- Bulk metrics requests
- Export requests (PDF, CSV, Animation)

### 3. TileHeavyUser (weight: 2)
- Simulates map-heavy usage
- Requests many tiles rapidly
- Tests tile serving performance

**Tasks:**
- Load full map views (25 tiles at once)

## Expected Performance Targets

| Endpoint | P50 | P95 | P99 |
|----------|-----|-----|-----|
| `/health` | <10ms | <50ms | <100ms |
| `/api/v1/regions` | <100ms | <300ms | <500ms |
| `/api/v1/metrics/{id}` | <200ms | <500ms | <1s |
| `/api/v1/tiles/...` | <50ms | <200ms | <500ms |
| Export requests | <500ms | <2s | <5s |

## Interpreting Results

### Key Metrics

- **Requests/s (RPS)**: Total throughput
- **Failure Rate**: Should be < 1% under normal load
- **P95 Response Time**: 95th percentile latency
- **Max Response Time**: Watch for outliers

### Warning Signs

- Failure rate > 1%: Check for rate limiting or errors
- P95 > 2x P50: High variance, possible bottleneck
- RPS decreasing over time: Resource exhaustion
- 429 errors: Rate limiting working (expected at high load)

## Configuration

Edit `locustfile.py` to adjust:

- `SAMPLE_REGION_IDS`: Use actual region IDs from your database
- `wait_time`: Time between requests per user
- `weight`: Proportion of each user type
- Task weights: Frequency of each request type

## CI Integration

Example GitHub Actions step:

```yaml
- name: Run Load Tests
  run: |
    pip install locust
    locust -f backend/tests/performance/locustfile.py \
      --host=http://localhost:8000 \
      --headless \
      -u 50 \
      -r 5 \
      -t 30s \
      --exit-code-on-error 1
```
