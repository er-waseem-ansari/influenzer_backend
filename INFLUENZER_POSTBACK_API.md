# Claude Code Prompt — Secure Conversion Postback API (FastAPI)

Build the **conversion postback receiver** for Influenzer — the endpoint brands' servers call to report
conversions (purchases, refunds) so we attribute them to influencers and compute metrics. **Security is
the top priority: only the owning brand must ever be able to post for their campaigns.** Use plain
FastAPI + the existing PostgreSQL; do not introduce new infrastructure (Redis optional, see below).

## Stack & architecture

- Python 3.12, **FastAPI**, **Pydantic v2**, async **SQLAlchemy 2.0**, **PostgreSQL**, Alembic.
- Reuse the existing layered structure: `api/` (routes), `schemas/` (Pydantic), `domain/` (logic),
  `services/`, `db/` (models + repos), `core/` (config, security, errors).
- No business logic in routes. Pure, typed, tested. Follow the same system-design standards as the
  existing campaign API (single source of truth, no magic strings, exhaustiveness checks).

## Endpoints

```
POST /collect/event     # conversions (event_type: purchase | refund), event-typed & extensible
```

One endpoint, discriminated on `event_type`, so adding `signup` etc. later is a new variant, not a new
route. (Refund may also be modeled as `event_type: "refund"` carrying the original `order_id`.)

---

## SECURITY — the core requirement (implement all of this)

The endpoint must guarantee a request genuinely came from the brand that owns the campaign, is
untampered, and is not a replay. Use the industry-standard **HMAC signature** scheme:

### 1. Per-brand signing secret
- On integration setup, generate a high-entropy secret per brand (e.g. 32 bytes, `secrets.token_hex`).
- Store it **encrypted at rest** (app-level encryption / KMS-style key from config — not plaintext, not
  a one-way hash, since we must recompute the HMAC). Show it to the brand once; allow rotation.
- Each brand/integration has a stable public `integration_id` used to look up its secret.

### 2. HMAC-SHA256 request signing
- Brand sends headers: `X-Inflz-Integration` (the integration_id), `X-Inflz-Timestamp` (unix seconds),
  `X-Inflz-Signature` (hex HMAC).
- Signature = `HMAC_SHA256(secret, f"{timestamp}.{raw_body}")` over the **raw request body bytes** —
  NOT the re-serialized JSON. Read the raw body in a dependency/middleware BEFORE Pydantic parsing;
  re-serializing changes bytes and breaks the signature. Verify, then parse.
- Compare using **constant-time comparison** (`hmac.compare_digest`) to prevent timing attacks.

### 3. Replay protection
- Reject if `X-Inflz-Timestamp` is outside a ±5-minute window (clock-skew tolerance). Stale signed
  requests can't be replayed later.
- (Optional, stronger — needs Redis) store a per-request nonce / `event_id` with TTL = the window and
  reject reuse, for full replay immunity. Degrade gracefully if Redis absent.
- Idempotency on `order_id` (below) also blunts replays of the same conversion.

### 4. Authorization (not just authentication)
- After verifying the signature proves *who* they are, verify the integration **owns the campaign**
  referenced (via click_id/coupon resolution). A valid brand must not post conversions for a campaign
  that isn't theirs. Reject cross-tenant attempts.

### 5. Transport & abuse
- Require HTTPS (enforce at proxy; reject/redirect plain HTTP).
- Per-integration **rate limiting** (Redis sliding-window if available; in-memory fallback) to stop
  floods.
- Generic failure responses: return `401` for any auth/signature/timestamp failure **without** leaking
  which check failed or whether the integration_id exists (no enumeration). Enough for a legit
  integrator to debug from docs, not enough to aid an attacker. `400` only for malformed JSON/schema.

### 6. Secret hygiene
- Secret never in the URL or query string, never logged. Strip signature/secret from any log line.
- Constant-time, fail-closed everywhere: any verification error → reject, never "allow on error."

---

## Payload schema

