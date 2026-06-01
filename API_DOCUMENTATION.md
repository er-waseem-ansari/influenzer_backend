# Influenzer — Brand API Documentation

Reference for integrating the **brand** side of the Influenzer backend with the web app.

- **Base URL:** `{BACKEND_URL}/api/v1` (local default: `http://localhost:8000/api/v1`)
- **Content type:** `application/json` for all request/response bodies.
- **Auth:** Bearer JWT in the `Authorization` header for `/brand/signout` and the `/brand/me/*` endpoints (see [Authentication](#authentication)).
- **Timestamps:** ISO‑8601 UTC strings (e.g. `2026-05-27T10:15:00Z`).
- **IDs:** UUID strings.

### A note on field casing ⚠️

Casing is **not uniform** across the API — match it exactly:

| Area | Casing | Example fields |
|------|--------|----------------|
| Auth requests (`/brand/login` etc.) | mixed | `email`, `password`, `deviceInfo` |
| Token & message responses | **snake_case** | `access_token`, `refresh_token`, `expires_in`, `message` |
| Brand profile / social / billing / OAuth (requests **and** responses) | **camelCase** | `displayName`, `websiteUrl`, `socialLinks` |

The camelCase endpoints also accept snake_case on input (lenient), but always **return** camelCase.

---

## Table of contents

1. [Authentication](#authentication)
2. [Error format](#error-format)
3. [Rate limits](#rate-limits)
4. [Roles & permissions](#roles--permissions)
5. [Auth endpoints](#auth-endpoints)
   - [POST /brand/signup](#post-brandsignup)
   - [POST /brand/login](#post-brandlogin)
   - [POST /auth/refresh](#post-authrefresh)
   - [POST /brand/signout](#post-brandsignout)
   - [POST /brand/resend-verification](#post-brandresend-verification)
   - [GET /brand/verify-email](#get-brandverify-email)
6. [Brand profile endpoints](#brand-profile-endpoints)
   - [GET /brand/me](#get-brandme)
   - [GET /brand/me/profile](#get-brandmeprofile)
   - [PATCH /brand/me/profile](#patch-brandmeprofile)
   - [GET /brand/me/social-links](#get-brandmesocial-links)
   - [PUT /brand/me/social-links/{platform}](#put-brandmesocial-linksplatform)
   - [DELETE /brand/me/social-links/{platform}](#delete-brandmesocial-linksplatform)
   - [GET /brand/me/billing](#get-brandmebilling)
   - [PUT /brand/me/billing](#put-brandmebilling)
   - [GET /brand/me/oauth-connections](#get-brandmeoauth-connections)
7. [Enums](#enums)

---

## Authentication

The brand product uses **email + password** auth. The lifecycle:

```
signup ──▶ (verify email via link) ──▶ login ──▶ access + refresh tokens
                                                      │
                                  use access token ◀──┘  Authorization: Bearer <token>
                                                      │
                                       refresh when expired (POST /auth/refresh)
```

- **Login** returns an `access_token` (default lifetime **30 min**) and a `refresh_token` (default **30 days**).
- Send the access token on protected endpoints:
  ```
  Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  ```
- The token is opaque to the client — store it and send it back; don't parse it.
- When the access token expires (401), call [`POST /auth/refresh`](#post-authrefresh) with the refresh token to get a new access token.
- A user **must verify their email before they can log in.**

Only **brand-side accounts** can use `/brand/login` and `/brand/me/*`: the user must have user role `BRAND` **and** an active brand membership. Every membership role is allowed to log in (`ADMIN`, `MANAGER`, `VIEWER`); see [Roles & permissions](#roles--permissions) for what each can do.

---

## Error format

All errors follow **RFC 9457 (Problem Details)** with `Content-Type: application/problem+json`:

```json
{
  "type": "about:blank",
  "title": "Forbidden",
  "status": 403,
  "detail": "Please verify your email address before logging in.",
  "instance": "/api/v1/brand/login",
  "code": "EMAIL_NOT_VERIFIED"
}
```

Always branch on the machine-readable **`code`**, not on `detail` (which is human-readable and may change).

**Common codes**

| HTTP | `code` | Meaning |
|------|--------|---------|
| 400 | `BAD_REQUEST` | Malformed/invalid request (e.g. bad verification token). |
| 401 | `UNAUTHORIZED` | Missing/invalid/expired token, or invalid login credentials. |
| 403 | `FORBIDDEN` | Authenticated but not allowed (wrong role / not an editor). |
| 403 | `EMAIL_NOT_VERIFIED` | Login blocked until email is verified. |
| 403 | `ACCOUNT_DEACTIVATED` | The account has been disabled. |
| 403 | `NO_ACTIVE_BRAND` | No active brand is linked to this account. |
| 404 | `NOT_FOUND` | Resource not found. |
| 409 | `CONFLICT` | State conflict (e.g. social link already exists). |
| 422 | `VALIDATION_ERROR` | Request body failed validation (see below). |
| 429 | `TOO_MANY_REQUESTS` | Rate limit exceeded. |
| 500 | `INTERNAL_SERVER_ERROR` | Unexpected server error. |
| 503 | `SERVICE_UNAVAILABLE` | Dependency (e.g. rate limiter) temporarily down. |

**Validation errors (422)** add a per-field `errors` array:

```json
{
  "type": "about:blank",
  "title": "Unprocessable Entity",
  "status": 422,
  "detail": "One or more request parameters failed validation.",
  "instance": "/api/v1/brand/signup",
  "code": "VALIDATION_ERROR",
  "errors": [
    { "field": "password", "message": "Password must contain at least one digit.", "type": "value_error" }
  ]
}
```

**Rate-limit errors (429)** add `errors.retryAfterSeconds`:

```json
{
  "type": "about:blank",
  "title": "Too Many Requests",
  "status": 429,
  "detail": "Rate limit exceeded. Try again in 42 second(s).",
  "instance": "/api/v1/brand/login",
  "code": "TOO_MANY_REQUESTS",
  "errors": { "retryAfterSeconds": 42 }
}
```

---

## Rate limits

Enforced with a Redis sliding-window counter. On hitting a limit you get a `429` with `retryAfterSeconds`.

| Endpoint | Limit | Window | Keyed by |
|----------|-------|--------|----------|
| `POST /brand/signup` | 5 | 1 hour | client IP |
| `POST /brand/login` | 10 | 5 min | client IP |
| `GET /brand/verify-email` | 10 | 1 min | client IP |
| `POST /brand/resend-verification` | 5 | 1 hour | client IP |
| `POST /brand/resend-verification` | 1 | 60 sec | email address (cooldown) |
| `PATCH/PUT/DELETE /brand/me/*` (writes) | 60 | 1 min | authenticated user |

---

## Roles & permissions

A logged-in brand user belongs to a brand with one membership role:

| Role | Read `/brand/me/*` | Write `/brand/me/*` (PATCH/PUT/DELETE) |
|------|:---:|:---:|
| `ADMIN` | ✅ | ✅ |
| `MANAGER` | ✅ | ✅ |
| `VIEWER` | ✅ | ❌ → `403 FORBIDDEN` |

The first user to sign up a brand becomes its `ADMIN`.

---

## Auth endpoints

### POST /brand/signup

Begin (or resume) brand signup. **The response is intentionally identical in every case** so it never reveals whether an email is already registered (anti-enumeration). Behind the scenes:

- **New email** → creates the account + brand + ADMIN membership and sends a verification email.
- **Existing unverified account** → resets its password to the new one and re-sends the verification email.
- **Already-registered (verified) email** → sends a "you already have an account" email instead; nothing changes.

**Auth:** none.

**Request body**

| Field | Type | Required | Rules |
|-------|------|:--:|-------|
| `email` | string | ✅ | Valid email. |
| `password` | string | ✅ | 8–72 chars; ≥1 letter and ≥1 digit. |

```json
{ "email": "founder@acme.com", "password": "Acme1234" }
```

**Response `200 OK`** (always this shape)

```json
{ "message": "Verification email sent. Please check your inbox." }
```

**Errors:** `422 VALIDATION_ERROR` (bad email / weak password), `429 TOO_MANY_REQUESTS`.

> Integration tip: treat `200` as "we've emailed you — go check your inbox." Do **not** show "email already taken."

---

### POST /brand/login

Authenticate and receive tokens. Allowed only for `BRAND` accounts with an active brand membership (any role).

**Auth:** none.

**Request body**

| Field | Type | Required | Notes |
|-------|------|:--:|-------|
| `email` | string | ✅ | |
| `password` | string | ✅ | |
| `deviceInfo` | string | ❌ | Optional device/platform fingerprint stored with the refresh token. |

```json
{ "email": "founder@acme.com", "password": "Acme1234", "deviceInfo": "Chrome 124 / macOS" }
```

**Response `200 OK`** (snake_case)

```json
{
  "access_token": "eyJhbGciOiJI...",
  "refresh_token": "eyJhbGciOiJI...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

`expires_in` is the access-token lifetime in **seconds**.

**Errors**

| HTTP | `code` | When |
|------|--------|------|
| 401 | `UNAUTHORIZED` | Unknown email, wrong password, or a non-brand account. Always the generic *"Invalid email or password."* |
| 403 | `EMAIL_NOT_VERIFIED` | Credentials correct but email not yet verified → prompt to verify / offer "resend". |
| 403 | `ACCOUNT_DEACTIVATED` | Account disabled. |
| 403 | `NO_ACTIVE_BRAND` | No active brand linked to the account. |
| 429 | `TOO_MANY_REQUESTS` | Too many attempts. |

---

### POST /auth/refresh

Exchange a valid refresh token for a fresh access token. **Shared** across the influencer and brand products (note: path is `/auth/refresh`, not under `/brand`).

**Auth:** none (the refresh token itself is the credential).

**Request body**

| Field | Type | Required |
|-------|------|:--:|
| `refreshToken` | string | ✅ |

```json
{ "refreshToken": "eyJhbGciOiJI..." }
```

**Response `200 OK`**

```json
{
  "access_token": "eyJhbGciOiJI...(new)",
  "refresh_token": "eyJhbGciOiJI...(same as sent)",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:** `401 UNAUTHORIZED` (invalid / revoked / expired refresh token), `404 NOT_FOUND` (user gone).

---

### POST /brand/signout

Revoke a refresh token so it can no longer be exchanged for a new access token. Use this when the user clicks **"Log out"** in your app, or **"Log out of all devices"** in security settings.

**Auth:** required — `Authorization: Bearer <access_token>` for a `BRAND` account.

**Request body**

| Field | Type | Required | Notes |
|-------|------|:--:|-------|
| `refreshToken` | string | conditional | The refresh token to revoke. **Required unless `allDevices` is `true`.** |
| `allDevices` | boolean | ❌ | Default `false`. When `true`, revokes **every** active refresh token for the caller and `refreshToken` is ignored. |

Sign out from this device only:

```json
{ "refreshToken": "eyJhbGciOiJI..." }
```

Sign out from every device:

```json
{ "allDevices": true }
```

**Response `200 OK`**

```json
{ "message": "Signed out." }
```

(or `"Signed out from all devices."` when `allDevices` was `true`.)

**Behaviour notes — read before integrating**

- **Server-side only.** This revokes the *refresh* token in the database. The current short-lived access token (≤ 30 min) remains valid until it naturally expires — the frontend MUST also drop the access token from its own storage (localStorage / cookies / memory) at the same time.
- **Idempotent.** Re-sending the same request, or sending an unknown / already-revoked / expired token that belongs to the caller, still returns `200`. Treat any `2xx` as "you are signed out" — don't show a "session not found" error if the user double-clicks Logout.
- **Caller-scoped.** Only refresh tokens belonging to the authenticated user can be revoked; passing a token that belongs to a different account is silently ignored (still returns `200`). A stolen access token therefore cannot be used to log out other users.
- **Recommended client flow:**
  1. `POST /brand/signout` with the stored `refreshToken`.
  2. On any `2xx` response (or even on network failure — see below), clear the access token + refresh token from local storage and redirect to the login screen.
  3. If the call fails with a network/5xx error, still wipe local tokens client-side — the user expects "Log out" to immediately log them out of the UI.

**Errors**

| HTTP | `code` | When |
|------|--------|------|
| 400 | `BAD_REQUEST` | `allDevices` is `false` (or omitted) **and** `refreshToken` was not provided. |
| 401 | `UNAUTHORIZED` | Missing / invalid / expired access token, or inactive account. |
| 403 | `FORBIDDEN` | Access token belongs to a non-`BRAND` account. |
| 422 | `VALIDATION_ERROR` | Body is malformed (e.g. `refreshToken` sent as empty string). |

---

### POST /brand/resend-verification

Re-send the verification email for an unverified account. Responds generically so it doesn't reveal whether the email exists.

**Auth:** none.

**Request body**

| Field | Type | Required |
|-------|------|:--:|
| `email` | string | ✅ |

```json
{ "email": "founder@acme.com" }
```

**Response `200 OK`**

```json
{ "message": "If an unverified account exists for that email, a new verification link has been sent." }
```

**Errors:** `429 TOO_MANY_REQUESTS` — both a per-IP cap (5/hour) and a per-email cooldown (1/60s) apply.

---

### GET /brand/verify-email

The target of the link inside the verification email. **The SPA does not normally call this directly** — the user's browser opens it, the backend validates the token, and then **redirects (303)** to a frontend page:

- Success → `{FRONTEND_URL}/email-verified`
- Failure → `{FRONTEND_URL}/email-verification-failed?reason=<CODE>` where `<CODE>` is `BAD_REQUEST` (invalid/expired/used token) or `NOT_FOUND` (user missing).

Your job on the frontend is to build those two landing pages. After a successful verify, send the user to login.

**Query param:** `token` (string, from the email link).
**Rate limit:** 10/min per IP (a `429` here returns JSON, not a redirect).

---

## Brand profile endpoints

All endpoints below require a valid **`Authorization: Bearer <access_token>`** header and operate on the brand the caller belongs to ("me"). Shared error responses:

| HTTP | `code` | When |
|------|--------|------|
| 401 | `UNAUTHORIZED` | Missing/invalid/expired token, or inactive account. |
| 403 | `FORBIDDEN` | Token belongs to a non-brand account, or a `VIEWER` attempted a write. |
| 404 | `NOT_FOUND` | No active brand / brand profile for this account. |

> **PATCH/PUT semantics:** updates apply **only the fields present** in the body. An omitted field is left unchanged; an explicit `null` clears it.

---

### GET /brand/me

Everything the brand-settings screen needs in one round-trip.

**Auth:** any active member. **Response `200 OK`:**

```json
{
  "profile": { "...": "see BrandProfile below" },
  "socialLinks": [ { "...": "see SocialLink below" } ],
  "billing": { "...": "see Billing below" },
  "oauthConnections": [ { "...": "see OAuthConnection below" } ]
}
```

`billing` is `null` if never set; `socialLinks` / `oauthConnections` are `[]` when empty.

---

### GET /brand/me/profile

Read the brand's core profile.

**Auth:** any active member. **Response `200 OK`** — the **BrandProfile** object:

```json
{
  "id": "0b3f...",
  "displayName": "Acme Inc.",
  "legalEntityName": "Acme Incorporated",
  "tagline": "We make everything",
  "about": "Long description...",
  "industry": "TECHNOLOGY",
  "companySize": "11-50",
  "foundedYear": 2018,
  "websiteUrl": "https://acme.com",
  "headquartersCountry": "United States",
  "addressLine1": "1 Market St",
  "addressLine2": null,
  "city": "San Francisco",
  "stateRegion": "CA",
  "postalCode": "94105",
  "contactName": "Jane Doe",
  "contactTitle": "Head of Marketing",
  "contactEmail": "jane@acme.com",
  "supportEmail": "support@acme.com",
  "phoneNumber": "+1 415 555 0100",
  "targetRegions": ["US", "CA", "EU"],
  "minAge": 18,
  "maxAge": 45,
  "audienceInterests": ["fitness", "travel"],
  "createdAt": "2026-05-01T09:00:00Z",
  "updatedAt": "2026-05-20T14:30:00Z"
}
```

Most fields are `null` until filled in.

---

### PATCH /brand/me/profile

Partially update the core profile.

**Auth:** `ADMIN` or `MANAGER`. **Rate limit:** 60/min per user.

**Request body** — all fields optional (camelCase):

| Field | Type | Rules |
|-------|------|-------|
| `displayName` | string | 1–100 chars |
| `legalEntityName` | string | ≤200 |
| `tagline` | string | ≤300 |
| `about` | string | ≤5000 |
| `industry` | enum | one of [Industry](#industry) |
| `companySize` | enum | one of [CompanySize](#companysize) |
| `foundedYear` | int | 1800 … current year |
| `websiteUrl` | string | valid `http(s)` URL, ≤500 |
| `headquartersCountry` | string | ≤100 |
| `addressLine1` / `addressLine2` | string | ≤255 |
| `city` | string | ≤100 |
| `stateRegion` | string | ≤100 |
| `postalCode` | string | ≤20 |
| `contactName` | string | ≤150 |
| `contactTitle` | string | ≤100 |
| `contactEmail` | string | valid email |
| `supportEmail` | string | valid email |
| `phoneNumber` | string | 7–15 digits, ≤30 chars |
| `targetRegions` | string[] | each entry ≤100 chars |
| `minAge` | int | 0–120 |
| `maxAge` | int | 0–120, must be ≥ `minAge` |
| `audienceInterests` | string[] | each entry ≤100 chars |

```json
{ "displayName": "Acme Inc.", "industry": "TECHNOLOGY", "minAge": 18, "maxAge": 45 }
```

**Response `200 OK`:** the full updated **BrandProfile** (same shape as `GET /brand/me/profile`).

**Errors:** `400 BAD_REQUEST` (e.g. `minAge > maxAge` against merged state), `422 VALIDATION_ERROR`, `403 FORBIDDEN` (viewer).

---

### GET /brand/me/social-links

List the brand's social links (one per platform), ordered by platform.

**Auth:** any active member. **Response `200 OK`:**

```json
[
  {
    "id": "9c1e...",
    "platform": "INSTAGRAM",
    "url": "https://instagram.com/acme",
    "createdAt": "2026-05-02T10:00:00Z",
    "updatedAt": "2026-05-02T10:00:00Z"
  }
]
```

---

### PUT /brand/me/social-links/{platform}

Create or replace the brand's URL for one platform (idempotent upsert).

**Auth:** `ADMIN` or `MANAGER`. **Rate limit:** 60/min per user.

**Path param:** `platform` — one of [SocialPlatform](#socialplatform), e.g. `INSTAGRAM`.

**Request body**

| Field | Type | Required | Rules |
|-------|------|:--:|-------|
| `url` | string | ✅ | valid `http(s)` URL, ≤500 |

```json
{ "url": "https://instagram.com/acme" }
```

**Response `200 OK`:** the **SocialLink** object (see above).

**Errors:** `422 VALIDATION_ERROR` (bad URL or unknown platform), `403 FORBIDDEN` (viewer).

---

### DELETE /brand/me/social-links/{platform}

Remove the brand's URL for a platform.

**Auth:** `ADMIN` or `MANAGER`. **Rate limit:** 60/min per user.

**Path param:** `platform` — one of [SocialPlatform](#socialplatform).

**Response `204 No Content`** (empty body).

**Errors:** `404 NOT_FOUND` (no link for that platform), `403 FORBIDDEN` (viewer).

---

### GET /brand/me/billing

Read billing details. **Sensitive identifiers (`taxId`, `gstNumber`) are returned masked** — only the last 4 characters, prefixed with `••••`.

**Auth:** any active member. **Response `200 OK`** (or `null` if billing was never set):

```json
{
  "billingContactName": "Acme Finance",
  "billingEmail": "billing@acme.com",
  "billingPhone": "+1 415 555 0101",
  "addressLine1": "1 Market St",
  "addressLine2": null,
  "city": "San Francisco",
  "stateRegion": "CA",
  "postalCode": "94105",
  "country": "United States",
  "taxId": "••••6789",
  "gstNumber": null,
  "createdAt": "2026-05-03T08:00:00Z",
  "updatedAt": "2026-05-18T11:00:00Z"
}
```

---

### PUT /brand/me/billing

Create or update the brand's single billing record (upsert).

**Auth:** `ADMIN` or `MANAGER`. **Rate limit:** 60/min per user.

**Request body** — all fields optional (camelCase):

| Field | Type | Rules |
|-------|------|-------|
| `billingContactName` | string | ≤150 |
| `billingEmail` | string | valid email |
| `billingPhone` | string | ≤30 |
| `addressLine1` / `addressLine2` | string | ≤255 |
| `city` | string | ≤100 |
| `stateRegion` | string | ≤100 |
| `postalCode` | string | ≤20 |
| `country` | string | ≤100 |
| `taxId` | string | ≤100 — stored encrypted, returned masked |
| `gstNumber` | string | ≤100 — stored encrypted, returned masked |

```json
{ "billingEmail": "billing@acme.com", "country": "United States", "taxId": "US123456789" }
```

**Response `200 OK`:** the **Billing** object with `taxId` / `gstNumber` masked.

**Errors:** `422 VALIDATION_ERROR`, `403 FORBIDDEN` (viewer).

---

### GET /brand/me/oauth-connections

List linked third-party accounts (read-only here). **Tokens are never exposed.**

**Auth:** any active member. **Response `200 OK`:**

```json
[
  {
    "id": "4a2b...",
    "provider": "GOOGLE",
    "providerAccountId": "1098...",
    "scopes": ["email", "profile"],
    "isActive": true,
    "tokenExpiresAt": "2026-06-01T00:00:00Z",
    "connectedAt": "2026-05-10T12:00:00Z",
    "lastRefreshedAt": "2026-05-25T12:00:00Z"
  }
]
```

---

## Enums

Enum values are **UPPERCASE on the wire** (except `CompanySize`, which uses range labels). Send them exactly as written.

### Industry
`FASHION`, `BEAUTY`, `TECHNOLOGY`, `FOOD_BEVERAGE`, `TRAVEL`, `FITNESS`, `GAMING`, `FINANCE`, `EDUCATION`, `ENTERTAINMENT`, `HEALTH`, `AUTOMOTIVE`, `HOME_LIVING`, `LIFESTYLE`, `OTHER`

### CompanySize
`1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1000+`

### SocialPlatform
`INSTAGRAM`, `YOUTUBE`, `TIKTOK`, `LINKEDIN`, `FACEBOOK`, `X`

### OAuthProvider
`GOOGLE`, `META`