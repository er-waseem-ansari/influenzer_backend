# Conversion Postback API — Implementation & Exact Contract

This document is the **single source of truth** for the postback integration, kept
in sync with the code. It serves two readers:

1. **Frontend / brand-onboarding UI** — what the brand connects, what we show them
   (the secret, the integration id), and the exact instructions their server must
   follow. See §1–§4 and §10–§12.
2. **Backend / maintainers** — the build, the security reasoning, the module
   layout. See §5–§9.

Every field, header, status code, and constant below is taken directly from the
implementation. If you change the code, update this file.

> Status legend: ✅ done · 🔜 planned

---

## 0. Two surfaces, two audiences

| Surface | Who calls it | Auth | Where it's used in the UI |
|---|---|---|---|
| **Integration management** (`/api/v1/brand/integrations…`) | The **brand dashboard frontend** | Brand JWT | The "Integrations / Connect your store" settings screen |
| **Conversion receiver** (`/collect/event`) | The **brand's backend server** | HMAC signature | Not called by the frontend — we *document* it for the brand's developers |

The frontend never signs or calls `/collect/event`. The frontend's job is to let a
brand **create an integration**, **show the secret once**, **list/rotate**
integrations, and **render the integration guide** (the curl/Node/Python snippet)
so the brand's engineers can wire their server.

---

## 1. What the brand is implementing (the mental model)

A brand reports a conversion (a purchase or refund) from **their server** to:

```
POST /collect/event
```

We must guarantee the request:

1. genuinely came from the brand that owns the campaign (**authentication**),
2. wasn't tampered with in transit (**integrity**),
3. isn't a replay of an earlier captured request (**freshness**),
4. only posts for *that brand's* campaigns (**authorization**),

then attribute the conversion to an influencer (via click or coupon) and store it
**once** (idempotent on `order_id`).

The endpoint takes **no brand info in the URL**. The caller identifies its
integration through the `X-Inflz-Integration` header — an opaque, high-entropy
handle (`intg_<random>`) that reveals nothing about the brand and is resolved
server-side.

---

## 2. The signing scheme (what the brand's server must compute)

The brand holds a **per-integration secret** (shown once at setup, stored encrypted
at rest on our side). On every request its server sends three headers:

| Header | Value |
|---|---|
| `X-Inflz-Integration` | the integration's `public_id` (`intg_…`) — looks up the secret |
| `X-Inflz-Timestamp`   | unix time in **seconds** when the request was signed |
| `X-Inflz-Signature`   | `hex( HMAC_SHA256(secret, "{timestamp}.{raw_body}") )` |

Exact signing rules (from `app/core/postback_signing.py`):

- **Algorithm:** HMAC-SHA256, hex-encoded (lowercase).
- **Key:** the secret string, used as **UTF-8 bytes**.
- **Message:** the literal string `"{timestamp}.{raw_body}"` — i.e. the timestamp
  string, a single `.` (0x2E), then the **raw request body bytes**.
- **Sign the exact bytes you send.** The signature is over the raw body on the
  wire — *never* a re-serialized JSON. If you parse and re-dump JSON (changing key
  order, spacing, or number formatting) the signature will not match. Build the
  body string once, sign that exact string, send that exact string.
- We compare with a **constant-time** function, so signatures can't be guessed
  byte-by-byte via timing.

Pseudocode:

```
body      = '{"event_type":"purchase","order_id":"…",…}'   # the exact string you POST
timestamp = "1718900000"                                    # str(int(time.time()))
signature = HMAC_SHA256(key=secret, msg=timestamp + "." + body).hexdigest()
```

---

## 3. Defence layers, in order

A request passes through these gates (any failure → reject, **fail-closed**):

```
  raw body read  ──▶  integration lookup  ──▶  status active?
        │                                            │
        ▼                                            ▼
  per-integration rate limit  ──▶  timestamp within ±5 min  ──▶  HMAC valid (constant-time)
        │                                            │
        ▼                                            ▼
  replay nonce unused (Redis)  ──▶  parse JSON (schema)  ──▶  attribute
        │                                            │
        ▼                                            ▼
  authorize (owns campaign?)  ──▶  store (idempotent on order_id)
```

