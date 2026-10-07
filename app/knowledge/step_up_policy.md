# Step-Up Authentication Policy

## Decision thresholds
Risk score below 35: allow. Score 35 to 69: step-up authentication with MFA. Score 70 or higher: block the action and revoke the session.

## Sensitive actions
Payments, data exports, role changes, password and email changes, and account recovery always carry extra weight. These actions are re-evaluated at the moment they happen, not only at login.

## Privacy
Only pseudonymous references are shared with AI components. Raw IP addresses, emails, and user agents are never sent to a language model. The language model explains decisions but never makes them.
