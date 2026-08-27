# Fix 04 — AgentOnboarding says 'Redirecting...' but never redirects

## Problem
In AgentOnboarding.jsx (line 276):
  <p ...>Redirecting to Dashboard...</p>

The component shows 'Redirecting to Dashboard...' on success, but it has no
mechanism to actually navigate. The parent App.jsx re-renders when
position.stake > 0n (detected after fetchPosition) which triggers the route
change, BUT only if fetchPosition has run after the successful registration.
In practice, after callRegisterUnified the loading state goes false and
position is updated, so the redirect DOES happen — but only if the 15-second
auto-refresh fires. There is no explicit post-register navigation call.

## Root cause
App.jsx derives the view from position.stake > 0n. After callRegisterUnified,
fetchPosition is called (inside ContractState), which updates position —
this triggers a re-render in App.jsx and the route changes. This works correctly
in the happy path BUT:
  a) The 'Redirecting...' text creates a false promise.
  b) If fetchPosition fails (network error) the user is stuck on the success
     screen with no way to proceed.

## Fix
In App.jsx, use a callback prop on AgentOnboarding to imperatively set view='app'
after registration success, rather than relying on reactive position state.

## Patch
