# Campaign Creation — Full Specification

This document captures **everything** the campaign-creation wizard collects: every
step, question, label, description, field name, type, option set, default,
conditional-visibility rule, and validation rule. It is the source spec for
building the backend API that receives and persists a created campaign.

Source files:
- Wizard shell + step order: `app/(dashboard)/campaigns/create/page.tsx`
- Step UIs: `app/(dashboard)/campaigns/create/_steps/*`
- Form schema + option lists + validation: `lib/campaign-form.ts`
- Domain model (tracks, targets, buy-points, integrations, metrics): `lib/campaign/model.ts`, `lib/campaign/metrics.ts`

---

## 1. High-level model

A campaign is a single **creator campaign**. Two top-level choices reshape the
whole wizard:

1. **Track** (`track`) — the entry point:
   - `awareness` — pure content play; **no destination URL required**; the brand may skip describing a product entirely.
   - `performance` — sends people to a destination and measures outcomes; **destination URL required**; **always tracks Sales** (a buy-point must be chosen).
2. **Visibility / sourcing** (`visibility`):
   - `marketplace` — publish brief; platform creators discover & apply.
   - `invite_existing` — **BYOC** (bring your own creators); invite by email via magic link.

Affiliate/commission only becomes available once a conversion target exists
(i.e. Performance with a tracking target). Awareness campaigns are always flat-fee.

### Phases
Steps are grouped into four phases (used for the progress stepper):
`Requirement` → `Details` → `Payment` → `Review`.

---

## 2. Step order & conditional visibility

Steps render in this fixed order. Visibility/track gate which steps appear.

| # | key | Phase | Title | Short | Shown when |
|---|-----|-------|-------|-------|------------|
| 1 | `requirement` | Requirement | Your track | Track | Always |
| 2 | `sourcing` | Details | Sourcing | Source | Always |
| 3 | `targetInfluencers` | Details | Target influencers | Influencers | Always* |
| 4 | `targetAudience` | Details | Target audience | Audience | Always |
| 5 | `basics` | Details | Product & attribution | Product | Always |
| 6 | `creative` | Details | Campaign details & brief | Brief | Always |
| 7 | `fulfillment` | Details | Fulfillment | Logistics | Always |
| 8 | `compliance` | Details | Compliance | Legal | Unless `invite_existing` AND `contractBypassAcknowledged === true` |
| 9 | `kpiTargets` | Details | Analytics & KPIs | KPIs | Always |
| 10 | `timeline` | Details | Timeline | Timeline | Always |
| 11 | `pricing` | Payment | Creator compensation & budget | Payment | Always |
| 12 | `review` | Review | Review & launch | Review | Always |

Notes:
- Until `visibility` is chosen, only `requirement` + `sourcing` are shown.
- **\*The `targetInfluencers` step renders different content per flow** (this is the *only* step that differs between flows):
  - `marketplace` → influencer-targeting questions (platforms, tiers, engagement, creator demographics, locations).
  - `invite_existing` (BYOC) → the **roster + welcome message + existing-contract** sections instead (no targeting questions).
- `compliance` is auto-skipped only in the BYOC flow when the brand confirms an existing MSA.

---

## 3. Steps, questions & descriptions

For every step below: `field` = form key, `type`, `required`, options, and the
exact label/description/placeholder shown to the brand.

### Step 1 — Requirement (`requirement`)
Header: **"What are you trying to achieve?"**
Desc: "Pick a track — it's the one choice that reshapes the rest of the wizard. The difference is simple: do you need to send people to a destination and measure what they do?"

| Question | field | type | required | options | description |
|---|---|---|---|---|---|
| Campaign track | `track` | single-select card | yes | `awareness`, `performance` | "Awareness is a pure content play; Performance sends people to a destination and measures outcomes." |
| Industry / niche | `niches` | multi tag-input | yes (≥1) | suggestions = NICHES list | "Pick all niches that fit — helps creators discover and our algorithm match." |

Track option copy:
- **Awareness** — "Get eyes on your brand. No destination required — a pure content play."
- **Performance** — "Send people somewhere and measure what they do. A destination is required."

Side effects of selecting a track:
- Selecting **Awareness** clears `trackingTargets = []`, `buyPoint = undefined`, `primaryKpiTarget = undefined`.
- If the resulting tracking targets are empty, compensation is forced to flat (`compensationModel = "flat"`, `affiliateEnabled = false`).

### Step 2 — Sourcing (`sourcing`)
Header: **"Where are the creators coming from?"**
Desc: "Pick whether you want our marketplace creators to apply, or invite people you already work with."

| Question | field | type | required | options |
|---|---|---|---|---|
| Sourcing | `visibility` | single-select card | yes | `marketplace`, `invite_existing` |

Option copy:
- **marketplace** — "Hire from our creator marketplace" / "Publish your brief — verified creators on our platform discover, apply, and you approve." / best for: "Discover new creators at scale"
- **invite_existing** — "Invite my own creators (BYOC)" / "You already work with the creators. Invite them by email — they get a magic link, install the app, and land straight on the brief. Same backend, seamless payments & tracking." / best for: "Existing creator relationships"

### Step 3 — Target influencers (`targetInfluencers`)

#### 3a. Marketplace variant
Header: **"Target influencers"**
Desc: "Which kind of creators should we surface? Pick the platforms, tiers, and demographics that fit."

| Question | field | type | required | options | description |
|---|---|---|---|---|---|
| Target social platforms | `platforms` | multi-select card | yes (marketplace) | PLATFORMS | "Where do you want this campaign to live?" |
| Influencer tier | `tiers` | multi-select card | yes (marketplace) | INFLUENCER_TIERS | "Pick one or more follower bands. Mix nano + micro for higher engagement and lower spend." |
| Minimum engagement rate | `minEngagement` | slider 0–15 step 0.1 (%) | no | — | "Filter creators whose engagement is below this threshold." |
| Creator gender | `creatorGender` | single-select card | no | CREATOR_GENDER | "Pick how the creator presents publicly." |
| Creator age range | `creatorAgeMin`, `creatorAgeMax` | number (13–80) | no | — | "The creator's own age (typically 18 – 45)." |
| Creator niches | `creatorNiches` | multi tag-input | no | suggestions = NICHES | "What the creator is known for — separate from your product niches." |
| Creator geographic location | `creatorLocations` | multi tag-input | no | suggestions = LOCATION_SUGGESTIONS | "Where the creators themselves are based. Leave empty for no restriction." |

