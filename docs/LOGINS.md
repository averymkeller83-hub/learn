# Logins — Sign in with Google / Apple, and sync (planned 2026-09-17 22:30)

Why: pages live in one browser today. A login makes them follow the person (iPad ↔ laptop ↔ phone),
makes the per-visitor quota a per-person quota, and is the base for sharing and teacher mode.

## Decision (search before building — CLAUDE.md 6c)
- **OpenAuth (openauth.js.org, SST, MIT)** — an auth server that runs ON Cloudflare Workers, ships Google and
  Apple providers, issues its own tokens, stores state in KV. Free, open source, fits the stack we have.
  Fallback if it fights us: hand-rolled OIDC (Google ≈ 80 lines; Apple ≈ 120 — needs the ES256 client-secret JWT).
- **No third-party hosted auth** (Clerk/Auth0/Firebase): vendor lock, and the app must stay free.
- **Storage: D1.** Tables `users(id, provider, sub, email, name, created)`, `pages(id, user_id, json, updated)`,
  `sources(id, user_id, notebook, json, updated)`, `quota(user_id, day, n)`.
- **Offline-first.** IndexedDB stays as the local cache; the `store` seam gets a `remote` twin. Every save writes
  locally, then pushes; on open, pull newer records. Last-write-wins by `updated`. Signed-out = today's behaviour.

## What only Avery can do (free, before the coding hour)
1. **Google**: console.cloud.google.com → APIs & Services → Credentials → OAuth client ID → *Web application*.
   Authorised origin `https://showwork.avery-keller.net`; redirect `https://showwork.avery-keller.net/auth/google/callback`.
   Keep the client ID + secret for `wrangler secret put`.
2. **Apple** (needs the Apple Developer account you already have for the Jarvis app): developer.apple.com →
   Identifiers → **Services ID** with Sign in with Apple, domain `showwork.avery-keller.net`, return URL
   `https://showwork.avery-keller.net/auth/apple/callback`; Keys → new key with Sign in with Apple → download the .p8.
   Keep Team ID, Key ID, Services ID, and the .p8 for secrets.

## The build (≈3 h Google + sync; +1 h Apple)
1. Worker: OpenAuth issuer at `/auth/*` with Google (+ Apple) providers; KV for its state; session cookie (httpOnly,
   SameSite=Lax) carrying the OpenAuth access token; `GET /me`.
2. D1 schema + `/api/pages`, `/api/sources` CRUD (owner-scoped), `/api/quota` (replaces the per-visitor cap when signed in).
3. Client: **Sign in** button in the title strip (Google · Apple); `store.remote` with push-on-save and pull-on-open;
   a small "Syncing… / Synced" note in the sidebar foot; sign-out keeps the local cache but stops syncing.
4. Migration on first sign-in: upload every local page and source once.
5. Verify as a human: sign in on the Mac, write, sign in on the iPad, see it.

## Not in this pass
Sharing links · teacher mode · merging edits made offline on two devices at once (last-write-wins is the rule).
