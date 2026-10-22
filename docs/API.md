# Toko FR API

Base URL for local testing: `http://127.0.0.1:8000`

Import [`postman/TokoFR.postman_collection.json`](postman/TokoFR.postman_collection.json) into Postman. Set `baseUrl` and `destinationId`; set `apiKey` to the same secret as `API_KEY` in `.env`. The provider key stays on the server and is never needed in Postman. Do not export/share values containing real keys.

## Authentication

`GET /api` requires the `X-API-Key` header. Set `API_KEY` in the server's ignored `.env` file. Requests with no configured key or an invalid key receive HTTP `401`.

`GET /api/transaksi` is for the admin dashboard and requires an authenticated admin session. Anonymous clients receive HTTP `401`; signed-in non-admin accounts receive HTTP `403`. The endpoint allows up to 10 requests per minute per IP.

State-changing web actions use POST and the application enables CSRF verification.

## Endpoints

### List transactions with an API key

`GET /api`

Headers: `X-API-Key: <API_KEY>`

Query parameters:

| Parameter | Description |
| --- | --- |
| `page` | 1-based page number; defaults to `1` |
| `perPage` | Items per page, clamped to `1..100`; defaults to `10` |
| `status` | Optional transaction status: `0`, `1`, or `2` |
| `username` | Optional partial username match |

The JSON response contains `results` and a `pagination` object (`page`, `perPage`, `total`, `totalPages`). Each result includes transaction details.

### Admin dashboard transactions

`GET /api/transaksi?page=1&perPage=10`

Requires the current admin's session cookie. Supports `page`, `perPage`, `status`, and `username`; response contains `data` and `pagination`. This endpoint is rate-limited to 10 requests per minute per IP.

### Search shipping destinations

`GET /get-location?search=Jakarta&limit=10`

No user session is required. Search text is required. The limit is clamped to `1..50`. The server calls the Komerce/RajaOngkir provider using `COST_API_KEY`; the provider key is never sent by the client. Rate limit: 30 requests per minute per IP.

### Calculate shipping cost

`GET /get-cost?origin=64999&destination={{destinationId}}&weight=1000&courier=jne`

No user session is required. `destination` is required. Weight is in grams and must be between `1` and `50000`. `origin` defaults to `64999`, `weight` to `1000`, and `courier` to `jne`. Rate limit: 20 requests per minute per IP.

The provider key is sent only from the server to Komerce. Use the app's `/get-cost` endpoint so the provider credential remains on the server.

The Django checkout uses the same location and cost endpoints to show courier services and recalculate the order total. The selected cost is verified against a fresh provider quote before the order is saved. The current checkout estimate uses a fixed weight of `1000` grams.

## Error responses

- `401`: missing/invalid API key or no authenticated session
- `403`: authenticated account does not have the admin role
- `422`: invalid query or missing required input
- `429`: rate limit exceeded
- `502`: shipping provider failed or returned an invalid response
- `503`: required server-side provider key is not configured

## Secrets

Set `API_KEY` and `COST_API_KEY` in `.env`; do not commit or send them in Postman collection exports. A provider key was previously present in application source, so revoke it in the provider dashboard and configure a newly rotated key.