### Status codes (exact)

| Code | When | Body |
|---|---|---|
| **200** | Accepted — **including duplicates** (so the brand stops retrying) | `PostbackAccepted` (§12) |
| **400** | Malformed/incomplete JSON or schema violation (e.g. missing `order_id`, purchase with no `value`) | error |
| **401** | **Any** auth/integrity/freshness/replay failure — single **generic** message; never reveals which check failed or whether the integration exists | `{"detail":"Postback authentication failed."}` |
| **403** | Authenticated, but the resolved campaign belongs to a different brand (cross-tenant) | error |
| **429** | Per-integration rate limit exceeded | error |
| **5xx** | *Our* failure — so the brand's retry logic kicks in | error |

> Design note: a `400` means "fix your payload"; a `401` means "fix your auth"; a
> `429` means "slow down and retry later"; a `5xx` means "retry, it's us". A `200`
> with `"duplicate": true` means "stop retrying, we already have it."

---

## 4. Operational constants (current config)

From `app/config.py` (`POSTBACK_*`). Surface the relevant ones in the brand guide:

| Constant | Value | Meaning |
|---|---|---|
| `POSTBACK_TIMESTAMP_TOLERANCE_SECONDS` | **300** | `X-Inflz-Timestamp` must be within ±5 min of server time (rejects stale **and** future) |
| `POSTBACK_RATE_LIMIT_MAX` | **600** | Max events per window, **per integration** |
| `POSTBACK_RATE_LIMIT_WINDOW_SECONDS` | **60** | The rate-limit window (→ 600 events / minute) |
| `POSTBACK_REPLAY_PROTECTION_ENABLED` | **true** | One-time nonce per signature (Redis) |
| `POSTBACK_DEFAULT_COOKIE_WINDOW_DAYS` | **30** | Click attribution window when the campaign doesn't override it |

Identifier formats:

| Thing | Format | Example |
|---|---|---|
| Integration `public_id` (header value) | `intg_` + 24 hex chars | `intg_9f1c0a7b3e5d6f2a1b4c8d0e` |
| Signing `secret` | 64 hex chars (32 bytes) | `4b8c…` (shown once) |

---

## 5. Module layout (modular & upgradable)

Each concern lives in its own file so it can evolve (or be swapped) independently:

```
app/core/
  postback_signing.py     # PURE crypto: compute/verify HMAC, timestamp window. No I/O — trivially testable.
  postback_replay.py      # Redis nonce store (replay immunity), graceful degrade.
  postback_security.py    # FastAPI dependency: orchestrates raw-body read, lookup, verify, replay, rate-limit.

app/models/
  integration.py          # PostbackIntegration: per-brand signing secret (encrypted), status, rotation.
  postback.py             # RawPostbackEvent (append-only audit) + Conversion (the fact).
  attribution_source.py   # Click + CouponAssignment — upstream lookup tables attribution reads.

app/schemas/
  postback.py             # Public wire contract: PostbackEvent union (purchase|refund) + accepted response.
  integration.py          # Integration management responses (secret shown once).

app/services/
  attribution.py          # PURE resolver: click vs coupon vs unattributed, window, conflict flagging.
  commission.py           # Commission compute + reversal from the campaign's affiliate config.
  postback_service.py     # Orchestration: idempotency, raw-first store, attribute, authorize, refund.
  integration_service.py  # Create / rotate integrations (generates + encrypts the secret).

app/api/v1/
  collect.py              # POST /collect/event  (public, HMAC-authenticated).
  brand/integrations.py   # Brand-authenticated integration management (create/rotate/list).
```

**Why split this way:** the crypto primitive (`postback_signing`) has zero
dependencies and is the most security-critical, so it's isolated and unit-tested in
full. The Redis-specific replay store is separate so the "optional hardening" can be
toggled/replaced without touching verification. Attribution is a pure function
(no DB) so its branching logic is exhaustively testable; the service does the DB
I/O around it.

---

## 6. Data model

