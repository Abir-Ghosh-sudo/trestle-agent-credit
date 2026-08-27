# Fix 09 — PaymentGatewayPanel exists but no top-level tab renders it

## Problem
PaymentGatewayPanel.jsx implements the full x402 payment demo. It is imported
in CreditPositionDashboard.jsx (line 17), but CreditPositionDashboard itself
only renders it nested inside the dashboard layout — it is never shown as a
standalone tab.

App.jsx renders:
  activeTab === 'position' -> CreditPositionDashboard
  activeTab === 'score'    -> CreditScorePanel
  (no 'payment' case)

SegmentedTabs only exposes 'position' and 'score'. There is no way for the
user to reach the x402 demo panel at all from the UI.

## Fix (same as Fix 01 — combined)
This is a duplicate finding that confirms Fix 01. Apply Fix 01 patches.

See fixes/01_tab_routing/ for the actual patch files.