#### 3b. BYOC (invite_existing) variant
Renders three sections instead of the targeting questions:

**Invite roster** (header "Invite your creators" / "Add the people you already work with. We'll generate magic links that drop them straight into the campaign brief — no marketplace, no applications.")
- `inviteRoster` — array (required, ≥1). Each row:
  - `email` (email, required) — placeholder "creator@email.com"
  - `customRate` (number, optional) — placeholder "Flat fee (₹)"
  - `customCommissionPct` (number, optional, step 0.5) — placeholder "Commission %"
  - `welcomeNote` (string, optional) — per-creator note (set programmatically; not a visible input in the row)
- Description: "Each creator gets a personalised invite link by email. You can override default rates per creator below."
- Shows a magic-link preview derived from the campaign title slug.

**Welcome message** (header "Personal welcome" / "The first thing each creator sees when they open the campaign on their phone. Skip if you'd rather keep it standard.")
- `welcomeMessage` (string, optional) — label "Welcome message", desc "Talk to your creators directly — they're more likely to accept a personalised invite." Mobile preview shown.

**Existing contracts** (header "Existing contracts" / "If you already have an MSA with these creators, we'll skip the standard platform agreement and disclosure flow.")
- `contractBypassAcknowledged` (boolean checkbox, optional) — "I have a signed MSA / contract with every creator in this roster. By checking this, our platform will skip the standard usage-rights and compliance step — your existing agreement governs reuse, exclusivity, and disclosure obligations." When checked, the **Compliance** step is skipped.

### Step 4 — Target audience (`targetAudience`)
Header: **"Target audience"** / "Who should the creator's content reach? We'll use this to filter creators whose audience profile matches."

| Question | field | type | required | options | description |
|---|---|---|---|---|---|
| Min age | `audienceAgeMin` | number (13–65) | no | — | — |
| Max age | `audienceAgeMax` | number (13–65) | no | — | — |
| Dominant gender | `audienceGender` | select | no | AUDIENCE_GENDER | — |
| Audience interests | `audienceInterests` | multi tag-input | no | suggestions = INTEREST_SUGGESTIONS | "Specific interests the creator's audience must skew toward." |

Note: "Audience demographics come from connected platform insights. Creators without verified insights won't appear in matches when filters are set." Collected for **both** flows.

### Step 5 — Product & attribution (`basics`)
Header: **"Product & attribution"** / "What you're promoting and where the action happens — so we know what we can measure."

**Awareness opt-out** (only shown for Awareness): toggle `describeProduct` (default `true`) — "Mention a product or service?" / "Awareness campaigns can run on pure reach. Turn this on only if you want creators to talk about a specific product or service." When off, the entire product section is skipped.

