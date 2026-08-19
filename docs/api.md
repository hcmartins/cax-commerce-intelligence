# API Reference

Base URL: `{API_BASE_URL}` (default `http://localhost:8000/api/v1`, set via
`API_V1_PREFIX` + host/port). Interactive docs are also served live at `/docs`
(Swagger UI) and `/redoc` on the running API — this file is the narrative version.

All request/response bodies are JSON.

## Errors

Every non-2xx response has the same shape:

```json
{
  "error": {
    "message": "Run 3fa85f64-... not found",
    "details": null
  }
}
```

| Status | When |
|---|---|
| `404` | The requested resource doesn't exist (or, for recalculate, the supplier offer doesn't belong to the given opportunity). |
| `422` | Request body/query params failed validation. `details` is Pydantic's error list (`loc`, `msg`, `type` per field). |
| `500` | Unexpected server error. Logged server-side; the response body never includes a traceback. |

## Health

Two unversioned, unauthenticated probes (`app/api/system.py`) — outside
`/api/v1` since these are container/orchestrator contracts, not the business
API.

### `GET /health`

Liveness — the process is up and can handle requests. Does **not** touch the
database.

```
200 {"status": "ok"}
```

### `GET /ready`

Readiness — the process is up *and* its database is reachable. This is what
`docker-compose.yml`'s `api` healthcheck polls, and what gates the `ui`
service's startup.

```
200 {"status": "ok", "database": "reachable"}
503 {"status": "unhealthy", "database": "unreachable"}
```

`GET /api/v1/health` still exists too, behaving the same as `/ready` — kept for
backward compatibility with the dashboard and existing callers.

## Correlation IDs

Every response carries an `X-Request-ID` header — echoed back if the request
sent one, otherwise generated per request. All log lines emitted while handling
that request (across routers, services, and the integration call log) carry the
same `request_id`; a `POST /runs` additionally binds `run_id` for the duration
of that run's pipeline, so a run's logs can be correlated end to end. See
`app/api/middleware.py`.

## Runs

A **run** is one product search — the whole discovery → sourcing → profitability →
recommendation pipeline, executed synchronously.

### `POST /runs`

Starts a search and runs it to completion (or failure) before responding.

**Request**

```json
{
  "query": "wireless earbuds",
  "filters": { "max_price": 50 }
}
```

`query` — required, 1–512 chars. `filters` — optional free-form object, passed
through to the search provider.

