---
name: gate-runner-maintainer
description: Maintain deprecated Gate Runner's commands, documentation, examples, and private release candidate. Use for changes in this repository.
---

# Maintain Gate Runner

Read `README.md`, `PROVENANCE.md`, and `docs/release/README.md`, then only the
command contracts under `docs/` relevant to the requested change.

Preserve code-state and command identity, immutable attempts, detached-process ownership, and explicit exit evidence. A reused result covers only declared inputs; it is not a hermetic build.

Use `make test` and the documented isolated demo. Install into a disposable prefix
when installation changes; do not install over a user's commands to test a package.
Fixtures must not read real home configuration, sessions, credentials, or ledgers.

Keep historical source dates distinct from this standalone extraction and later
commits. Preserve Apache-2.0 attribution and the exact revision/platform attached
to a validation result. Add current evidence separately from historical receipts.
Public launch is deferred; this skill grants no visibility, remote push, deployment,
or paid CI authority. Apply any explicit authorization in the active task.

Keep the 2026-09-22 deprecation visible. This skill maintains reference material
and fixes requested by the owner; it does not recommend new Claude integrations.