**Product / Service type** (`promotionType`) — single-select card, required for Performance:
Label "Product / Service" / "Pick the closest fit — we'll ask a few questions tailored to it."
Options = PROMOTION_TYPES: `physical_product`, `mobile_app`, `website_saas` (see §5 for each type's follow-up fields).

**Scope** (`promotionScope`) — *physical_product only* (hidden otherwise; defaults `single_product`):
Label "What are you promoting?" / "This shapes where creators send people and what we can break down later."
Options = PROMOTION_SCOPES: `single_product` ("A specific product" / "One item / listing"), `store_catalog` ("Your store / catalog" / "Whole shop or a collection").

**Type-specific detail fields** (see §5) — rendered into one of:
- physical + `single_product` → repeatable list `promotionProducts[]` (each keyed by PHYSICAL_PRODUCT_FIELDS)
- physical + `store_catalog` → `storeCatalog` record (STORE_CATALOG_FIELDS) + the store URL goes into `landingUrl`
- non-physical → single `promotionDetails` record (the type's `fields`)

**Destination URL** (`landingUrl`) — url. Required for Performance, optional for Awareness. (For physical single-product, the primary product's `productUrl` is mirrored into `landingUrl`; for store_catalog the store URL is captured directly as `landingUrl`.)
- Label "Destination URL" / Performance: "Where the creator's trackable link points — product page, store, signup, or booking." / Awareness: "Optional for awareness — add one if you want a clickable destination."

**Sales — purchase tracking** (`buyPoint`) — shown only when **Performance AND promotionType set AND promotionType ≠ `mobile_app`**:
Label "Where do you sell?" (required) / "Pick where purchases happen. Clicks are tracked now; verified revenue unlocks once connected (deferred to after launch)."
Options = SALES_BUY_POINTS: `shopify`, `woocommerce`, `custom`, `marketplace` (see §6). Selecting one opens an informational capability popup (track-now vs unlock-once-connected).

**How should we track conversions?** (tracking methods) — shown only when **Performance AND product collected AND promotionType ≠ `mobile_app`**:
"Pick the methods you want. Unique tracking links and coupon codes are generated for each creator once they're assigned to the campaign — so they're never shared."
- **Tracking link (UTM)** — always on / mandatory (shown as a locked, "Required" card). "A unique link per creator that redirects to your product / service page, so every click is attributed."
- **Coupon code** — optional toggle `couponTrackingEnabled`. When enabled: `couponDiscount` (string) — label "Buyer discount" / "What the customer gets when they use the code. The code itself is generated per creator on assignment." (e.g. "15% OFF").
- The actual per-creator links/codes are NOT generated here — only the choice is captured.

**What you'll be able to measure** — read-only derived panel (Tracked-now vs Verified). No input.

**Cover image** (`coverImage`) — single file upload (PNG/JPG, 1200×630 preferred). Optional. "A high-quality banner shown on the campaign card."

> Legacy/unused on this step: `utmSource`, `utmMedium`, `utmCampaign` exist in the schema but the per-creator UTM preview UI was removed; do not expect values for them.

### Step 6 — Campaign details & creative brief (`creative`)
Header: **"Campaign details & creative brief"** / "Name the campaign, then tell creators exactly what to produce and the guardrails."

| Question | field | type | required | options | description / placeholder |
|---|---|---|---|---|---|
| Campaign title | `title` | text | yes (min 3) | — | "A short, catchy name creators see in the marketplace." |
| Campaign description | `campaignDescription` | textarea | yes (min 20 chars) | — | "A short overview — the angle, the audience, and what you want creators to drive." |
| Deliverable requirements | `deliverables` | quantity per type (≥1 total) | yes | DELIVERABLE_TYPES, each qty 0–10 (stored 1–20) | "Choose the content types and quantity each creator must publish." |
| Key messaging & hooks | `keyMessaging` | textarea | yes (min 10) | — | "What must creators say or address — especially in the first 3 seconds?" |
| Content do's | `dos` | multi tag-input | no | DO suggestions | "Mandatory actions creators must include." |
| Content don'ts | `donts` | multi tag-input | no | DON'T suggestions | "Hard restrictions that auto-flag during review." |
| Call to action (CTA) | `cta` | text | yes (min 2) | — | "The exact phrase creators must say or write." |
| Required media assets | `mediaAssets` | multi file upload (≤20) | no | images/video/audio/pdf/zip/fonts | "Drop in logos (transparent PNGs), brand fonts, soundtracks, mood boards." |
| Content pre-approval | `preApprovalRequired` | toggle | no | — | On: "Creators must submit drafts for your review before publishing." Off: "Creators can publish directly once approved." |

`deliverables[]` entry shape: `{ type: DeliverableType, quantity: int 1–20 }`.

### Step 7 — Fulfillment (`fulfillment`)
Header: **"Fulfillment & provisioning"** / "How creators get hands-on with your {product} so they can create honest content."

**What will you provide to creators?** (`provisionType`) — single-select card, defaulted from the product type:
Options = PROVISION_TYPES: `product`, `subscription`, `service`, `none`. "Pre-filled from what you're promoting — change it if needed."

Conditional sub-fields:
- **`provisionType === "product"`:**
  - `productVariants` (multi tag-input) — "Product variant options" / "Sizes, colors, or styles creators can choose from during onboarding."
  - `shippingScope` (single-select card) — `domestic` / `international` / `both`.
  - `shippingCountries` (multi tag-input) — "Eligible shipping countries" / "Limit to specific markets. Leave empty to ship to all."
  - `estimatedDeliveryDays` (number 0–60) — "Estimated delivery (days)" / "We use this to auto-calculate your content submission buffer."
- **`provisionType === "subscription"`:**
  - `subscriptionPlan` (text) — "Plan / tier creators get" / "Which plan should we comp? Default to your most representative tier."
  - `subscriptionDuration` (select) — SUBSCRIPTION_DURATIONS — "Access duration".
  - `subscriptionSeats` (number ≥1) — "Seats per creator" / "Usually 1. Increase for team / family plans."
  - `subscriptionAccessMethod` (single-select card, **required when subscription**) — SUBSCRIPTION_ACCESS_METHODS — "How do creators get access?"
- **`provisionType === "service"`:**
  - `serviceProvisionNote` (textarea) — "What's included for creators?" / "Describe the complimentary session / booking and how creators redeem it."
- **`provisionType === "none"`:** no extra fields.

`giftingEnabled` (boolean) is kept in sync: `true` for any provisionType other than `none`.

### Step 8 — Compliance (`compliance`)
Header: **"Compliance, legal & usage rights"** / "Protect your brand and stay on the right side of disclosure laws."
(Skipped entirely when BYOC + `contractBypassAcknowledged`.)

| Question | field | type | required | options | description |
|---|---|---|---|---|---|
| Usage rights scope | `usageRightsScope` | multi-select card | yes (≥1) | USAGE_RIGHTS | "How can you reuse the influencer's content?" |
| Usage rights duration | `usageRightsDuration` | select | yes | USAGE_DURATIONS | "How long can the brand use the content?" |
| Category exclusivity window | `exclusivityWindowDays` | button group | no | EXCLUSIVITY_WINDOWS (0/15/30/60/90) | "Days the creator can't promote a direct competitor after posting." |
| Disclosure acknowledgement | `complianceAcknowledged` | checkbox | yes (must be true) | — | Agree creators use #ad / #sponsored / paid-partnership labels (ASCI / FTC). |

### Step 9 — Analytics & KPIs (`kpiTargets`)
Header: **"Analytics & KPIs"** / "Set the numbers you'll judge this campaign by. We'll surface deltas on the dashboard once data starts rolling in."

- `kpiTargets` — a record keyed by metricId → number (≥0). **All optional** ("leave blank to skip a benchmark").
- Which metric inputs are shown is **derived** (not fixed): headline KPI(s) + a track-appropriate baseline:
  - Awareness baseline shown: `reach`, `impressions`, `engagementRate` (+ headline `reach`,`impressions`).
  - Performance baseline shown: `ctr`, `cpc` (+ headline derived from targets/product — see §7 `headlineKpi`).
- Also displays a read-only "What this campaign measures" panel (derived, no input).

### Step 10 — Timeline (`timeline`)
Header: **"Campaign timeline & deadlines"**

- **Application window** — *marketplace only*:
  - `applicationStart` (date, required for marketplace) — "Application opens"
  - `applicationEnd` (date, required for marketplace) — "Application closes"
- **Content delivery:**
  - `contentSubmissionDeadline` (date, required for ALL) — "Content submission deadline" / "Last day to submit drafts for review."
  - Product shipping buffer — read-only, auto-calculated from `estimatedDeliveryDays`. No input.
- **Live posting window:**
  - `liveStart` (date, required) — "Go live"
  - `liveEnd` (date, required) — "Wrap"
- **Application access** — *marketplace only*:
  - `joinType` (single-select card, required for marketplace) — `open` ("Open join") / `approval` ("Approval required").

### Step 11 — Creator compensation & budget (`pricing`)
Header: **"Creator compensation & budget"** / "Decide how you'll pay creators and set your budget. We'll show your total commitment live."

- **Compensation model** (`compensationModel`) — single-select card, **shown only when a conversion target exists** (Performance with target). Options = PAYMENT_MODELS: `flat`, `affiliate`, `hybrid`. If no target, it's forced to `flat` and the selector is hidden. Selecting non-flat sets `affiliateEnabled = true`.
- **Max creators on this campaign** (`maxInfluencers`) — number ≥1, required. "Hard cap on approved creators — we'll auto-pause new approvals once this is reached."
- **Fixed fee per creator (₹)** (`fixedFeePerCreator`) — number ≥0, required. **Hidden when `compensationModel === "affiliate"` (commission-only)**, in which case it is pinned to `0`. "What you'll pay each approved creator for content."
- Live totals tile (read-only): Per creator, Max creators, Total at max (= fee × maxInfluencers).
- **Affiliate config** sub-section — rendered inline when `compensationModel !== "flat"` (Affiliate/Hybrid). See §11a below.

#### 11a. Affiliate & conversion configuration (sub-section of pricing)
Header: **"Affiliate & conversion configuration"** / "Power the tracking engine and define how commissions get attributed."

| Question | field | type | required (when affiliate) | options | description |
|---|---|---|---|---|---|
| Commission type | `commissionType` | single-select card | yes | `percentage`, `flat` | percentage="Percentage of sale", flat="Flat rate" |
| Commission value | `commissionValue` | number ≥0 | yes | — | flat → "(₹)" + "Fixed amount the creator earns per attributed conversion."; pct → "(%)" + "Share of the sale the creator earns per attributed conversion." |
| Cookie expiry window | `cookieWindow` | select | yes | COOKIE_WINDOWS | "How long after a click should the creator earn credit for a purchase?" |
| Subscription commission duration | `subscriptionCommissionDuration` | select | yes **if** affiliate model is subscription/both | SUBSCRIPTION_COMMISSION_DURATIONS | "How long does a creator keep earning on a subscriber they refer?" |
| Buyer discount (% OFF) | `promoCodeDiscount` | number int 0–100 | yes (promo is mandatory) | — | "Whole number up to 100 — what the customer gets when using the code." |
| Code prefix style | `promoCodePrefix` | text | no | — | "Auto-appended with each creator's handle." (e.g. "CREATOR") |

- **Promo code tracking is mandatory** when affiliate is active: `promoCodeEnabled` is forced to `true`; there is no enable/disable toggle.
- `affiliateModel` (`one_time` / `subscription` / `both`) is **auto-derived** from the product type (no UI picker) and drives whether the subscription-duration question appears.
- A note states: the per-creator **UTM tracking link is generated once the influencer is assigned** to the campaign.
- **Removed / not asked here** (exist in schema but no UI; do not expect values): `baseAffiliateUrl`, `attributionScope`, `attributionSkus`, `affiliateBudgetCap`.

### Step 12 — Review & launch (`review`)
Read-only summary. Cards render in wizard order, gated by flow:
1. **Invite roster** (BYOC only): creators invited (count), existing contract (bypass/use MSA), welcome message.
2. **Target influencers** (marketplace only): platforms, tiers, min engagement, creator location, creator age, creator gender, creator niches.
3. **Target audience**: audience age, gender, interests.
4. **Product & destination**: promoting (type + scope), per-product/store details, destination URL, niches, cover image.
5. **Attribution & tracking**: track; (Performance) verified-data note / sells-via buy-point / tracking method (UTM + coupon); derived verified-capability rows.
6. **Campaign details & brief**: title, pre-approval, description, deliverables, key messaging, CTA, media assets (count), do's/don'ts (count).
7. **Fulfillment**: provides-to-creators + the provision-specific rows (incl. shipping countries for product).
8. **Compliance** (unless bypassed): usage rights, duration, exclusivity, disclosure tags.
9. **Analytics & KPI targets**: derived benchmark rows.
10. **Timeline**: (marketplace) apply window + join type; submission deadline; live window.
11. **Creator compensation & budget**: compensation model, max creators, flat fee/creator (hidden for commission-only).
12. **Affiliate config** (only when affiliate enabled): commission, subscription payout (if applicable), cookie window, promo codes.

---

## 4. Complete data model (form schema)

All fields on `campaignFormSchema`. Types use Zod semantics; `coerce.number`
means numeric strings are accepted. Arrays/records default to empty unless noted.

### Core / track / sourcing
| field | type | default | notes |
|---|---|---|---|
| `track` | enum `awareness`\|`performance` | — | required |
| `trackingTargets` | array of `sales`\|`leads` | `[]` | Performance-only; Sales is implicit for Performance |
| `buyPoint` | enum `shopify`\|`woocommerce`\|`custom`\|`marketplace` | — | required for Performance |
| `primaryKpiTarget` | enum `sales`\|`leads` | — | tiebreaker for headline KPI (reserved) |
| `visibility` | enum `marketplace`\|`invite_existing` | — | required |
| `affiliateEnabled` | boolean | — | synced with compensationModel ≠ flat |
| `compensationModel` | enum `flat`\|`affiliate`\|`hybrid` | — | |
| `templateId` | string | — | optional template seed id |

### General / product
| field | type | default | notes |
|---|---|---|---|
| `title` | string (min 3) | — | required |
| `campaignDescription` | string (min 20 chars) | — | required |
| `describeProduct` | boolean | `true` | awareness opt-out |
| `promotionType` | enum `physical_product`\|`website_saas`\|`mobile_app` | — | required for Performance |
| `promotionScope` | enum `single_product`\|`store_catalog` | `single_product` | required for physical |
| `promotionDetails` | record<string, any> | `{}` | non-physical type fields |
| `promotionProducts` | array<record<string, any>> | `[]` | physical + single_product |
| `storeCatalog` | record<string, any> | `{}` | physical + store_catalog |
| `coverImage` | array<{name,size,type}> | — | single banner |
| `niches` | array<string> | `[]` | required ≥1 |
| `landingUrl` | string (URL) | — | required for Performance |
| `utmSource` / `utmMedium` / `utmCampaign` | string | — | legacy, unused UI |
| `couponTrackingEnabled` | boolean | — | product-step coupon opt-in |
| `couponDiscount` | string | — | e.g. "15% OFF" |

### Targeting (marketplace)
| field | type | default | notes |
|---|---|---|---|
| `platforms` | array<string> | `[]` | required ≥1 (marketplace) |
| `tiers` | array<string> | `[]` | required ≥1 (marketplace) |
| `minEngagement` | number 0–20 | — | |
| `creatorLocations` | array<string> | `[]` | |
| `creatorAgeMin` / `creatorAgeMax` | number 13–80 | — | max ≥ min (marketplace) |
| `creatorGender` | enum `any`\|`female`\|`male`\|`non_binary` | — | |
| `creatorNiches` | array<string> | `[]` | |

### Audience
| field | type | default | notes |
|---|---|---|---|
| `audienceAgeMin` / `audienceAgeMax` | number 13–65 | — | max ≥ min |
| `audienceGender` | enum `any`\|`female`\|`male`\|`balanced` | — | |
| `audienceInterests` | array<string> | `[]` | |

### Compensation / budget
| field | type | default | notes |
|---|---|---|---|
| `fixedFeePerCreator` | number | — | required (pinned 0 for commission-only) |
| `totalBudgetCap` | number | — | **schema-only, no UI** (field removed from wizard) |
| `perCreatorBudgetCap` | number | — | **schema-only, no UI** (field removed from wizard) |
| `maxInfluencers` | number ≥1 | — | required |

### KPI targets
| field | type | default |
|---|---|---|
| `kpiTargets` | record<metricId, number ≥0> | `{}` |

### Creative brief
| field | type | default | notes |
|---|---|---|---|
| `deliverables` | array<{type:string, quantity:int 1–20}> | `[]` | required ≥1 |
| `keyMessaging` | string (min 10) | — | required |
| `dos` / `donts` | array<string> | `[]` | |
| `cta` | string (min 2) | — | required |
| `mediaAssets` | array<{name,size,type}> | — | |
| `preApprovalRequired` | boolean | — | |

### Affiliate config
| field | type | default | notes |
|---|---|---|---|
| `commissionType` | enum `percentage`\|`flat` | — | required when affiliate |
| `commissionValue` | number | — | required when affiliate |
| `cookieWindow` | enum `24h`\|`7d`\|`30d`\|`60d` | — | required when affiliate |
| `promoCodeEnabled` | boolean | — | forced true when affiliate |
| `promoCodeDiscount` | number int 0–100 | — | required when affiliate |
| `promoCodePrefix` | string | — | |
| `affiliateModel` | enum `one_time`\|`subscription`\|`both` | — | auto-derived |
| `subscriptionCommissionDuration` | enum `first_only`\|`3m`\|`6m`\|`12m`\|`lifetime` | — | required if affiliateModel subscription/both |
| `baseAffiliateUrl` | string | — | **schema-only, no UI** |
| `attributionScope` | enum `storewide`\|`specific` | — | **schema-only, no UI** |
| `attributionSkus` | array<string> | — | **schema-only, no UI** |
| `affiliateBudgetCap` | number | — | **schema-only, no UI** |

### Fulfillment
| field | type | default | notes |
|---|---|---|---|
| `giftingEnabled` | boolean | — | synced (≠ none) |
| `provisionType` | enum `product`\|`subscription`\|`service`\|`none` | — | |
| `productVariants` | array<string> | `[]` | product |
| `shippingScope` | enum `domestic`\|`international`\|`both` | — | product |
| `shippingCountries` | array<string> | `[]` | product |
| `estimatedDeliveryDays` | number 0–60 | — | product |
| `subscriptionPlan` | string | — | subscription |
| `subscriptionDuration` | enum `1m`\|`3m`\|`6m`\|`12m`\|`lifetime` | — | subscription |
| `subscriptionAccessMethod` | enum `promo_code`\|`manual_invite`\|`license_key` | — | required when subscription |
| `subscriptionSeats` | number ≥1 | — | subscription |
| `serviceProvisionNote` | string | — | service |

### Compliance
| field | type | default | notes |
|---|---|---|---|
| `usageRightsScope` | array<string> | `[]` | required ≥1 (unless bypass) |
| `usageRightsDuration` | enum `30d`\|`90d`\|`1y`\|`perpetual` | — | required (unless bypass) |
| `exclusivityWindowDays` | number ≥0 | — | |
| `complianceAcknowledged` | boolean | — | must be true (unless bypass) |

### Timeline
| field | type | default | notes |
|---|---|---|---|
| `applicationStart` / `applicationEnd` | string (date) | — | required for marketplace; end ≥ start |
| `contentSubmissionDeadline` | string (date) | — | required ALL; ≤ liveStart |
| `liveStart` / `liveEnd` | string (date) | — | required; end ≥ start |
| `joinType` | enum `open`\|`approval` | — | required for marketplace |

### BYOC (invite_existing)
| field | type | default | notes |
|---|---|---|---|
| `inviteRoster` | array<rosterEntry> | `[]` | required ≥1 (BYOC) |
| `defaultRate` | number | — | **schema-only, no UI** |
| `defaultCommissionPct` | number | — | **schema-only, no UI** |
| `contractBypassAcknowledged` | boolean | — | gates compliance skip |
| `welcomeMessage` | string | — | |

`rosterEntry` = `{ email (valid email, required), customRate? (number), customCommissionPct? (number), welcomeNote? (string) }`.

---

## 5. Option lists / enums

### NICHES (tag suggestions; also `niches` & `creatorNiches`)
`Skincare, Beauty, Fashion, Fitness, Wellness, Food, Tech, Gaming, Edtech, Lifestyle, Parenting, Travel, Finance, B2B SaaS, Other`

### PLATFORMS (`platforms`)
| value | label |
|---|---|
| `ig_reels` | Instagram Reels |
| `ig_stories` | Instagram Stories |
| `ig_posts` | Instagram Posts |
| `tiktok` | TikTok |
| `yt_dedicated` | YouTube — Dedicated |
| `yt_shorts` | YouTube Shorts |
| `linkedin` | LinkedIn |

### INFLUENCER_TIERS (`tiers`)
| value | label | range | description |
|---|---|---|---|
| `nano` | Nano | 1K – 10K | Niche communities, highest engagement |
| `micro` | Micro | 10K – 50K | Trusted local voices, strong CVR |
| `midtier` | Mid-tier | 50K – 500K | Established creators with reach |
| `macro` | Macro / Mega | 500K+ | Mass awareness and reach |

### CREATOR_GENDER (`creatorGender`)
`any` (Any), `female` (Female), `male` (Male), `non_binary` (Non-binary)

### AUDIENCE_GENDER (`audienceGender`)
`any` (Any), `female` (Female-leaning), `male` (Male-leaning), `balanced` (Balanced)

### DELIVERABLE_TYPES (`deliverables[].type`)
| value | label |
|---|---|
| `ig_reel` | Instagram Reel |
| `ig_story` | Instagram Story |
| `ig_post` | Instagram Post |
| `tiktok_video` | TikTok video |
| `yt_dedicated` | YouTube — Dedicated |
| `yt_shorts` | YouTube Shorts |
| `linkedin_post` | LinkedIn post |

### USAGE_RIGHTS (`usageRightsScope`)
`organic_repost` (Organic social repost), `paid_whitelist` (Paid ad whitelisting), `spark_ads` (Spark / Boost ads), `website` (Website & landing pages)

### USAGE_DURATIONS (`usageRightsDuration`)
`30d` (30 days), `90d` (90 days), `1y` (1 year), `perpetual` (Perpetual)

### EXCLUSIVITY_WINDOWS (`exclusivityWindowDays`)
`0` (None), `15`, `30`, `60`, `90` days

### COOKIE_WINDOWS (`cookieWindow`)
`24h` (24 hours), `7d` (7 days), `30d` (30 days), `60d` (60 days)

### PAYMENT_MODELS (`compensationModel`)
| value | title | description |
|---|---|---|
| `flat` | Flat fee | A fixed payment per creator for the content they deliver. |
| `affiliate` | Affiliate / commission | Pay only on the sales or leads a creator drives — no flat fee. |
| `hybrid` | Hybrid (flat + commission) | A flat content fee plus commission on what they drive. |

### AFFILIATE_MODELS (`affiliateModel`, auto-derived)
`one_time` (One-time purchase), `subscription` (Subscription), `both` (Both)

### SUBSCRIPTION_COMMISSION_DURATIONS (`subscriptionCommissionDuration`)
`first_only` (First payment only), `3m` (First 3 months), `6m` (First 6 months), `12m` (First 12 months), `lifetime` (Lifetime — every renewal)

### PROVISION_TYPES (`provisionType`)
| value | title | description |
|---|---|---|
| `product` | Ship a physical product | Mail the product to each creator's address. |
| `subscription` | Grant a free subscription | Comp creators access to your app, SaaS, or membership. |
| `service` | Offer the service | Give creators a complimentary session or booking. |
| `none` | Nothing to provide | Creators already have access — skip provisioning. |

### SUBSCRIPTION_ACCESS_METHODS (`subscriptionAccessMethod`)
`promo_code` (Coupon / promo code), `manual_invite` (Manual account invite), `license_key` (License / access key)

### SUBSCRIPTION_DURATIONS (`subscriptionDuration`)
`1m`, `3m`, `6m`, `12m`, `lifetime`

### PROMOTION_SCOPES (`promotionScope`)
`single_product` (A specific product), `store_catalog` (Your store / catalog)

### PROMOTION_TYPES (`promotionType`) and their detail fields

Option values produced by the `opt()` helper are **slugified labels**: lowercased,
non-alphanumeric runs → `_`, trimmed. e.g. `"iOS"`→`ios`, `"Health & fitness"`→`health_fitness`, `"In-app purchases"`→`in_app_purchases`, `"Start free trial"`→`start_free_trial`.

#### `physical_product` — "Physical product"
blurb: "A physical good you ship (apparel, beauty, electronics, food)."
Detail fields (`promotionProducts[]` rows when single_product = PHYSICAL_PRODUCT_FIELDS):
| name | label | type | required | options/placeholder |
|---|---|---|---|---|
| `name` | Product name | text | yes | "Aurora Vitamin C Serum" |
| `category` | Product category | select | yes | PRODUCT_CATEGORY_OPTIONS |
| `price` | Retail price (₹) | number | yes | "1899" |
| `productUrl` | Product landing URL | url | yes | "https://yourbrand.com/product" |
| `keyFeatures` | Key features / USPs | text | no | comma-separated |
| `description` | What is it & why will people love it? | textarea | yes | — |

When scope = `store_catalog`, use STORE_CATALOG_FIELDS instead (`storeCatalog`):
| name | label | type | required |
|---|---|---|---|
| `storeName` | Store / brand name | text | yes |
| `category` | What does your store sell? | select (PRODUCT_CATEGORY_OPTIONS) | yes |
| `collections` | Collections / categories to feature | text | no |
| `priceRange` | Typical price range | text | no |
| `description` | Tell creators about your store | textarea | yes |

`PRODUCT_CATEGORY_OPTIONS` (slugified): Apparel & fashion, Beauty & skincare, Electronics & gadgets, Food & beverage, Home & living, Health & supplements, Toys & baby, Jewellery & accessories, Other.

#### `mobile_app` — "Mobile app" (stored in `promotionDetails`)
blurb: "An iOS / Android app."
| name | label | type | required | options |
|---|---|---|---|---|
| `name` | App name | text | yes | — |
| `platform` | Platform | radio | yes | iOS / Android / Both |
| `appCategory` | App category | select | no | Health & fitness, Finance, Productivity, Social, Gaming, Education, Shopping, Food & drink, Travel, Other |
| `appStoreUrl` | App Store link | url | no | — |
| `playStoreUrl` | Google Play link | url | no | — |
| `pricingModel` | Pricing model | select | yes | Free, Freemium, Paid, Subscription, In-app purchases |
| `primaryAction` | Primary action | radio | yes | Install / Sign up / Purchase |
| `description` | What does the app do? | textarea | yes | — |

#### `website_saas` — "Website / SaaS" (stored in `promotionDetails`)
blurb: "An online product, tool, booking, or service with a web destination."
| name | label | type | required | options |
|---|---|---|---|---|
| `name` | Product name | text | yes | — |
| `audience` | Who is it for? | radio | no | B2B / B2C / Both |
| `pricingModel` | Pricing model | select | yes | Free, Freemium, Free trial, Subscription, One-time |
| `startingPrice` | Starting price | text | no | — |
| `freeTrialDays` | Free trial length (days) | number | no | — |
| `primaryAction` | Primary conversion | radio | yes | Sign up / Start free trial / Book a demo / Purchase |
| `description` | What does it do? | textarea | yes | — |

### SALES_BUY_POINTS (`buyPoint`)
| id | label | examples | url label | integration | verifiable | effort |
|---|---|---|---|---|---|---|
| `shopify` | Shopify | — | Store URL | `shopify` | yes | click |
| `woocommerce` | WooCommerce | — | Store URL | `woocommerce` | yes | click |
| `custom` | Custom website | — | Store URL | `postback` | yes | developer |
| `marketplace` | Marketplace | Amazon, Flipkart, Myntra… | Listing URL | `null` | **no** | developer |

Each buy-point also carries capability-popup copy (`trackNow`, `unlock`, `mechanism`) — see `lib/campaign/model.ts` `SALES_BUY_POINTS`.

### TRACKS (`track`)
`awareness` (no destination), `performance` (destination required).

### TRACKING_TARGETS (`trackingTargets`)
`sales` (Sales — purchases/revenue/ROAS), `leads` (Leads — sign-ups/demos/forms). Sales is implicit for every Performance campaign.

### INTEGRATIONS (verified-data unlock, backend concept)
`shopify`, `woocommerce`, `pixel`, `postback`, `mmp`, `crm`, or `null` (never verifiable).

---

## 6. Metric catalog (`kpiTargets` keys & analytics)

`kpiTargets` is keyed by `metricId`. Each metric has label/unit/format/source/tier.
Tier `content` = platform-sourced; `click` = our redirect; `verified` = needs integration.

| metricId | label | unit | format | source | tier |
|---|---|---|---|---|---|
| `reach` | Reach | count | integer | platform | content |
| `impressions` | Impressions | count | integer | platform | content |
| `engagement` | Engagements | count | integer | platform | content |
| `engagementRate` | Engagement rate | percent | percent | platform | content |
| `views` | Views | count | integer | platform | content |
| `cpm` | CPM | currency | currency | platform | content |
| `emv` | Earned media value | currency | currency | platform | content |
| `sharesSaves` | Shares & saves | count | integer | platform | content |
| `clicks` | Clicks | count | integer | redirect | click |
| `uniqueClicks` | Unique clicks | count | integer | redirect | click |
| `ctr` | CTR | percent | percent | redirect | click |
| `cpc` | CPC | currency | currency | redirect | click |
| `geo` | Geo breakdown | category | text | redirect | click |
| `device` | Device breakdown | category | text | redirect | click |
| `orders` | Orders | count | integer | integration | verified |
| `revenue` | Revenue | currency | currency | integration | verified |
| `roas` | ROAS | multiplier | multiplier | integration | verified |
| `cpa` | CPA | currency | currency | integration | verified |
| `aov` | Average order value | currency | currency | integration | verified |
| `conversionRate` | Conversion rate | percent | percent | integration | verified |
| `codeRedemptions` | Code redemptions | count | integer | integration | verified |
| `installs` | Installs | count | integer | integration | verified |
| `inAppPurchases` | In-app purchases | count | integer | integration | verified |
| `cpi` | Cost per install | currency | currency | integration | verified |
| `leads` | Leads | count | integer | integration | verified |
| `cpl` | Cost per lead | currency | currency | integration | verified |
| `qualifiedLeads` | Qualified leads | count | integer | integration | verified |
| `costPerQualifiedLead` | Cost per qualified lead | currency | currency | integration | verified |
| `commissionOwed` | Commission owed | currency | currency | integration | verified |

Derived metric sets (backend may mirror for analytics):
- **Awareness measures:** content baseline (`reach`,`impressions`,`engagement`,`engagementRate`) + `views`,`cpm`,`emv`,`sharesSaves` (+ `clicks` if a destination exists).
- **Performance measures:** content baseline + click baseline (`clicks`,`uniqueClicks`,`ctr`,`cpc`,`geo`,`device`) + verified metrics per connected target.
- **Sales verified (web/physical):** `orders`,`revenue`,`roas`,`cpa`,`aov`,`conversionRate`,`codeRedemptions`,`commissionOwed`.
- **Sales verified (mobile_app):** `installs`,`inAppPurchases`,`revenue`,`roas`,`cpa`,`cpi`,`commissionOwed`.
- **Leads verified:** `leads`,`cpl`,`conversionRate`,`qualifiedLeads`,`costPerQualifiedLead`,`commissionOwed`.
- **Headline KPI** (`headlineKpi`): awareness → `reach`,`impressions`; performance no target → `ctr`,`cpc`; leads → `leads`,`cpl`; sales web → `roas`,`revenue`; sales mobile → `installs`,`cpi`.
- `commissionOwed` only renders for affiliate/hybrid payment.

---

## 7. Validation rules (server should mirror)

From `campaignFormSchema` refinements (in evaluation order):

1. `visibility` required — "Pick how you'll source creators".
2. **Destination URL**: required & valid URL for `track === performance`; if present for any track, must be a valid URL.
3. **Product section** (only when `track === performance`):
   - `promotionType` required.
   - physical: `promotionScope` required; if `store_catalog` → required STORE_CATALOG_FIELDS; if `single_product` → ≥1 product, each with required PHYSICAL_PRODUCT_FIELDS.
   - non-physical: required fields of the chosen type's `fields` (in `promotionDetails`).
4. **Sales buy-point**: `buyPoint` required when `track === performance`.
5. `campaignDescription` ≥ 20 chars.
6. `niches` ≥ 1.
7. **Marketplace only:** `platforms` ≥1; `tiers` ≥1; `creatorAgeMax ≥ creatorAgeMin` (if both set).
8. `audienceAgeMax ≥ audienceAgeMin` (if both set) — both flows.
9. `fixedFeePerCreator` must be defined (commission-only campaigns set it to 0 automatically).
10. **Affiliate (when `affiliateEnabled`):** `commissionType` + `commissionValue` + `cookieWindow` required; `promoCodeDiscount` required; `subscriptionCommissionDuration` required if `affiliateModel` is `subscription`/`both`.
11. **Subscription provisioning:** `subscriptionAccessMethod` required when `provisionType === subscription`.
12. `deliverables` ≥ 1.
13. `keyMessaging` ≥ 10 chars.
14. `cta` ≥ 2 chars.
15. **Compliance** (unless BYOC + `contractBypassAcknowledged`): `usageRightsScope` ≥1; `usageRightsDuration` set; `complianceAcknowledged === true`.
16. **Timeline:**
    - Marketplace: `applicationStart` & `applicationEnd` required; `applicationEnd ≥ applicationStart`.
    - All: `contentSubmissionDeadline` required and `≤ liveStart`.
    - `liveStart` & `liveEnd` required; `liveEnd ≥ liveStart`.
17. `maxInfluencers ≥ 1`.
18. Marketplace: `joinType` required.
19. BYOC: `inviteRoster` ≥ 1.

### Per-step validation groups (`STEP_FIELDS`)
The wizard triggers validation on these field groups when advancing each step:
- `requirement`: `track`, `niches`
- `sourcing`: `visibility`
- `basics`: `promotionType`, `promotionScope`, `promotionDetails`, `promotionProducts`, `storeCatalog`, `landingUrl`, `trackingTargets`, `buyPoint`, `couponTrackingEnabled`, `couponDiscount`
- `targetInfluencers`: `platforms`, `tiers`, `minEngagement`, `creatorAgeMin`, `creatorAgeMax`, `creatorGender`, `creatorNiches`, `inviteRoster`, `welcomeMessage`, `contractBypassAcknowledged`
- `targetAudience`: `audienceAgeMin`, `audienceAgeMax`, `audienceGender`
- `creative`: `title`, `campaignDescription`, `deliverables`, `keyMessaging`, `cta`, `preApprovalRequired`
- `fulfillment`: `giftingEnabled`, `provisionType`, `subscriptionAccessMethod`, `estimatedDeliveryDays`
- `compliance`: `usageRightsScope`, `usageRightsDuration`, `exclusivityWindowDays`, `complianceAcknowledged`
- `kpiTargets`: `kpiTargets`
- `timeline`: `applicationStart`, `applicationEnd`, `contentSubmissionDeadline`, `liveStart`, `liveEnd`, `joinType`
- `pricing`: `maxInfluencers`, `fixedFeePerCreator`, `totalBudgetCap`, `perCreatorBudgetCap`, `defaultRate`, `defaultCommissionPct`, `compensationModel`, `affiliateModel`, `baseAffiliateUrl`, `commissionType`, `commissionValue`, `cookieWindow`, `subscriptionCommissionDuration`, `attributionScope`, `affiliateBudgetCap`

---

## 8. Derived / business logic the backend should know

- **Sales is implicit for Performance:** `trackingTargets` always includes `sales` for a Performance campaign.
- **affiliateEnabled / compensationModel:** `affiliateEnabled = compensationModel !== "flat"`. Commission models only offered when a conversion target exists.
- **Commission-only (`affiliate`)** → `fixedFeePerCreator` is forced to `0`.
- **`affiliateModel` auto-derivation:** subscription if the promoted product's `pricingModel === "subscription"` or type is `mobile_app`/`website_saas`; else `one_time`.
- **`provisionType` default:** subscription if subscription-priced or type is app/saas; `product` for physical; else `none`.
- **`giftingEnabled`** mirrors `provisionType !== "none"`.
- **Promo code mandatory** when affiliate active (`promoCodeEnabled = true`).
- **Per-creator tracking links & coupon codes are generated on influencer assignment**, not at campaign creation — store only the brand's choice (`couponTrackingEnabled`, `couponDiscount`, `promoCodeDiscount`, `promoCodePrefix`).
- **Verified data is deferred:** at creation everything is "Tracked"; Sales becomes "Verified" only after the brand connects the integration post-launch. Leads are hosted (Verified at launch).
- **Attribution profile** (derived for the post-create dialog): whether verified is available + which integration unlocks it, from `buyPoint`/targets/productType. Marketplace buy-point is never verifiable.

---

## 9. Suggested API shape

The created campaign payload is essentially the validated `campaignFormSchema`
output (`CampaignSubmitValues`). Recommended handling:
- Persist all collected fields above.
- Ignore/omit the schema-only-no-UI fields unless you intend to use them: `totalBudgetCap`, `perCreatorBudgetCap`, `defaultRate`, `defaultCommissionPct`, `baseAffiliateUrl`, `attributionScope`, `attributionSkus`, `affiliateBudgetCap`, `utmSource`, `utmMedium`, `utmCampaign`.
- Re-run the §7 validation server-side (do not trust the client).
- `coverImage` / `mediaAssets` arrive as file metadata `{name,size,type}` — wire to your upload pipeline for the actual binaries.
- On success the UI shows: BYOC → "Invites are being sent to your roster."; marketplace → "Creators can now apply."