**Response** `201`

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "query_text": "wireless earbuds",
  "filters": { "max_price": 50 },
  "status": "COMPLETE",
  "error_message": null,
  "completed_at": "2026-08-15T19:23:56.987064",
  "created_at": "2026-08-15T19:23:56.935107"
}
```

`status` is one of `PENDING`, `RUNNING`, `COMPLETE`, `FAILED`. A `201` here means
the run was *created and executed* — check `status` in the body, since a failed
pipeline still returns `201` with `status: "FAILED"` and a populated
`error_message`, not an HTTP error. An HTTP `4xx`/`5xx` means the request itself
was invalid or the server errored before/outside the pipeline.

### `GET /runs`

Paginated, newest first.

**Query params:** `limit` (1–100, default 50), `offset` (≥0, default 0)

**Response** `200` — array of the same shape as `POST /runs`'s response.

### `GET /runs/{run_id}`

Single run. `404` if it doesn't exist.

### `GET /runs/{run_id}/opportunities`

Ranked opportunities produced by that run. `404` if the run doesn't exist (an
empty array, not a 404, if the run exists but found nothing).

**Response** `200`

```json
[
  {
    "id": "...",
    "run_id": "...",
    "title": "Rechargeable Wireless Earbuds Kit",
    "category": "Electronics",
    "source": "mock",
    "currency": "USD",
    "demand_score": 82.0,
    "competition_score": 41.0,
    "trend_score": 76.0,
    "avg_selling_price": 45.99,
    "overall_score": 68.07,
    "rank": 1,
    "created_at": "..."
  }
]
```

## Opportunities

### `GET /opportunities/{opportunity_id}`

Same fields as the list above, plus `raw_evidence` (the provider's raw payload for
that candidate, as a JSON object). `404` if it doesn't exist.

### `GET /opportunities/{opportunity_id}/suppliers`

Supplier offers sourced for this opportunity, cheapest first. `404` if the
opportunity doesn't exist.

```json
[
  {
    "id": "...",
    "product_opportunity_id": "...",
    "supplier": {
      "id": "...",
      "name": "TurkeyPrime Manufacturing Co.",
      "country": "Turkey",
      "website": "https://...",
      "contact_email": "sales@...",
      "contact_phone": "+90 ...",
      "source": "mock"
    },
    "unit_price": 57.13,
    "currency": "USD",
    "moq": 100,
    "lead_time_days": 21,
    "shipping_method": "Sea Freight",
    "shipping_cost": 340.12,
    "notes": "Auto-generated candidate for MVP evaluation.",
    "created_at": "..."
  }
]
```

### `GET /opportunities/{opportunity_id}/profitability`

Profitability calculations for this opportunity — one per supplier offer that's
been evaluated, best profit first. `404` if the opportunity doesn't exist.

```json
[
  {
    "id": "...",
    "product_opportunity_id": "...",
    "supplier_offer_id": "...",
    "landed_cost": 60.54,
    "selling_price": 45.99,
    "marketplace_fee": 8.28,
    "shipping_cost": 340.12,
    "other_costs": 0.0,
    "profit": -22.83,
    "margin_pct": -49.66,
    "roi_pct": -37.72,
    "assumptions": {
      "marketplace_fee_pct": 15.0,
      "payment_fee_pct": 3.0,
      "selling_price_source": "opportunity.avg_selling_price"
    },
    "recommendation": {
      "id": "...",
      "decision": "REJECT",
      "rationale": "Margin (-49.7%) and/or ROI (-37.7%) too thin at a $22.83 loss per unit to justify sourcing.",
      "confidence": 0.5,
      "created_at": "..."
    },
    "created_at": "..."
  }
]
```

`decision` is one of `BUY_TEST`, `WATCH`, `REJECT`.

### `POST /opportunities/{opportunity_id}/profitability:recalculate`

Re-runs the calculator for **one supplier offer** with optionally overridden
assumptions — for the dashboard's "what if" interaction. Writes a **new**
calculation + recommendation; the original is left untouched.

**Request**

```json
{
  "supplier_offer_id": "...",
  "selling_price": 65.0,
  "marketplace_fee_pct": 12.0,
  "payment_fee_pct": 3.0,
  "other_costs": 0.0
}
```

Only `supplier_offer_id` is required. Any omitted override falls back to the
opportunity's discovered market price / the app's configured default fee
percentages — recorded in the response's `assumptions.selling_price_source`
(`"override"` or `"opportunity.avg_selling_price"`).

**Response** `201` — same shape as one item from the profitability list above.

**Errors:** `404` if the opportunity doesn't exist, or if `supplier_offer_id`
doesn't belong to it. `422` if `selling_price` (must be `> 0`) or a fee/cost field
(must be `≥ 0`) fails validation.

## Example: full flow with curl

```bash
BASE=http://localhost:8000/api/v1

run=$(curl -s -X POST "$BASE/runs" -H "Content-Type: application/json" \
  -d '{"query": "wireless earbuds", "filters": {"max_price": 50}}')
run_id=$(echo "$run" | python -c "import json,sys;print(json.load(sys.stdin)['id'])")

opp_id=$(curl -s "$BASE/runs/$run_id/opportunities" \
  | python -c "import json,sys;print(json.load(sys.stdin)[0]['id'])")

curl -s "$BASE/opportunities/$opp_id/suppliers" | python -m json.tool
curl -s "$BASE/opportunities/$opp_id/profitability" | python -m json.tool
```
