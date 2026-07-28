# Conversion Postback — Integration Guide

How your server reports a conversion (purchase or refund) to Influenzer so we can
attribute it to the right creator.

```
POST https://<host>/collect/event
Content-Type: application/json
```

You authenticate every request with an **HMAC-SHA256 signature** over the raw
request body. Get your **integration id** and **signing secret** from the
Influenzer dashboard (the secret is shown only once — store it securely; you can
rotate it any time).

---

## The two things integrators get wrong

1. **Sign the *raw* body bytes — the exact bytes you send.** Build the JSON string
   once, sign *that string*, and send *that same string*. Do **not** sign one
   object and then re-serialize a different one (key order/spacing/number format
   changes the bytes and the signature won't match).
2. **Send a fresh `X-Inflz-Timestamp`** (current unix seconds). Requests more than
   **5 minutes** off our clock are rejected.

---

## Headers

| Header | Value |
|---|---|
| `X-Inflz-Integration` | your integration id (`intg_...`) |
| `X-Inflz-Timestamp` | current time, unix **seconds** |
| `X-Inflz-Signature` | `hex( HMAC_SHA256(secret, "{timestamp}.{raw_body}") )` |

The signing string is the timestamp, a literal `.`, then the raw body.

---

## Payload

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

- `event_type` — `purchase` or `refund` (required)
- `order_id`, `occurred_at` — required
- `value`, `currency` — required for `purchase`
- `click_id`, `coupon_code` — each optional; send at least one so we can attribute
  (sending neither is accepted but credits no one)
- Refund: `{"event_type":"refund","order_id":"ORD-9982","occurred_at":"...","value":1499.00}`
  (`value` optional → full refund)

---

## Responses

| Code | Meaning | What you should do |
|---|---|---|
| `200` | Accepted (incl. duplicates) | Done — stop retrying |
| `400` | Malformed/incomplete JSON | Fix the payload; don't retry as-is |
| `401` | Auth failed (signature/timestamp) | Check secret, raw-body signing, clock |
| `403` | Not authorized for that campaign | The click/coupon isn't yours |
| `429` | Rate limited | Back off and retry later |
| `5xx` | Our error | Retry with backoff |

Duplicate `order_id`s are idempotent — safe to retry; we never double-count.

---

## curl

```bash
SECRET="your_signing_secret"
INTEGRATION="intg_xxxxxxxxxxxx"
TS=$(date +%s)
BODY='{"event_type":"purchase","order_id":"ORD-9982","value":1499.00,"currency":"INR","coupon_code":"MAYA10","occurred_at":"2026-06-14T14:31:00Z"}'
SIG=$(printf '%s.%s' "$TS" "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')

curl -sS -X POST https://<host>/collect/event \
  -H "Content-Type: application/json" \
  -H "X-Inflz-Integration: $INTEGRATION" \
  -H "X-Inflz-Timestamp: $TS" \
  -H "X-Inflz-Signature: $SIG" \
  --data "$BODY"
```

> Note `--data "$BODY"` sends exactly the bytes we signed.

---

## Python

```python
import hashlib, hmac, time, requests

SECRET = "your_signing_secret"
INTEGRATION = "intg_xxxxxxxxxxxx"

raw_body = (
    '{"event_type":"purchase","order_id":"ORD-9982","value":1499.00,'
    '"currency":"INR","coupon_code":"MAYA10","occurred_at":"2026-06-14T14:31:00Z"}'
)
ts = str(int(time.time()))
signature = hmac.new(
    SECRET.encode(), f"{ts}.{raw_body}".encode(), hashlib.sha256
).hexdigest()

resp = requests.post(
    "https://<host>/collect/event",
    data=raw_body,  # send the exact signed bytes
    headers={
        "Content-Type": "application/json",
        "X-Inflz-Integration": INTEGRATION,
        "X-Inflz-Timestamp": ts,
        "X-Inflz-Signature": signature,
    },
)
print(resp.status_code, resp.json())
```

---

## Node.js

```js
const crypto = require("crypto");

const SECRET = "your_signing_secret";
const INTEGRATION = "intg_xxxxxxxxxxxx";

const rawBody = JSON.stringify({
  event_type: "purchase",
  order_id: "ORD-9982",
  value: 1499.0,
  currency: "INR",
  coupon_code: "MAYA10",
  occurred_at: "2026-06-14T14:31:00Z",
});
const ts = Math.floor(Date.now() / 1000).toString();
const signature = crypto
  .createHmac("sha256", SECRET)
  .update(`${ts}.${rawBody}`)
  .digest("hex");

await fetch("https://<host>/collect/event", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Inflz-Integration": INTEGRATION,
    "X-Inflz-Timestamp": ts,
    "X-Inflz-Signature": signature,
  },
  body: rawBody, // send the exact signed string
});
```

> Build `rawBody` once with `JSON.stringify` and reuse it for *both* the signature
> and the request body — never stringify twice.
