# Fix 02 — Secret credentials exposed in browser bundle

## Problem
rontend/.env contains:
  AGENT_MNEMONIC=soft bulk midnight...   (live mnemonic -> private key)
  VENICE_API_KEY=WmwvJjtMB2i...         (live API key)

Vite bakes ALL VITE_* and unlisted variables that are referenced by
import.meta.env.* into the production JS bundle. These secrets are
accessible to ANYONE who loads the site and opens DevTools.

## Root cause
Secrets that belong to the Python SDK / backend agent were accidentally
placed in the frontend .env file. They are NOT referenced by any Vite
frontend code (no VITE_ prefix) but their presence is a clear security risk.

## Fix
1. Remove AGENT_MNEMONIC and VENICE_API_KEY from frontend/.env immediately.
2. Those values belong only in trestle_project/.env (Python backend side).
3. Add frontend/.env.example showing ONLY safe VITE_* keys.

## Affected files
- frontend/.env           [MODIFY — remove non-VITE secrets]
- frontend/.env.example   [ADD — document safe env vars]
- .gitignore              [VERIFY — confirm .env is listed]
