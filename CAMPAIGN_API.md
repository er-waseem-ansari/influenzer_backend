# Influenzer — Campaign API

Frontend integration reference for the **brand** campaign-creation API. Built
from `CAMPAIGN_CREATION.md` (spec) + `CAMPAIGN_CREATION_PROMPT.md` (brief). For
auth/login flows see [`API_DOCUMENTATION.md`](./API_DOCUMENTATION.md).

- **Base URL:** `{BACKEND_URL}/api/v1` (local: `http://localhost:8000/api/v1`)
- **Content type:** `application/json` for all bodies.
- **Auth:** Bearer JWT in `Authorization` on every endpoint here.
- **Casing:** **camelCase** on the wire (requests *and* responses). snake_case is
  also accepted on input (lenient), but responses are always camelCase.
- **Unknown keys are rejected.** The request body uses `extra="forbid"` — sending
  a field that isn't in the schema (e.g. legacy `totalBudgetCap`, `utmSource`)
  returns a 422. Send only the documented fields.
- **Dates:** calendar dates as `YYYY-MM-DD` strings (e.g. `"2026-07-20"`).
- **Timestamps:** ISO-8601 UTC (e.g. `2026-06-11T10:15:00Z`).
- **IDs:** UUID strings. **Money:** numbers in ₹ (rupees).
- **Enums:** UPPERCASE wire values (see [Enums](#enums)).

---

## Table of contents

1. [Auth & roles](#auth--roles)
2. [Rate limits](#rate-limits)
3. [Error format](#error-format)
4. [Endpoints](#endpoints)
   - [POST /brand/campaigns](#post-brandcampaigns) — create
   - [POST /brand/campaigns/draft](#post-brandcampaignsdraft) — save draft
   - [GET /brand/campaigns](#get-brandcampaigns) — list
   - [GET /brand/campaigns/{id}](#get-brandcampaignsid) — fetch one
5. [Request body — full schema](#request-body--full-schema)
   - [Top level](#top-level)
   - [`track` (union)](#track-union)
   - [`promotion` (union)](#promotion-union)
   - [`sourcing` (union)](#sourcing-union)
   - [`compensation` (union)](#compensation-union)
   - [`fulfillment` (union)](#fulfillment-union)
   - [`audience`](#audience) · [`creative`](#creative) · [`timeline`](#timeline) · [`compliance`](#compliance) · [`kpiTargets`](#kpitargets)
6. [Server-derived fields (read-only)](#server-derived-fields-read-only)
7. [Conditional rules — what to send when](#conditional-rules--what-to-send-when)
8. [Validation rules (server-enforced)](#validation-rules-server-enforced)
9. [Enums](#enums)
10. [Full example payloads](#full-example-payloads)
11. [Design notes (backend)](#design-notes-backend)

---

## Auth & roles

Every endpoint requires `Authorization: Bearer <access_token>` and an active
brand membership.

| Action | Required role |
|---|---|
| Create campaign / save draft (writes) | `ADMIN` or `MANAGER` |
| List / fetch (reads) | any member (`ADMIN`, `MANAGER`, `VIEWER`) |

A `VIEWER` calling a write endpoint gets `403 FORBIDDEN`.

## Rate limits

Campaign **writes** (create + draft) are limited to **30 requests / 60 s per
user**. Exceeding it returns `429 TOO_MANY_REQUESTS`. Reads are not limited.

## Error format

All errors are **RFC 9457 Problem Details**, `Content-Type: application/problem+json`:

```json
{
  "type": "about:blank",
  "title": "Forbidden",
  "status": 403,
  "detail": "You do not have permission to modify this brand.",
  "instance": "/api/v1/brand/campaigns",
  "code": "FORBIDDEN"
}
```

**Validation errors (422)** aggregate every failure (not first-fail) under
`errors[]`, each with a dotted `field` path you can map back to the form:

```json
{
  "type": "about:blank",
  "title": "Unprocessable Entity",
  "status": 422,
  "detail": "One or more request parameters failed validation.",
  "instance": "/api/v1/brand/campaigns",
  "code": "VALIDATION_ERROR",
  "errors": [
    { "field": "creative.campaignDescription", "message": "String should have at least 20 characters", "type": "string_too_short" },
    { "field": "track.sales.buyPoint", "message": "Value error, buyPoint is required for a Performance campaign.", "type": "value_error" }
  ]
}
```

> The `field` path uses the **camelCase** keys and, for unions, points inside the
> chosen variant (e.g. `sourcing.platforms`, `track.promotion.scope.products.0.name`).

Common statuses: `401` (missing/expired token), `403` (role), `404` (campaign not
found / not your brand), `409` (idempotency/constraint conflict), `422`
(validation), `429` (rate limit).

---

## Endpoints

### POST /brand/campaigns

Create (launch) a campaign. The created campaign's `status` is `ACTIVE`.

**Headers**

| Header | Required | Notes |
|---|---|---|
| `Authorization: Bearer <token>` | yes | |
| `Idempotency-Key: <uuid>` | optional | Safe-retry key. Reuse the **same** key for retries of one submission; a repeat returns the original campaign instead of creating a duplicate. Generate once per submission, rotate only after success. |

**Body:** the full [campaign request](#request-body--full-schema).

**`201 Created`** → `CampaignCreatedResponse`:

```jsonc
{
  "campaign": { /* CampaignResponse — see below */ },
  "message": "Creators can now apply."
}
```

`message` is flow-specific:
- Marketplace → `"Creators can now apply."`
- BYOC (invite_existing) → `"Invites are being sent to your roster."`

`campaign` is the full [`CampaignResponse`](#fetch-response-campaignresponse),
which includes the server-[`derived`](#server-derived-fields-read-only) block
(attribution profile, headline KPIs, forced fee, etc.).

---

### POST /brand/campaigns/draft

Persist a **partial** campaign with relaxed validation (status `DRAFT`). Send any
subset of the campaign body — it is stored as-is; no field/cross-field rules are
enforced. Use this for "Save & exit" from any wizard step.

**Body:** any JSON object (the partial form state).

**`201 Created`** → `DraftResponse`:

```jsonc
{
  "id": "f1e2...",
  "brandId": "a9c8...",
  "status": "DRAFT",
  "title": "Glow Serum Launch",
  "data": { /* exactly what you sent */ },
  "createdAt": "2026-06-11T10:15:00Z",
  "updatedAt": "2026-06-11T10:15:00Z"
}
```

`title` is best-effort (top-level `title` or `creative.title` if present).

> Drafts are **not** returned by `GET /brand/campaigns/{id}` (that endpoint
> rebuilds a fully-normalized campaign and a bare draft has nothing to rebuild).
> Re-submit the draft `data` to `POST /brand/campaigns` to launch.

---

### GET /brand/campaigns

List the brand's campaigns (newest first). This powers the **campaign list page** —
each item carries everything the list table renders: heading + subheading, status,
track, spend, results, influencers, and the end date.

**Query params**

| Param | Type | Default | Notes |
|---|---|---|---|
| `track` | enum | — | `AWARENESS` \| `PERFORMANCE` |
| `status` | enum | — | `DRAFT` \| `ACTIVE` \| `PAUSED` \| `COMPLETED` \| `ARCHIVED` |
| `limit` | int | `20` | 1–100 |
| `offset` | int | `0` | ≥ 0 |

`track` and `status` are independent filters (omit either to skip it). Pagination
is `limit`/`offset`; `total` is the unpaginated count for the current filters.

**`200 OK`** → `CampaignListResponse`:

```json
{
  "items": [
    {
      "id": "f1e2...",
      "title": "Glow Serum Launch",
      "subheading": "Hook in the first 3 seconds with the glow result.",
      "track": "PERFORMANCE",
      "visibility": "MARKETPLACE",
      "status": "ACTIVE",
      "spend": { "amount": 0, "currency": "USD" },
      "results": { "revenue": 0, "roas": 0, "clicks": null, "cvr": null },
      "influencers": { "joined": 0, "target": 10 },
      "liveStart": "2026-07-20",
      "liveEnd": "2026-07-30",
      "createdAt": "2026-06-11T10:15:00Z"
    },
    {
      "id": "b7a4...",
      "title": "Brand Buzz",
      "subheading": "Talk about the vibe and feeling.",
      "track": "AWARENESS",
      "visibility": "INVITE_EXISTING",
      "status": "PAUSED",
      "spend": { "amount": 0, "currency": "USD" },
      "results": { "revenue": null, "roas": null, "clicks": 0, "cvr": 0 },
      "influencers": { "joined": 0, "target": 5 },
      "liveStart": "2026-08-05",
      "liveEnd": "2026-08-15",
      "createdAt": "2026-06-10T09:00:00Z"
    }
  ],
  "total": 2,
  "limit": 20,
  "offset": 0
}
```

#### List item (`CampaignListItem`) — field → column map

| Field | Type | List column | Notes |
|---|---|---|---|
| `id` | UUID | (row key) | Use for the row link → `GET /brand/campaigns/{id}`. |
| `title` | string \| null | **Heading** | The campaign title (`creative.title`). `null` only for bare drafts. |
| `subheading` | string \| null | **Subheading** | The creative's `keyMessaging` line; `null` if not set (e.g. bare drafts). |
| `status` | enum | **Status** | `DRAFT`, `ACTIVE`, `PAUSED`, `COMPLETED`, `ARCHIVED`. |
| `track` | enum \| null | **Track** | `PERFORMANCE` or `AWARENESS`. Render as *Performance* / *Awareness*. `null` for bare drafts. |
| `spend` | object | **Spend** | `{ amount: number, currency: string }`. Total money spent so far. |
| `results` | object | **Results** | Always 4 keys; **only two are populated per row** (see below). |
| `influencers` | object | **Influencers** | `{ joined: int, target: int\|null }` → render `joined/target` (e.g. `18/17`). `target` is `maxInfluencers`. |
| `liveEnd` | date \| null | **Ends** | Campaign end date (`YYYY-MM-DD`). `null` for bare drafts. |
| `visibility` | enum \| null | — | `MARKETPLACE` / `INVITE_EXISTING`. Extra context (not a listed column). |
| `liveStart` | date \| null | — | Campaign start date. |
| `createdAt` | datetime | — | Creation timestamp. |

**`results` — which two fields are populated**

The object always has all four keys; the two that don't apply to the row's track
are `null`. Render whichever pair is non-null.

| Track | Populated pair | `null` pair |
|---|---|---|
| `PERFORMANCE` | `revenue` (number, ₹/currency) + `roas` (multiplier, e.g. `3.5`) | `clicks`, `cvr` |
| `AWARENESS` | `clicks` (int) + `cvr` (conversion rate, **percent** e.g. `2.4`) | `revenue`, `roas` |
| `null`/draft | — (all four `null`) | all |

```jsonc
// performance row
"results": { "revenue": 125000, "roas": 4.2, "clicks": null, "cvr": null }
// awareness row
"results": { "revenue": null, "roas": null, "clicks": 8421, "cvr": 2.4 }
```

> **Placeholders today.** `spend.amount`, every populated `results` value, and
> `influencers.joined` are currently returned as **0** — they are wired structurally
> but have no actuals source yet (no billing/metrics-actuals pipeline and no
> participation/roster model). The **shape is final**, so build the UI against it
> now; the numbers go live when those pipelines land. `influencers.target` and
> `liveEnd` are real today. `spend.currency` defaults to `"USD"` until per-brand
> currency settings exist.

---

### GET /brand/campaigns/{id}

Fetch one campaign (scoped to the caller's brand). `404` if not found or not yours.

**`200 OK`** → [`CampaignResponse`](#fetch-response-campaignresponse).

#### Fetch response (`CampaignResponse`)

Mirrors the request body (same nested shape) plus server fields:

```jsonc
{
  "id": "f1e2...",
  "brandId": "a9c8...",
  "status": "ACTIVE",
  "title": "Glow Serum Launch",
  "niches": ["Beauty", "Skincare"],
  "maxInfluencers": 10,
  "coverImage": { "name": "banner.png", "size": 84211, "type": "image/png" },
  "track":        { /* same shape you sent */ },
  "sourcing":     { /* ... */ },
  "compensation": { /* ... */ },
  "fulfillment":  { /* ... */ },
  "audience":     { /* ... */ },
  "creative":     { /* ... */ },
  "timeline":     { /* ... */ },
  "compliance":   { /* ... */ } ,   // null when BYOC + bypass
  "kpiTargets":   { "roas": 3.5, "revenue": 100000 },
  "derived":      { /* server-computed, read-only — see below */ },
  "createdAt": "2026-06-11T10:15:00Z",
  "updatedAt": "2026-06-11T10:15:00Z"
}
```

---

## Request body — full schema

The body is **normalized & nested** (not the flat wizard form). It assembles
four discriminated unions + simple blocks.

> **How unions work:** each union object carries a **tag field** that selects the
> variant. Send the tag plus that variant's fields. Tags:
> `track.track`, `sourcing.visibility`, `track.promotion.promotionType`
> (+ nested `scope.promotionScope` for physical), `compensation.compensationModel`,
> `fulfillment.provisionType`.

### Top level

| Field | Type | Required | Constraints / notes |
|---|---|---|---|
| `niches` | string[] | **yes** | ≥1; each ≤100 chars. Free tags (suggestions in [Enums](#enums)). |
| `maxInfluencers` | int | **yes** | ≥1. Hard cap on approved creators. |
| `coverImage` | [FileAsset](#fileasset) \| null | no | Banner image metadata. |
| `track` | [Track union](#track-union) | **yes** | |
| `sourcing` | [Sourcing union](#sourcing-union) | **yes** | |
| `compensation` | [Compensation union](#compensation-union) | **yes** | |
| `fulfillment` | [Fulfillment union](#fulfillment-union) | **yes** | |
| `audience` | [audience](#audience) | **yes** | (object may be `{}`) |
| `creative` | [creative](#creative) | **yes** | |
| `timeline` | [timeline](#timeline) | **yes** | |
| `compliance` | [compliance](#compliance) \| null | conditional | Required **unless** BYOC + `contractBypassAcknowledged: true`. |
| `kpiTargets` | object | no | `{ metricId: number≥0 }`; see [kpiTargets](#kpitargets). |

#### FileAsset
`{ "name": string(≤255), "size": int≥0, "type": string(≤100) }` — file metadata
only; upload the binary via your file pipeline separately.

---

### `track` (union)

Tag: **`track`** = `AWARENESS` | `PERFORMANCE`.

**AWARENESS** — pure content play.

| Field | Type | Required | Notes |
|---|---|---|---|
| `track` | `"AWARENESS"` | yes | |
| `describeProduct` | bool | no (default `true`) | If `false`, omit `promotion`. |
| `destinationUrl` | string (URL) | no | Optional clickable destination. ≤500 chars. |
| `promotion` | [Promotion](#promotion-union) \| null | no | Must be omitted when `describeProduct=false`. |

**PERFORMANCE** — sends people to a destination, always Sales.

| Field | Type | Required | Notes |
|---|---|---|---|
| `track` | `"PERFORMANCE"` | yes | |
| `destinationUrl` | string (URL) | **yes** | Must be a valid http(s) URL. ≤500. |
| `promotion` | [Promotion](#promotion-union) | **yes** | |
| `sales` | object | yes (defaults `{}`) | See below. |

`sales`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `buyPoint` | enum | conditional | **Required** unless `promotionType=MOBILE_APP` (must be **omitted** for mobile app). Values: `SHOPIFY`,`WOOCOMMERCE`,`CUSTOM`,`MARKETPLACE`. |
| `coupon` | object | no (defaults disabled) | `{ enabled: bool, discountPercent: int 0–100, discountLabel: string≤50 }`. `discountPercent` **required when `enabled=true`**. Per-creator codes are minted later. |

---

### `promotion` (union)

Tag: **`promotionType`** = `PHYSICAL_PRODUCT` | `MOBILE_APP` | `WEBSITE_SAAS`.

**PHYSICAL_PRODUCT** — has a nested union on **`scope.promotionScope`**:

```jsonc
// single product
{ "promotionType": "PHYSICAL_PRODUCT",
  "scope": { "promotionScope": "SINGLE_PRODUCT", "products": [ /* 1–50 */ ] } }
// whole store
{ "promotionType": "PHYSICAL_PRODUCT",
  "scope": { "promotionScope": "STORE_CATALOG", "store": { /* ... */ } } }
```

`products[]` item:

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | 1–200 |
| `category` | enum [ProductCategory](#productcategory) | yes | |
| `price` | number | yes | ≥0 (₹) |
| `productUrl` | string (URL) | yes | ≤500 |
| `keyFeatures` | string | no | ≤1000, comma-separated |
| `description` | string | yes | 1–5000 |

`store`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `storeName` | string | yes | 1–200 |
| `category` | enum [ProductCategory](#productcategory) | yes | |
| `collections` | string | no | ≤1000 |
| `priceRange` | string | no | ≤100 |
| `description` | string | yes | 1–5000 |

**MOBILE_APP** — `{ "promotionType": "MOBILE_APP", "details": { ... } }`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | 1–200 |
| `platform` | enum | yes | `IOS`,`ANDROID`,`BOTH` |
| `appCategory` | enum [AppCategory](#appcategory) | no | |
| `appStoreUrl` | string (URL) | no | ≤500 |
| `playStoreUrl` | string (URL) | no | ≤500 |
| `pricingModel` | enum | yes | `FREE`,`FREEMIUM`,`PAID`,`SUBSCRIPTION`,`IN_APP_PURCHASES` |
| `primaryAction` | enum | yes | `INSTALL`,`SIGN_UP`,`PURCHASE` |
| `description` | string | yes | 1–5000 |

**WEBSITE_SAAS** — `{ "promotionType": "WEBSITE_SAAS", "details": { ... } }`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | 1–200 |
| `audience` | enum | no | `B2B`,`B2C`,`BOTH` |
| `pricingModel` | enum | yes | `FREE`,`FREEMIUM`,`FREE_TRIAL`,`SUBSCRIPTION`,`ONE_TIME` |
| `startingPrice` | string | no | ≤100 |
| `freeTrialDays` | int | no | 0–365 |
| `primaryAction` | enum | yes | `SIGN_UP`,`START_FREE_TRIAL`,`BOOK_A_DEMO`,`PURCHASE` |
| `description` | string | yes | 1–5000 |

---

### `sourcing` (union)

Tag: **`visibility`** = `MARKETPLACE` | `INVITE_EXISTING`.

**MARKETPLACE**:

| Field | Type | Required | Notes |
|---|---|---|---|
| `visibility` | `"MARKETPLACE"` | yes | |
| `platforms` | enum[] [Platform](#platform) | **yes** | ≥1, unique |
| `tiers` | enum[] [InfluencerTier](#influencertier) | **yes** | ≥1, unique |
| `minEngagement` | number | no | 0–20 (%) |
| `creatorGender` | enum | no | `ANY`,`FEMALE`,`MALE`,`NON_BINARY` |
| `creatorAgeMin` | int | no | 13–80 |
| `creatorAgeMax` | int | no | 13–80; ≥ `creatorAgeMin` |
| `creatorNiches` | string[] | no | free tags, each ≤100 |
| `creatorLocations` | string[] | no | free tags, each ≤100 |
| `applicationStart` | date | **yes** | |
| `applicationEnd` | date | **yes** | ≥ `applicationStart` |
| `joinType` | enum | **yes** | `OPEN`,`APPROVAL` |

**INVITE_EXISTING** (BYOC):

| Field | Type | Required | Notes |
|---|---|---|---|
| `visibility` | `"INVITE_EXISTING"` | yes | |
| `inviteRoster` | object[] | **yes** | 1–500 entries, unique emails |
| `welcomeMessage` | string | no | ≤2000 |
| `contractBypassAcknowledged` | bool | no (default `false`) | If `true`, **skip** `compliance`. |

`inviteRoster[]` item:

| Field | Type | Required | Notes |
|---|---|---|---|
| `email` | string (email) | yes | |
| `customRate` | number | no | ≥0 (₹) per-creator override |
| `customCommissionPct` | number | no | 0–100 |
| `welcomeNote` | string | no | ≤2000 |

---

### `compensation` (union)

Tag: **`compensationModel`** = `FLAT` | `AFFILIATE` | `HYBRID`.
> Only `FLAT` is allowed for **Awareness** campaigns. Affiliate/Hybrid require a
> Performance track.

**FLAT** — `{ "compensationModel": "FLAT", "fixedFeePerCreator": number≥0 }`

**AFFILIATE** — `{ "compensationModel": "AFFILIATE", "commission": { ... } }`
> Do **not** send `fixedFeePerCreator` — the server forces it to `0`
> (commission-only).

**HYBRID** — `{ "compensationModel": "HYBRID", "fixedFeePerCreator": number≥0, "commission": { ... } }`

`commission` (required for AFFILIATE/HYBRID):

| Field | Type | Required | Notes |
|---|---|---|---|
| `commissionType` | enum | yes | `PERCENTAGE`,`FLAT` |
| `commissionValue` | number | yes | ≥0 (₹ if flat, % if percentage) |
| `cookieWindow` | enum | yes | `24H`,`7D`,`30D`,`60D` |
| `promoCodeDiscount` | int | yes | 0–100 (buyer % off; promo is mandatory for affiliate) |
| `promoCodePrefix` | string | no | ≤30 (e.g. `"CREATOR"`) |
| `subscriptionCommissionDuration` | enum | no | Reserved/unused now (`affiliateModel` is pinned `ONE_TIME`). |

---

### `fulfillment` (union)

Tag: **`provisionType`** = `PRODUCT` | `SUBSCRIPTION` | `SERVICE` | `NONE`.

**PRODUCT**:

| Field | Type | Required | Notes |
|---|---|---|---|
| `provisionType` | `"PRODUCT"` | yes | |
| `productVariants` | string[] | no | sizes/colors/styles |
| `shippingScope` | enum | no | `DOMESTIC`,`INTERNATIONAL`,`BOTH` |
| `shippingCountries` | string[] | no | empty = all |
| `estimatedDeliveryDays` | int | no | 0–60 |

**SUBSCRIPTION**:

| Field | Type | Required | Notes |
|---|---|---|---|
| `provisionType` | `"SUBSCRIPTION"` | yes | |
| `subscriptionPlan` | string | no | ≤200 |
| `subscriptionDuration` | enum | no | `1M`,`3M`,`6M`,`12M`,`LIFETIME` |
| `subscriptionSeats` | int | no (default `1`) | 1–100 |
| `subscriptionAccessMethod` | enum | **yes** | `PROMO_CODE`,`MANUAL_INVITE`,`LICENSE_KEY` |

**SERVICE** — `{ "provisionType": "SERVICE", "serviceProvisionNote": string≤2000 }`

**NONE** — `{ "provisionType": "NONE" }`

---

### `audience`

All optional (send `{}` to skip). Collected for **both** flows.

| Field | Type | Notes |
|---|---|---|
| `audienceAgeMin` | int | 13–65 |
| `audienceAgeMax` | int | 13–65; ≥ `audienceAgeMin` |
| `audienceGender` | enum | `ANY`,`FEMALE`,`MALE`,`BALANCED` |
| `audienceInterests` | string[] | free tags, each ≤100 |

### `creative`

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | string | **yes** | 3–200. This is the campaign title. |
| `campaignDescription` | string | **yes** | 20–5000 |
| `deliverables` | object[] | **yes** | ≥1; each `{ type: `[DeliverableType](#deliverabletype)`, quantity: int 1–20 }`; type unique |
| `keyMessaging` | string | **yes** | 10–5000 |
| `dos` | string[] | no | free tags |
| `donts` | string[] | no | free tags |
| `cta` | string | **yes** | 2–300 |
| `mediaAssets` | [FileAsset](#fileasset)[] | no | ≤20 |
| `preApprovalRequired` | bool | no (default `false`) | |

### `timeline`

| Field | Type | Required | Notes |
|---|---|---|---|
| `contentSubmissionDeadline` | date | **yes** | ≤ `liveStart` |
| `liveStart` | date | **yes** | |
| `liveEnd` | date | **yes** | ≥ `liveStart` |

> The marketplace **application window** (`applicationStart`/`applicationEnd`) and
> `joinType` live on the [`sourcing` marketplace variant](#sourcing-union), not here.

### `compliance`

Required unless BYOC + `contractBypassAcknowledged: true` (then send `null`/omit).

| Field | Type | Required | Notes |
|---|---|---|---|
| `usageRightsScope` | enum[] [UsageRight](#usageright) | **yes** | ≥1, unique |
| `usageRightsDuration` | enum | **yes** | `30D`,`90D`,`1Y`,`PERPETUAL` |
| `exclusivityWindowDays` | int | no (default `0`) | one of `0,15,30,60,90` |
| `complianceAcknowledged` | bool | **yes** | must be `true` |

### `kpiTargets`

Optional map `{ metricId: number≥0 }`. Keys must be known metric ids; unknown
keys → 422. Available metric ids:

`reach`, `impressions`, `engagement`, `engagementRate`, `views`, `cpm`, `emv`,
`sharesSaves`, `clicks`, `uniqueClicks`, `ctr`, `cpc`, `geo`, `device`, `orders`,
`revenue`, `roas`, `cpa`, `aov`, `conversionRate`, `codeRedemptions`, `installs`,
`inAppPurchases`, `cpi`, `commissionOwed`.

> Use `derived.headlineKpis` / `derived.measuredMetrics` (from a prior fetch, or
> compute the same logic) to decide which inputs to surface. Leads metrics are
> descoped.

---

## Server-derived fields (read-only)

Returned under `campaign.derived`. **Never send these** — the server computes
them and ignores/forbids client values.

| Field | Type | Meaning |
|---|---|---|
| `affiliateEnabled` | bool | `true` when `compensationModel ≠ FLAT` |
| `affiliateModel` | enum \| null | Pinned `ONE_TIME` when affiliate; `null` for flat |
| `promoCodeEnabled` | bool | Forced `true` when affiliate |
| `giftingEnabled` | bool | `true` when `provisionType ≠ NONE` |
| `fixedFeePerCreator` | number | Effective fee (forced `0` for `AFFILIATE`) |
| `attributionProfile` | object | `{ verifiedAvailable, unlockingIntegration, verifiedAtLaunch, note }` — whether/how verified conversion data can be unlocked. Marketplace buy-point → never verifiable; Sales is always deferred to post-launch connect. |
| `headlineKpis` | string[] | Headline metric ids for this campaign |
| `measuredMetrics` | string[] | All metric ids this campaign can surface |

---

## Conditional rules — what to send when

| Situation | Send |
|---|---|
| Track = `AWARENESS`, no product | `track.describeProduct=false`, omit `promotion`; `destinationUrl` optional; `compensation` must be `FLAT` |
| Track = `AWARENESS`, with product | `describeProduct=true` (or omit) + `promotion` |
| Track = `PERFORMANCE` | `destinationUrl` (required), `promotion` (required), `sales` |
| `promotion = MOBILE_APP` | **omit** `sales.buyPoint` |
| `promotion ≠ MOBILE_APP` (performance) | `sales.buyPoint` required |
| `sourcing = MARKETPLACE` | targeting fields + `applicationStart/End` + `joinType` |
| `sourcing = INVITE_EXISTING` | `inviteRoster` (≥1); `compliance` optional iff `contractBypassAcknowledged=true` |
| `compensation = AFFILIATE` | omit `fixedFeePerCreator`; send `commission` |
| `compensation = HYBRID` | `fixedFeePerCreator` + `commission` |
| `fulfillment = SUBSCRIPTION` | `subscriptionAccessMethod` required |
| coupon on (performance) | `sales.coupon.enabled=true` + `discountPercent` |

---

## Validation rules (server-enforced)

The server re-checks everything; never rely on client validation alone.

1. `destinationUrl` required & valid for Performance; if present on any track, must be a valid http(s) URL.
2. Promotion required for Performance; per-type/scope required fields enforced.
3. `sales.buyPoint` required for Performance **except** `MOBILE_APP` (where it must be absent).
4. `niches` ≥1.
5. `creative.campaignDescription` ≥20; `keyMessaging` ≥10; `cta` ≥2; `title` ≥3.
6. `deliverables` ≥1 (type unique; quantity 1–20).
7. Marketplace: `platforms` ≥1, `tiers` ≥1, `creatorAgeMax ≥ creatorAgeMin`, `applicationEnd ≥ applicationStart`, `joinType` set.
8. `audienceAgeMax ≥ audienceAgeMin`.
9. Affiliate/Hybrid: `commissionType`,`commissionValue`,`cookieWindow`,`promoCodeDiscount` required.
10. Subscription provisioning: `subscriptionAccessMethod` required.
11. Compliance trio (`usageRightsScope`≥1, `usageRightsDuration`, `complianceAcknowledged=true`) — unless BYOC + bypass.
12. Timeline: `contentSubmissionDeadline ≤ liveStart`; `liveEnd ≥ liveStart`.
13. `maxInfluencers` ≥1.
14. BYOC: `inviteRoster` ≥1, unique emails.
15. Awareness ⇒ `compensationModel = FLAT`.
16. Coupon enabled ⇒ `discountPercent` set.
17. Unknown/extra fields ⇒ 422 (`extra="forbid"`).

---

## Enums

All wire values are **UPPERCASE** (the special values below keep their literal
form, e.g. `30D`, `24H`, `1Y`, `1M`).

| Enum | Values |
|---|---|
| Track (`track.track`) | `AWARENESS`, `PERFORMANCE` |
| Visibility (`sourcing.visibility`) | `MARKETPLACE`, `INVITE_EXISTING` |
| Campaign status | `DRAFT`, `ACTIVE`, `PAUSED`, `COMPLETED`, `ARCHIVED` |
| <a id="platform"></a>Platform | `IG_REELS`, `IG_STORIES`, `IG_POSTS`, `TIKTOK`, `YT_DEDICATED`, `YT_SHORTS`, `LINKEDIN` |
| <a id="influencertier"></a>InfluencerTier | `NANO`, `MICRO`, `MIDTIER`, `MACRO` |
| CreatorGender | `ANY`, `FEMALE`, `MALE`, `NON_BINARY` |
| JoinType | `OPEN`, `APPROVAL` |
| AudienceGender | `ANY`, `FEMALE`, `MALE`, `BALANCED` |
| <a id="deliverabletype"></a>DeliverableType | `IG_REEL`, `IG_STORY`, `IG_POST`, `TIKTOK_VIDEO`, `YT_DEDICATED`, `YT_SHORTS`, `LINKEDIN_POST` |
| <a id="usageright"></a>UsageRight | `ORGANIC_REPOST`, `PAID_WHITELIST`, `SPARK_ADS`, `WEBSITE` |
| UsageDuration | `30D`, `90D`, `1Y`, `PERPETUAL` |
| ExclusivityWindowDays | `0`, `15`, `30`, `60`, `90` (int) |
| PromotionType | `PHYSICAL_PRODUCT`, `MOBILE_APP`, `WEBSITE_SAAS` |
| PromotionScope | `SINGLE_PRODUCT`, `STORE_CATALOG` |
| <a id="productcategory"></a>ProductCategory | `APPAREL_FASHION`, `BEAUTY_SKINCARE`, `ELECTRONICS_GADGETS`, `FOOD_BEVERAGE`, `HOME_LIVING`, `HEALTH_SUPPLEMENTS`, `TOYS_BABY`, `JEWELLERY_ACCESSORIES`, `OTHER` |
| MobileAppPlatform | `IOS`, `ANDROID`, `BOTH` |
| <a id="appcategory"></a>AppCategory | `HEALTH_FITNESS`, `FINANCE`, `PRODUCTIVITY`, `SOCIAL`, `GAMING`, `EDUCATION`, `SHOPPING`, `FOOD_DRINK`, `TRAVEL`, `OTHER` |
| AppPricingModel | `FREE`, `FREEMIUM`, `PAID`, `SUBSCRIPTION`, `IN_APP_PURCHASES` |
| AppPrimaryAction | `INSTALL`, `SIGN_UP`, `PURCHASE` |
| SaasAudience | `B2B`, `B2C`, `BOTH` |
| SaasPricingModel | `FREE`, `FREEMIUM`, `FREE_TRIAL`, `SUBSCRIPTION`, `ONE_TIME` |
| SaasPrimaryAction | `SIGN_UP`, `START_FREE_TRIAL`, `BOOK_A_DEMO`, `PURCHASE` |
| BuyPoint (`sales.buyPoint`) | `SHOPIFY`, `WOOCOMMERCE`, `CUSTOM`, `MARKETPLACE` |
| Integration (derived) | `SHOPIFY`, `WOOCOMMERCE`, `PIXEL`, `POSTBACK`, `MMP`, `CRM` |
| CompensationModel | `FLAT`, `AFFILIATE`, `HYBRID` |
| CommissionType | `PERCENTAGE`, `FLAT` |
| CookieWindow | `24H`, `7D`, `30D`, `60D` |
| AffiliateModel (derived) | `ONE_TIME`, `SUBSCRIPTION`, `BOTH` (currently always `ONE_TIME`) |
| SubscriptionCommissionDuration | `FIRST_ONLY`, `3M`, `6M`, `12M`, `LIFETIME` |
| ProvisionType | `PRODUCT`, `SUBSCRIPTION`, `SERVICE`, `NONE` |
| ShippingScope | `DOMESTIC`, `INTERNATIONAL`, `BOTH` |
| SubscriptionAccessMethod | `PROMO_CODE`, `MANUAL_INVITE`, `LICENSE_KEY` |
| SubscriptionDuration | `1M`, `3M`, `6M`, `12M`, `LIFETIME` |

**Niche suggestions** (free tags, not enforced): `Skincare, Beauty, Fashion,
Fitness, Wellness, Food, Tech, Gaming, Edtech, Lifestyle, Parenting, Travel,
Finance, B2B SaaS, Other`.

---

## Full example payloads

### A) Performance · Marketplace · Physical single-product · Affiliate

```json
{
  "niches": ["Beauty", "Skincare"],
  "maxInfluencers": 10,
  "coverImage": { "name": "banner.png", "size": 84211, "type": "image/png" },
  "track": {
    "track": "PERFORMANCE",
    "destinationUrl": "https://brand.com/serum",
    "promotion": {
      "promotionType": "PHYSICAL_PRODUCT",
      "scope": {
        "promotionScope": "SINGLE_PRODUCT",
        "products": [{
          "name": "Vitamin C Serum",
          "category": "BEAUTY_SKINCARE",
          "price": 1899,
          "productUrl": "https://brand.com/serum",
          "keyFeatures": "Brightening, Vegan",
          "description": "A great serum for glowing skin."
        }]
      }
    },
    "sales": {
      "buyPoint": "SHOPIFY",
      "coupon": { "enabled": true, "discountPercent": 15, "discountLabel": "15% OFF" }
    }
  },
  "sourcing": {
    "visibility": "MARKETPLACE",
    "platforms": ["IG_REELS", "TIKTOK"],
    "tiers": ["NANO", "MICRO"],
    "minEngagement": 2.5,
    "creatorGender": "FEMALE",
    "creatorAgeMin": 18,
    "creatorAgeMax": 35,
    "creatorNiches": ["Skincare"],
    "creatorLocations": ["India"],
    "applicationStart": "2026-07-01",
    "applicationEnd": "2026-07-10",
    "joinType": "APPROVAL"
  },
  "compensation": {
    "compensationModel": "AFFILIATE",
    "commission": {
      "commissionType": "PERCENTAGE",
      "commissionValue": 12,
      "cookieWindow": "30D",
      "promoCodeDiscount": 15,
      "promoCodePrefix": "CREATOR"
    }
  },
  "fulfillment": {
    "provisionType": "PRODUCT",
    "productVariants": ["30ml", "50ml"],
    "shippingScope": "DOMESTIC",
    "shippingCountries": ["India"],
    "estimatedDeliveryDays": 5
  },
  "audience": {
    "audienceAgeMin": 18,
    "audienceAgeMax": 35,
    "audienceGender": "FEMALE",
    "audienceInterests": ["skincare", "beauty"]
  },
  "creative": {
    "title": "Glow Serum Launch",
    "campaignDescription": "Drive trial of our new vitamin C serum with honest reviews.",
    "deliverables": [{ "type": "IG_REEL", "quantity": 2 }],
    "keyMessaging": "Hook in the first 3 seconds with the glow result.",
    "dos": ["Show the texture"],
    "donts": ["No competitor mentions"],
    "cta": "Shop now",
    "mediaAssets": [{ "name": "logo.png", "size": 12000, "type": "image/png" }],
    "preApprovalRequired": true
  },
  "timeline": {
    "contentSubmissionDeadline": "2026-07-15",
    "liveStart": "2026-07-20",
    "liveEnd": "2026-07-30"
  },
  "compliance": {
    "usageRightsScope": ["ORGANIC_REPOST", "SPARK_ADS"],
    "usageRightsDuration": "90D",
    "exclusivityWindowDays": 30,
    "complianceAcknowledged": true
  },
  "kpiTargets": { "roas": 3.5, "revenue": 100000 }
}
```

### B) Awareness · BYOC (contract bypass, no compliance) · Flat

```json
{
  "niches": ["Lifestyle"],
  "maxInfluencers": 5,
  "track": { "track": "AWARENESS", "describeProduct": false },
  "sourcing": {
    "visibility": "INVITE_EXISTING",
    "inviteRoster": [
      { "email": "a@creator.com" },
      { "email": "c@creator.com", "customRate": 500 }
    ],
    "welcomeMessage": "Excited to work with you!",
    "contractBypassAcknowledged": true
  },
  "compensation": { "compensationModel": "FLAT", "fixedFeePerCreator": 2000 },
  "fulfillment": { "provisionType": "NONE" },
  "audience": {},
  "creative": {
    "title": "Brand Buzz",
    "campaignDescription": "Pure awareness content play for our brand.",
    "deliverables": [{ "type": "IG_STORY", "quantity": 1 }],
    "keyMessaging": "Talk about the vibe and feeling.",
    "cta": "Follow us"
  },
  "timeline": {
    "contentSubmissionDeadline": "2026-08-01",
    "liveStart": "2026-08-05",
    "liveEnd": "2026-08-15"
  }
}
```

### C) Performance · Mobile app (no buyPoint)

```jsonc
{
  // ...niches, maxInfluencers, sourcing, compensation, fulfillment,
  //    audience, creative, timeline, compliance as needed...
  "track": {
    "track": "PERFORMANCE",
    "destinationUrl": "https://apps.apple.com/app/fitapp",
    "promotion": {
      "promotionType": "MOBILE_APP",
      "details": {
        "name": "FitApp",
        "platform": "IOS",
        "pricingModel": "FREEMIUM",
        "primaryAction": "INSTALL",
        "description": "A fitness tracking app."
      }
    },
    "sales": {}        // no buyPoint for mobile apps
  }
}
```

---

## Design notes (backend)

Built to the existing codebase conventions, not the prompt's idealized stack:

| Prompt suggested | This codebase (followed) |
|---|---|
| async SQLAlchemy | **sync** SQLAlchemy 2.0 (psycopg2) |
| Alembic | **`create_tables.py`** drop+recreate (no Alembic) |
| lowercase slug enums | **UPPERCASE** wire/DB enum values |

- **Four discriminated unions** (Pydantic v2 `Field(discriminator=...)`): track,
  sourcing, promotion (physical nests a second union on `promotionScope`),
  compensation. Plus a fulfillment union.
- **Normalized, not flat** — `extra="forbid"` drops the no-UI cruft fields
  (`totalBudgetCap`, `utmSource`, `baseAffiliateUrl`, …).
- **Leads descoped** — Performance always = Sales.
- **Derived server-side, never trusted** — see [derived fields](#server-derived-fields-read-only).
- **Persistence**: queryable scalars as columns; polymorphic detail as typed
  JSONB blobs, each validated by its Pydantic model on write and re-validated on read.
- **Files** (`coverImage`, `mediaAssets`) stored as `{name,size,type}` metadata;
  binary upload pipeline is separate.

### Spec section → module map

| Spec | Module |
|---|---|
| §1/§3 Track union | `app/schemas/campaign/track.py` |
| §2/§3 Sourcing union | `app/schemas/campaign/sourcing.py` |
| §5 Promotion union | `app/schemas/campaign/promotion.py` |
| §3.11 Compensation union | `app/schemas/campaign/compensation.py` |
| §3.7 Fulfillment union | `app/schemas/campaign/fulfillment.py` |
| §3.4/§3.6/§3.8/§3.10 simple blocks | `audience.py` / `creative.py` / `compliance.py` / `timeline.py` |
| §5 enums · §5 buy-point config · §6 metrics | `enums.py` / `catalog.py` / `metrics.py` |
| §7 cross-block validation | `requests.py` + per-variant validators |
| §8 derivation + attribution | `app/services/campaign_derivation.py`, `derived.py` |
| §9 responses / routes | `responses.py`, `app/api/v1/brand/campaigns.py` |
| Persistence | `app/models/campaign.py`, `app/services/campaign_service.py` |

### Schema / tests

```bash
python create_tables.py          # create the campaigns table (drop first to re-create)
python -m pytest tests/ -q       # §7 validation matrix, §8 derivations, union round-trips
```
