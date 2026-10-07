# Data Exfiltration Playbook

## Indicators
Bulk exports far above the user's normal size, exports shortly after login, and exports following a credential change. A baseline of typical export size per user makes outliers easy to spot.

## Response
Block exports over five times the user's baseline until verified. Require step-up for exports under that threshold when the device or location is new. Alert the security team and preserve logs for review.

## Prevention
Rate-limit exports, require approval for large exports, and watermark exported files.
