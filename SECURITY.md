# Security

Do not publish secrets or live account snapshots in issues. Until a private security-reporting channel is configured, contact the repository owner through an already trusted private channel rather than creating a public vulnerability report containing sensitive details.

`audit_public.py` checks a public allowlist, symlinks, private module imports, and limited secret patterns. It is not a comprehensive security scan or license audit. `verify_bundle.py` verifies signatures, identities, copied helper hashes, explicit namespace rejection and temporary-store self-tests. Tests do not grant permissions or fetch live accounts.

Native, Python and helper code must agree on one build profile. A production collector cannot be redirected by MONITOR_DATA_DIR. Only explicit fixture mode permits a temporary override, and known production data paths are rejected. This is not a sandbox guarantee.

Keep provider host restrictions, certificate verification, retry/backoff, timeouts, private-pipe credentials and sanitized results intact. More privileged private experiments must be reviewed independently and must not enter the public product.
