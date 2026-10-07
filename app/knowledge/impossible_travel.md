# Impossible Travel Playbook

## Detection
Compare the distance between consecutive logins with elapsed time. Implied speed above 900 km/h is impossible travel; 500 to 900 km/h is suspicious. Distances under 300 km are ignored because of mobile network noise.

## False positives
VPNs, corporate proxies, and mobile carriers can move an IP across countries. Check whether the device is a known device before blocking. A known device with impossible travel usually deserves MFA step-up, not a hard block.

## Response
Known device: step-up with MFA. New device: block the session and verify the user out-of-band.
