# Contributing

Run `bash scripts/test.sh` and `bash scripts/build.sh`. The latter produces a candidate and never installs it. Keep `Package.swift` independent of adjacent local checkouts and use exact path casing.

Public changes belong in this checkout. Private experiments belong in a separate private package that depends on the public libraries, never the reverse. The public manifest must not import LocalExperiments or load private source trees through symlinks. Use synthetic fixtures, not personal snapshots.

Adding a provider or helper requires tests, a documented credential source, conservative query throttling and privacy review. Public entitlements cannot be expanded silently. Do not change bundle identifiers, data directories, keychain prefixes or helper identities as part of a cosmetic rename.

No license is selected yet. Resolve `LICENSE_PENDING.md` and third-party provenance before accepting external contributions for publication.
