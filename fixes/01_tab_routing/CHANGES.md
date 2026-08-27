# Fix 01 — PaymentGatewayPanel unreachable (no tab)

## Problem
PaymentGatewayPanel.jsx exists and is imported inside CreditPositionDashboard.jsx,
but the tab that shows it (payment) is **never exposed** by SegmentedTabs.jsx.
Users can never reach the x402 payment demo panel from the UI.

## Root cause
SegmentedTabs.jsx only exposes two tabs: position and score.
The dashboard renders ctiveTab === 'payment' nowhere in App.jsx.

## Fix (SegmentedTabs.jsx)
Add a third tab: payment / ? x402 Payment.

## Fix (App.jsx)
Add {activeTab === 'payment' && <PaymentGatewayPanel />} in the tab-content block.

## Affected files
- frontend/src/components/layout/SegmentedTabs.jsx   [MODIFY]
- frontend/src/App.jsx                               [MODIFY]
