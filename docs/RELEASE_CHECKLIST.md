# Release gate

Development candidates may be built now, but no artifact should be promoted as a general end-user release until the following are complete:

- Select LICENSE and resolve all third-party provenance/asset notices.
- Package a supported Python runtime, or explicitly scope a developer-only release and revise this gate deliberately.
- Use a clean, fixed source commit/tag and retain the build receipt. Never include private experiments, live snapshots, logs or signing material.
- Pass fixture tests, separate-edition namespace tests, detached public build, bundle verification and clean-Mac installation tests for every advertised architecture/system version.
- Complete Developer ID signing of nested helpers and the main bundle, update their final signed hashes, notarize and validate Gatekeeper behavior.

`release_preflight.py` returns a failing status while blockers remain. Source publication and executable distribution are distinct operations. A GitHub automatic source archive is not the built app. Build scripts never call install scripts; install scripts require explicit --install.