- **`postback_integrations`** — `id` (uuid), `public_id` (`intg_…`, unique, the
  header value), `brand_id`, `secret` (encrypted at rest), `status`
  (`ACTIVE`/`DISABLED`), `label`, `rotated_at`.
- **`raw_postback_events`** — append-only: raw body, sanitized headers (no
  signature/secret), `received_at`, verification result. The durable "we received
  this" record; lets us replay processing if attribution logic changes.
- **`conversions`** — the immutable fact: `order_id` (unique per integration),
  `event_type`, `campaign_id`, `attributed_influencer_id`, `attribution_key`
  (`CLICK_ID`/`COUPON`/null), `value`, `currency`, `status`, `occurred_at`,
  `commission_amount`, `reversed`/`reversed_value`/`reversed_at`, `confidence`,
  `flagged_for_review`.
- **`clicks`** / **`coupon_assignments`** — minimal upstream tables that map a
  `click_id` / `coupon_code` to `(campaign, influencer)`. Other parts of the system
  populate these; attribution only reads them.

---

## 7. Attribution logic

One resolvable key wins, in this order:

1. `click_id` resolves to a click **within the campaign's cookie window** → attribute by click (`attribution_key = CLICK_ID`).
2. else `coupon_code` maps to an assigned creator → attribute by coupon
   (`attribution_key = COUPON`; tag `confidence = CODE_ONLY` when there was no click at all).
3. else → store **UNATTRIBUTED** (credit no one, `attribution_key = null`) — **never reject**.

Special cases:
- A click **older than the window** doesn't earn credit → fall through to coupon.
- If both keys resolve but to **different creators** → attribute by coupon (source
  of truth for coupon-driven sales) **and** set `flagged_for_review = true` — we
  never silently pick one.
- `coupon_code` is matched **case-insensitively** (normalised to uppercase on lookup).
- The cookie window comes from the campaign's affiliate config
  (`24H`/`7D`/`30D`/`60D`), falling back to the 30-day default.

---

## 8. Idempotency, durability, refunds

- **Idempotent on `(integration_id, order_id)`**: a repeated purchase returns `200`
  with `"duplicate": true` and does nothing — no double count, no double commission.
- **Raw-first**: the verified raw event is inserted immediately (durable), then the
  conversion is resolved and written. Conversions are never overwritten.
- **Refund**: looks up the original conversion by `order_id`, marks it reversed
  (subtracting `value` for partials) and reverses the commission, so verified
  revenue stays **net** of refunds.
  - A refund with a `value` = partial reversal; a refund with **no `value`** = full reversal.
  - A refund for an **unknown** `order_id` is still accepted (`200`) and audited — nothing to reverse.
  - A **replayed** refund on an already-reversed order is a no-op (`200`, `"duplicate": true`).

---

