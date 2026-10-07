# Account Takeover (ATO) Playbook

## Indicators
Login from a new device and a new country, unusual hours, impossible travel, and a password or email change within minutes of login. Attackers move fast: credential change followed by payment or export is the classic ATO chain.

## Response by risk level
Score 70 or more: revoke the session immediately, invalidate refresh tokens, force password reset, and notify the account owner. Score 35 to 69: require MFA step-up before any sensitive action and keep monitoring the session.

## Recovery
Verify the owner through a trusted channel, review actions taken during the suspicious session, reverse payments, and restore changed email or role settings. Add the incident to the user's risk history.
