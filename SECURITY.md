# Security policy

## Supported scope

Security fixes are handled on the current `main` branch. This repository is a
local/pre-pilot foundation; no production retail tenant or connector should be
assumed to exist from the code alone.

## Reporting a vulnerability

Do not disclose credentials, customer data, personal data, or exploit details
in a public issue. Use GitHub's private vulnerability reporting for this
repository when it is enabled by the repository owner. If private reporting is
not enabled, ask the owner for a private reporting channel before sharing
sensitive details.

Please include a concise description, affected paths or versions, reproduction
steps, likely impact, and any proposed mitigation. Maintain the existing
authorisation and human-approval boundaries while investigating a report.

## Secret and data handling

- Never commit access tokens, passwords, connection strings, or `.env` files.
- Never commit retailer exports or identifiable customer data.
- Rotate any credential exposed in a branch, terminal transcript, issue, or
  pull request before continuing work.
- Treat public benchmarks and fixtures as non-production material and label
  them accordingly.