## 9. Endpoints delivered

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/collect/event` | HMAC signature | Receive a purchase/refund conversion |
| `POST` | `/api/v1/brand/integrations` | Brand JWT (ADMIN/MANAGER) | Create integration → secret shown once |
| `POST` | `/api/v1/brand/integrations/{id}/rotate` | Brand JWT (ADMIN/MANAGER) | Rotate the signing secret |
| `GET`  | `/api/v1/brand/integrations` | Brand JWT (any member) | List integrations (no secrets) |

> Note the public receiver has **no `/api/v1` prefix** — it is mounted at the root
> (`/collect/event`). The management endpoints **do** carry the `/api/v1` prefix.

---

## 10. Integration-management contract (the frontend calls these)

All four use the brand session/JWT (same auth as the campaign & profile routers).
Writes (`create`, `rotate`) require a write-capable role (**ADMIN / MANAGER**);
`list` is open to any active member.

### 10.1 Create an integration

```
POST /api/v1/brand/integrations
Authorization: Bearer <brand JWT>
Content-Type: application/json
```

**Request body** (`IntegrationCreate`):

| Field | Type | Required | Constraints |
|---|---|---|---|
| `label` | string \| null | no | max 120 chars; a human name like "Shopify – US store" |

```json
{ "label": "Shopify – US store" }
```

**Response `201 Created`** (`IntegrationSecretResponse`) — **the only time the
secret is ever returned**:

```json
{
  "integration": {
    "id": "f5b2…uuid",
    "public_id": "intg_9f1c0a7b3e5d6f2a1b4c8d0e",
    "brand_id": "a1c3…uuid",
    "status": "ACTIVE",
    "label": "Shopify – US store",
    "rotated_at": null,
    "created_at": "2026-06-20T10:00:00Z",
    "updated_at": "2026-06-20T10:00:00Z"
  },
  "secret": "4b8c…64-hex-chars…",
  "message": "Store this signing secret securely now. It is shown only once and cannot be retrieved later; rotate to obtain a new one."
}
```

> **Frontend must:** display `secret` once, with a copy button and a clear "you
> can't see this again — store it in your server's secrets" warning. Persist only
> the `public_id` for display; never store the `secret` client-side.

### 10.2 Rotate the secret

```
POST /api/v1/brand/integrations/{integration_id}/rotate
Authorization: Bearer <brand JWT>
```

No request body. **Response `200`** is the same `IntegrationSecretResponse` shape as
create, carrying a **new** `secret` and a non-null `rotated_at`. The previous secret
**stops working immediately** — show a confirmation step before calling this.

### 10.3 List integrations

```
GET /api/v1/brand/integrations
Authorization: Bearer <brand JWT>
```

**Response `200`** — array of `IntegrationResponse` (**no secret**), newest first:

```json
[
  {
    "id": "f5b2…uuid",
    "public_id": "intg_9f1c0a7b3e5d6f2a1b4c8d0e",
    "brand_id": "a1c3…uuid",
    "status": "ACTIVE",
    "label": "Shopify – US store",
    "rotated_at": null,
    "created_at": "2026-06-20T10:00:00Z",
    "updated_at": "2026-06-20T10:00:00Z"
  }
]
```

`IntegrationResponse` fields:

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | internal id (used in the rotate URL) |
| `public_id` | string | the `X-Inflz-Integration` header value the brand's server sends |
| `brand_id` | uuid | owning brand |
| `status` | string | `ACTIVE` or `DISABLED` (only `ACTIVE` integrations can post events) |
| `label` | string \| null | the human label |
| `rotated_at` | datetime \| null | last secret rotation, if any |
| `created_at` | datetime | |
| `updated_at` | datetime | |

---

## 11. Conversion event contract — `POST /collect/event` (request)

The brand sends **snake_case** JSON. The body is a discriminated union on
`event_type`. Unknown top-level keys are **rejected** (`extra="forbid"`) — this
catches integrator typos early. All string fields are whitespace-trimmed.

### 11.1 Common fields (both `purchase` and `refund`)

| Field | Type | Required | Constraints |
|---|---|---|---|
| `event_type` | `"purchase"` \| `"refund"` | **yes** | the union discriminator |
| `order_id` | string | **yes** | 1–128 chars; idempotency key (unique per integration) |
| `occurred_at` | datetime (ISO 8601) | **yes** | when the conversion happened |
| `click_id` | string \| null | no | max 128; the click attribution key |
| `coupon_code` | string \| null | no | max 64; the coupon attribution key (matched case-insensitively) |
| `status` | string \| null | no | max 30; your order status passthrough (stored, not interpreted) |
| `meta` | object | no | free-form JSON; defaults to `{}` |

> Attribution keys are **both optional**. A payload with neither is still accepted
> and stored UNATTRIBUTED — the domain decides credit, never the parser.

### 11.2 `purchase`-only fields

| Field | Type | Required | Constraints |
|---|---|---|---|
| `value` | number | **yes** | **> 0** (the order value) |
| `currency` | string | **yes** | 3-letter ISO code; uppercased server-side (e.g. `USD`) |

### 11.3 `refund`-only fields

| Field | Type | Required | Constraints |
|---|---|---|---|
| `value` | number \| null | no | **> 0** if present. **Omit for a full refund**; include for a partial |
| `currency` | string \| null | no | 3-letter ISO if present |

### 11.4 Examples

Purchase:

```json
{
  "event_type": "purchase",
  "order_id": "ORD-10293",
  "click_id": "clk_abc123",
  "coupon_code": "CREATOR10",
  "value": 89.90,
  "currency": "USD",
  "status": "paid",
  "occurred_at": "2026-06-20T14:21:05Z",
  "meta": { "sku": "TEE-BLK-M" }
}
```

Full refund (no `value`):

```json
{
  "event_type": "refund",
  "order_id": "ORD-10293",
  "occurred_at": "2026-06-25T09:00:00Z"
}
```

Partial refund:

```json
{
  "event_type": "refund",
  "order_id": "ORD-10293",
  "value": 20.00,
  "currency": "USD",
  "occurred_at": "2026-06-25T09:00:00Z"
}
```

### 11.5 Full request (headers + body)

```
POST /collect/event HTTP/1.1
Host: <api-host>
Content-Type: application/json
X-Inflz-Integration: intg_9f1c0a7b3e5d6f2a1b4c8d0e
X-Inflz-Timestamp: 1718900000
X-Inflz-Signature: 2b1f…hex-hmac…

