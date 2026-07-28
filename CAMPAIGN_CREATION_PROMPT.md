# Claude Code Prompt — Campaign Creation API (FastAPI, Python)

Build the **campaign-creation API** for Influenzer. Source of truth for fields/options/validation is the
attached `Campaign Creation — Full Specification`. **Do not blindly mirror the frontend's flat form
shape** — normalize it into a clean domain model. Follow the corrections and architecture below exactly.

## Stack & standards

- Python 3.12, **FastAPI**, **Pydantic v2**, **SQLAlchemy 2.0** (or SQLModel), **PostgreSQL**, Alembic
  migrations. Async throughout (async SQLAlchemy).
- Layered architecture, strict separation — no business logic in route handlers, no ORM objects
  leaking past the service layer.
- Full type hints; no `Any`-typed JSON bags in the domain (see "type the variants" below).
- Server-authoritative validation: re-implement **every** rule in spec §7; never trust the client.

## Layering (create these layers, do not collapse them)

```
app/
  api/campaigns.py          # routes only: parse → call service → return response
  schemas/campaign/         # Pydantic request/response models + discriminated unions + validation
  domain/campaign/          # normalized internal models + the derived business logic (§8)
  db/models/campaign.py     # SQLAlchemy tables
  db/repositories/          # persistence; maps domain <-> ORM
  services/campaign.py      # create-campaign use case orchestration
  core/                     # config, db session, errors
```

Flow for POST: route → request schema (validate) → service (normalize → derive §8 → persist via repo →
build response schema).

## Model the four discriminated unions (this is the core requirement)

Use Pydantic v2 **tagged unions** (`Field(discriminator=...)`). These replace ~80 flat nullable fields.

1. **Track** — `AwarenessTrack | PerformanceTrack` on `track`.
   - Awareness: optional `destination_url`, optional product (`describe_product` gate), no buy-point.
   - Performance: **required** `destination_url`, required `promotion`, required `sales` config (buy-point).
2. **Sourcing** — `MarketplaceSourcing | ByocSourcing` on `visibility`.
   - Marketplace: targeting (platforms, tiers, engagement, creator demographics, locations), application
     window, `join_type`.
   - BYOC: `invite_roster[]`, `welcome_message`, `contract_bypass_acknowledged`.
3. **Promotion** — `PhysicalProduct | MobileApp | WebsiteSaas` on `promotion_type`; PhysicalProduct
   further splits `single_product` (list of products) vs `store_catalog` (store record) on
   `promotion_scope`. **Type every detail field as a real model** — `MobileAppDetails`,
   `WebsiteSaasDetails`, `PhysicalProductDetails`, `StoreCatalogDetails`. NO `dict[str, Any]`.
4. **Compensation** — `FlatComp | AffiliateComp | HybridComp` on `compensation_model`.
   - Flat: just `fixed_fee_per_creator`. Affiliate/Hybrid: the full commission config block.

## Corrections to the spec — apply these, do NOT copy the spec verbatim

1. **Drop `trackingTargets` and `leads` entirely.** Leads is descoped. A Performance campaign always
   means Sales — model that directly. Do not create a multi-target array or any leads fields/metrics.
   Keep Performance's conversion config as a struct that *could* be extended later, but ship sales-only.
2. **Do NOT include the schema-only-no-UI fields:** `totalBudgetCap`, `perCreatorBudgetCap`,
   `defaultRate`, `defaultCommissionPct`, `baseAffiliateUrl`, `attributionScope`, `attributionSkus`,
   `affiliateBudgetCap`, `utmSource`, `utmMedium`, `utmCampaign`. They are frontend cruft — omit from
   API, domain, and DB.
