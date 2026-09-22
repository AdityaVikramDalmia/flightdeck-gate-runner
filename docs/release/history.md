# Source history and attribution

The earliest tracked source evidence at the extraction base is below. Dates use
the original author timezone (Asia/Kolkata); the private history also retains
committer dates. Git metadata is evidence, not an independent timestamp service.

| Source mechanism | First recorded | Source commit | Latest source edit at extraction |
|---|---|---|---|
| `bin/gate-run.sh` | 2026-07-27 | `5a8d09ec4a83df6a45e023ba5bc4d8f5a896105d` | 2026-08-05 |

Standalone extraction: **2026-09-22**, commit `59b037a39804d98e8b5358751ea5062a62bb79aa`.


The source mechanism's earlier date does not date every feature in the standalone
implementation. `PROVENANCE.md` distinguishes retained behavior, rewritten code,
and newly added contracts. In particular, portability and hardening work belongs
to the September extraction. Source history was not imported: it contains private
operational material outside this package.

Aditya Dalmia designed and maintains this work, with AI coding assistance during
implementation, extraction, and review. Upstream runtimes, language libraries, Git,
and operating-system facilities remain their authors' work. No authorship of
Claude Code or its native messaging feature is claimed.

On **2026-09-22**, the owner selected Apache-2.0 and requested private preparation
for a later public launch. This change adds the license, copyright notice, and
maintenance guidance in a new commit with its actual date. Existing history and
author/committer timestamps are preserved; the timeline is not a reconstructed
contribution graph.

The maintainer also marked all twelve repositories deprecated for new Claude Code
integrations on **2026-09-22**. This is a present maintenance decision, not a
historical claim that all utilities were replaced by native features.

On **2026-09-22**, a later correctness fix closes the late-signal window in the
standalone Python supervisor: cancellation remains effective during final input
validation and ends at an explicit signal-blocking boundary before publication.
This repair and its regressions are September work, not part of the July/August
source mechanism or the original extraction. The new receipt is recorded
separately from the original validation evidence.
