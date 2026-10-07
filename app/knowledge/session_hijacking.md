# Session Hijacking Playbook

## Indicators
The same session token is used from a different device, user agent, or country in the middle of a session. Sensitive actions such as role changes right after the switch are a strong signal of stolen cookies or tokens.

## Response
Revoke the session token immediately and require a fresh login with MFA. Rotate session secrets for the affected user. Review role changes and permission grants made in the session and roll them back.

## Prevention
Bind sessions to device fingerprints, use short-lived tokens with rotation, and re-check risk before every sensitive action instead of only at login.