3. **Type the promotion detail variants** as Pydantic models (see union #3). Slugified option values
   from the spec become proper enums.
4. **Normalize coupon discount to one typed representation:** an int percent (0–100) plus an optional
   display label — not a free-text string in one place and an int in another.
5. **Compute all §8 derived fields server-side in the domain layer**, never accept them from the client:
   `affiliate_enabled` (= comp ≠ flat), `affiliate_model` (auto-derived from pricing model / app/saas),
   `provision_type` default, `gifting_enabled` (= provision ≠ none), `promo_code_enabled` (forced true
   when affiliate), `fixed_fee_per_creator` forced 0 for commission-only, and the **attribution profile**
   (verified availability + unlocking integration; marketplace buy-point never verifiable).

## Validation (mirror spec §7 exactly, server-side)

- Field-level via Pydantic types/constraints; cross-field via `@model_validator(mode="after")` on the
  relevant union variant.
- Cover all §7 rules: destination URL required+valid for Performance; promotion required fields per
  type/scope; buy-point required for Performance; description ≥20; niches ≥1; marketplace platforms≥1 /
  tiers≥1 / creator age order; audience age order; affiliate fields required when affiliate
  (+ subscription duration when affiliate_model subscription/both); subscription access method when
  subscription provisioning; deliverables ≥1; keyMessaging ≥10; cta ≥2; compliance trio unless
  BYOC+bypass; timeline date ordering (apply window marketplace-only, submission ≤ liveStart, live
  end ≥ start); maxInfluencers ≥1; joinType marketplace; roster ≥1 BYOC.
- Return structured 422 errors (field path + message), aggregated (not first-fail).

## Persistence (hybrid relational + JSONB)

- `campaigns` table: scalar always-present columns as real columns — `id` (uuid), `title`, `track`,
  `visibility`, `status` (enum: `draft`/`active`/…), `compensation_model`, `fixed_fee_per_creator`,
  `max_influencers`, timeline dates, `created_at`, `updated_at`.
- Polymorphic/variant data as **typed JSONB columns**, each validated by its Pydantic model before
  write: `promotion`, `targeting_or_roster`, `creative`, `fulfillment`, `compliance`, `affiliate`,
  `kpi_targets`, `attribution_profile`.
- Rationale to follow: scalars stay queryable (filter by track/status/date) without a 15-table join;
  variant blobs stay flexible for new promotion/comp types. A JSONB field can be promoted to a column
  later when query patterns demand it. Do not fully normalize into a table-per-variant now.
- Store `cover_image` / `media_assets` as file metadata `{name,size,type}` + a reference; wire actual
  binaries to a separate upload pipeline (out of scope here — leave a clean interface).

## Scalability / extensibility (must hold)

- Adding a new promotion type, compensation model, buy-point, integration, or re-adding leads/app-
  installs must be **adding a union variant + enum entry + config row** — never editing branching logic.
- Centralize all enums/option lists (spec §5) in one module; no magic strings.
- Keep an `assertNever`-style exhaustiveness guard (e.g. `typing.assert_never`) on every match over a
  union so a new variant fails type-check until handled.
- Idempotency: accept an optional idempotency key on create to make retries safe.

## Endpoints (v1)

- `POST /campaigns` — create. Body = the validated request union. Returns `201` + created campaign
  (response schema, not ORM object) + the derived `attribution_profile` and success message
  (BYOC vs marketplace variants per spec §9).
- `POST /campaigns/draft` — persist a partial draft (relaxed validation; status `draft`).
- `GET /campaigns/{id}` — fetch one (response schema).
- (Stub, don't build deep) `GET /campaigns` — list with track/status filters + pagination.

## Deliverables

- The layered modules above, Alembic migration for the tables, Pydantic v2 schemas with the four
  discriminated unions, the domain derivation logic (§8), server-side validation (§7), and the repo +
  service wiring.
- Unit tests: validation matrix (each §7 rule pass/fail), the §8 derivations, and union
  discrimination (each variant round-trips correctly). Plus exhaustiveness tests.
- A short README mapping spec sections → modules.

## Do not

- Persist the flat form shape, include the no-UI cruft fields, use `dict[str, Any]` for promotion
  details, trust any client-supplied derived field, or put business logic in route handlers.