{"event_type":"purchase","order_id":"ORD-10293",...}
```

---

## 12. Conversion event contract — response (`PostbackAccepted`)

Returned with `200` for every accepted event (**including duplicates**):

| Field | Type | Meaning |
|---|---|---|
| `status` | string | always `"accepted"` |
| `order_id` | string | echo of the order id |
| `event_type` | `"purchase"` \| `"refund"` | echo |
| `duplicate` | bool | `true` if we already had this `order_id` (or a re-applied refund) — **stop retrying** |
| `attributed` | bool | `true` if credited to an influencer |
| `attribution_key` | string \| null | `"CLICK_ID"` \| `"COUPON"` \| `null` |
| `confidence` | string \| null | `"CODE_ONLY"` when credited by coupon with no click; else `null` |
| `flagged_for_review` | bool | `true` when click and coupon resolved to different creators |
| `campaign_id` | uuid \| null | resolved campaign, if attributed |
| `influencer_id` | uuid \| null | credited influencer, if attributed |

```json
{
  "status": "accepted",
  "order_id": "ORD-10293",
  "event_type": "purchase",
  "duplicate": false,
  "attributed": true,
  "attribution_key": "CLICK_ID",
  "confidence": null,
  "flagged_for_review": false,
  "campaign_id": "c0ffee…uuid",
  "influencer_id": "1nf1u…uuid"
}
```

> A `refund` for an unknown order returns the minimal accepted shape
> (`status`/`order_id`/`event_type` only; the attribution fields stay at defaults).

A full signing guide with copy-paste curl / Python / Node snippets lives in
`POSTBACK_INTEGRATION_GUIDE.md` — link to it from the integration screen.

---

## 13. Build log

- ✅ Config knobs (`POSTBACK_*`).
- ✅ Models: `PostbackIntegration`, `RawPostbackEvent`, `Conversion`, `Click`, `CouponAssignment` (+ registered in `create_tables.py`).
- ✅ Security core: `postback_signing` (pure HMAC), `postback_replay` (Redis nonce, fail-open), `postback_security` (dependency).
- ✅ Schemas: `postback` (event union + accepted), `integration` (mgmt + once-only secret).
- ✅ Services: `attribution` (pure), `commission` (pure), `postback_service` (orchestration), `integration_service`.
- ✅ Routes: `collect.py` (public), `brand/integrations.py` (managed); wired in `main.py`.
- ✅ Tests: signing (12), attribution (7), commission (6) — all pure, no DB/Redis. Full suite green (78).

### Deferred / future work (intentional)
- **Service-level integration tests** (dedupe, cross-tenant 403, refund reversal end-to-end) need a Postgres test fixture — the existing suite is DB-free. The logic they'd cover is unit-tested at the pure layer; add a `TestClient` + test-DB fixture when one is introduced.
- **Multiple distinct partial refunds** per order: currently the first refund reverses and further refunds on the same `order_id` are idempotent no-ops. A dedicated `refunds` ledger (refund_id) would lift this.
- **HTTPS enforcement** is expected at the proxy/ingress, not in app code.
