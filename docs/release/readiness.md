# Readiness and launch boundary

This repository has documented setup, requirements, command/failure
contracts, synthetic tests, provenance, Apache-2.0 terms, and maintainer guidance.
These were preparation artifacts for the public release, not a security certification.

## Attribution and dependencies

The owner selected the license for this work. The inspected tracked distribution
contains original/adapted component code, documentation, and synthetic fixtures;
no vendored upstream framework or dependency source tree was found. Runtime
dependencies are invoked or imported from the user's installation as listed in
README.md; their own licenses still apply. The local validation image is a test
environment, not a redistributed product image. Do not remove future third-party
notices or assume this inventory clears newly added code or assets.

Apache-2.0 includes copyright and patent grants and conditions for redistribution,
including retaining relevant attribution and marking modified files. It does not
require a prominent personal-credit banner. A private GitHub repository controls
access; it does not revoke the license rights granted to recipients.

## Verify the candidate

Run `make test` and the documented demo against a clean commit. Record the commit,
platform, commands, failures, and skips. Use the companion's validation harness for
macOS/Linux checks and scan the complete candidate Git history plus working tree
with Gitleaks. Inspect docs, fixtures, commit messages, and links for private data;
zero scanner findings is not proof that every kind of secret is detectable.

Preserve code-state and command identity, immutable attempts, detached-process ownership, and explicit exit evidence. A reused result covers only declared inputs; it is not a hermetic build.

## Launch checklist

Confirm the intended twelve-repository release set, current GitHub visibility,
the reviewed commits, and no unreviewed changes since the receipts. Confirm any
new third-party materials have compatible terms and appropriate notices. Confirm the intended presentation of all twelve deprecated reference projects
in the first public batch; do not market them as actively maintained integrations.
Then use a new explicit launch instruction to push any remaining local commits,
change visibility, and add verified public links to the portfolio. Deployment and
DNS are separate actions. No release tags, visibility changes, paid CI runs, or
deployments are performed by this preparation procedure.
