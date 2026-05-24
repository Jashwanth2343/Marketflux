# Handover — Supabase Auth Login Fix

Branch: `claude/auth-login-supabase-migration-dU7Wl`

## Problem

Login was completely broken ("ref error" / white screen). The app had been
migrated from MongoDB/JWT auth to Supabase Auth, but no Supabase credentials
existed anywhere (no `.env.local`, no env vars). As a result
`frontend/src/lib/supabase.js` called `createClient(undefined, undefined)`,
which `@supabase/supabase-js` v2 throws on at *import time* — crashing the
whole app before the login page could render.

## What was changed (committed + pushed)

- **`frontend/src/lib/supabase.js`** — added a guard so missing config throws a
  clear, actionable message instead of the opaque crash.
  Commit: `d545ba4` ("fix: fail with clear message when Supabase env vars are missing").

## Env files created (gitignored — NOT in git, secrets stay local)

These were created in this session but are gitignored, so they do **not**
persist beyond the working container. Recreate them in your real
deployment / local checkout.

- `frontend/.env.local`
  - `REACT_APP_SUPABASE_URL` = your project URL (`https://<project-ref>.supabase.co`, from the Supabase dashboard)
  - `REACT_APP_SUPABASE_ANON_KEY` = anon JWT (the long `eyJ...` key — public/safe)
- `backend/.env`
  - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` (service key is secret)
  - plus `MONGO_URL`, `DB_NAME`, `ALLOWED_ORIGINS`, Redis/Alpaca placeholders

Note: this project is **Create React App + craco**, so frontend env vars use the
`REACT_APP_*` convention (NOT Vite's `import.meta.env.VITE_*`).

## Verification

- Frontend dev server compiles, serves HTTP 200, and the real Supabase URL is
  inlined into the JS bundle — confirming `createClient` now receives valid args.
  The import-time crash is gone.
- **Not verified:** the live auth round-trip. Confirm actual sign-in from a
  browser with network access to your Supabase project. The backend additionally
  still imports MongoDB, so it requires a reachable Mongo instance to run.

## Things to know before testing login

1. **Old accounts lived in MongoDB, not Supabase.** Logging in with old
   credentials returns "Invalid login credentials". Use the **Sign Up** form to
   create a fresh Supabase account.
2. If "Confirm email" is enabled (Supabase Dashboard → Authentication → Email),
   confirm via the emailed link before sign-in works.
3. Set `REACT_APP_SUPABASE_URL` / `REACT_APP_SUPABASE_ANON_KEY` in your host's
   build environment for deployment (the local `.env.local` won't ship).
4. **Security:** rotate the `SUPABASE_SERVICE_KEY` in the Supabase dashboard if
   it may have been exposed.

## Outstanding / next steps

- **Backend Supabase env in deployment:** set `SUPABASE_URL` +
  `SUPABASE_SERVICE_KEY` so `server.py`'s `_supabase_auth_enabled` turns on and
  tokens get verified.
- **Mongo-free auth (optional):** `server.py` `_verify_supabase_token`
  (~lines 222-267) currently auto-writes a user record to Mongo. App data
  (watchlists, portfolios, chat, streams) still lives in Mongo. Going fully
  Mongo-free requires refactoring that function and migrating those collections.
- **Dead legacy code (optional cleanup):** the MongoDB/bcrypt/JWT
  `/api/auth/register` and `/api/auth/login` endpoints in `server.py`
  (~lines 311-362) are no longer called by the frontend and can be removed.

## Run locally

```
cd MarketFlux/frontend
yarn install
yarn start        # craco dev server on http://localhost:3000
```