```json
{
  "event_type": "purchase",
  "click_id": "clk_7Yz2",
  "coupon_code": "MAYA10",
  "order_id": "ORD-9982",
  "value": 1499.00,
  "currency": "INR",
  "status": "confirmed",
  "occurred_at": "2026-06-14T14:31:00Z",
  "meta": {}
}
```

- `event_type` (required), `order_id` (required), `currency` (required for purchase), `value` (required
  for purchase), `occurred_at` (required).
- `click_id` and `coupon_code` are **both optional individually**, but **at least one must be present
  and resolvable** (see attribution). `meta` is freeform.
- Refund payload: `event_type:"refund"` + the original `order_id` (+ optional partial `value`).

---

## Attribution logic (domain layer)

A conversion needs *one* resolvable attribution key — **click_id OR coupon_code**, not both:

```
1. if click_id present and resolves to a click within the campaign's attribution/cookie window
       → attribute via click_id
2. elif coupon_code present and maps to an assigned creator
       → attribute via coupon_code   (more reliable: survives cross-device/time)
3. else → store as UNATTRIBUTED (log it; credit no one). Do NOT reject the request.
```

- Enforce the **attribution window** (campaign `cookieWindow`): a click older than the window does not
  earn credit — fall through to coupon, else unattributed.
- If both keys present, prefer the coupon code as source of truth for coupon-driven sales; if they
  resolve to *different* creators, flag the event for review (don't silently pick one).
- **Code-only (no click_id) is fully valid** — accept and attribute via the code. Optionally tag
  `confidence: "code_only"` (code-leakage awareness), but still count it.

---

## Idempotency & storage

- **Dedupe on `order_id`** (per integration), independent of which key attributed it. A repeat
  `order_id` → return `200` and do nothing (no double-count, no double-commission). This is mandatory.
- **Append-only / raw-first:** insert the raw verified event immediately (durable), then resolve
  attribution and write the conversion record. If processing fails, the raw event can be replayed.
  Never overwrite; a conversion is an immutable fact.
- Refund: find the original conversion by `order_id`, mark it reversed / subtract value, reverse any
  commission. Keep verified revenue **net** of refunds.

## HTTP status codes (the brand's retry logic depends on these)

- `200`/`202` — accepted (and also on duplicate, so they stop retrying).
- `400` — malformed body / schema / missing required field.
- `401` — signature / timestamp / auth failure (generic message).
- `403` — authenticated but not authorized for that campaign.
- `429` — rate limited.
- `5xx` — only on *our* failure, so the brand retries.

## Persistence

- `integrations` (or extend existing): `integration_id`, `brand_id`, encrypted `secret`, status, rotated_at.
- `raw_postback_events`: raw body, headers (minus secret), received_at, verification result.
- `conversions`: order_id (unique per integration), event_type, attributed_influencer_id, campaign_id,
  attribution_key (`click_id`/`coupon`), value, currency, status, occurred_at, reversed flag, confidence.
- Indexes: unique `(integration_id, order_id)`; lookups by campaign, influencer, occurred_at.

## Deliverables

- The `/collect/event` route, the HMAC verification dependency (raw-body, constant-time, timestamp
  window), per-brand secret storage (encrypted) + rotation, attribution resolver, idempotent
  store, refund handling, rate limiting, Alembic migration.
- **Security-focused tests** (must include): valid signature passes; tampered body fails; wrong secret
  fails; stale/future timestamp fails; replayed order_id deduped; cross-tenant campaign rejected (403);
  missing both keys → unattributed not rejected; code-only attributes correctly; refund reverses revenue
  + commission; constant-time compare used (no early-return on mismatch).
- A short doc/README: the signing scheme with a copy-paste example (curl + Python + Node) a brand's dev
  can implement — documenting the **raw-body signing** and **timestamp** steps most prominently, since
  those are where integrators fail.

## Do not

- Parse JSON before verifying the signature; sign re-serialized bytes; put the secret in the URL or
  logs; use `==` for signature comparison; allow-on-error; reject code-only conversions; or double-count
  on retries.