# C1: late supervisor cancellation

Executed **2026-09-22**, on Darwin 25.2.0 arm64 with Python 3.14.6. This is a
new correctness receipt; it does not replace the extraction or preparation
receipts. Gate Runner remains private, Apache-2.0, and deprecated for new Claude
Code integrations.

## Exact revisions

- Reproduced baseline: `587facdaff79fedadd1ea582f30ae5f8282874a2`.
- Fixed and tested candidate: `3c246b7b831e7002afb7f6d353ca4ee8b5f8dafc`.
- Original review record: companion `flightdeck-examples` commit `6ad9597`,
  `docs/correctness-review/coordination/gate-runner-interruption.md` and its
  `reproduce.py`. Historical findings and execution restrictions are preserved.

## Baseline and fix

From the collection root, ran only the requested signal probe:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 flightdeck-examples/docs/correctness-review/coordination/reproduce.py --tools-root . --case signal
```

It exited 0 and reported `actual_state: pass`, `actual_exit: 0`, and
`same_attempt_reused_as_pass: true`, although the final-snapshot Git shim sent
SIGTERM to the fixture supervisor. Its recorded target matched that attempt's
`meta.json`. The command had exited successfully; the missing evidence was the
supervisor interruption. No `latest` or `archives` probe was executed.

The fix retains cancellation through final snapshot computation, then atomically
blocks SIGTERM/SIGINT/SIGHUP before the final interruption check and terminal
publication. Signals accepted before blocking produce `error`; signals arriving
after that documented completion boundary do not revise the completed verdict.
The reaped foreground command is no longer a signal target during validation.
README, lifecycle documentation, maintainer instructions, and dated provenance
agree with that behavior. These changes are September work, not July/August work.

## Candidate validation

A fresh local clone using `git clone --no-hardlinks` was detached at the full
candidate revision above, with a synthetic HOME, `GIT_CONFIG_NOSYSTEM=1`,
`GIT_CONFIG_GLOBAL=/dev/null`, and no network access needed. Clone, installation,
and project paths included spaces. The clean clone ran:

```sh
make test
```

Result: **43 unittest tests passed, zero skips**, in 39.785 seconds. This includes
Python compilation and Bash syntax validation. The two new tests are:

- `test_final_snapshot_cancellation_cannot_be_reused_as_pass`: three signal
  subcases (SIGTERM, SIGINT, SIGHUP), each sent by a fixture Git shim after
  verifying its parent against fixture supervisor metadata. Each completed
  command retains `exit_code: 0`, returns `error`/6 with the signal reason, and
  reuses only that error on a repeated identical start.
- `test_cancellation_after_completion_boundary_does_not_change_verdict`: an
  owned subprocess runs the actual supervisor and injects all three real signals
  at terminal publication. They are pending and blocked; the pass verdict stays
  unchanged. The publication wrapper is test instrumentation, not production
  timing code.

The 43 count is unittest test methods, not a total of signal subcases or individual
assertions. No aggregate coverage percentage is claimed.

The README installation was then performed into the synthetic HOME by copying
`bin` and `gate_runner` together and symlinking the installed launcher into
`.local/bin`. `gate-run --version` returned `0.1.0rc1`. The disposable example's
two starts, wait, log, cached repeat, forced repeat, and input-key edits passed:
one initial execution, one joined attempt, `finished` output, same-attempt cached
pass, a distinct forced attempt with the old result retained, and three distinct
keys for three input states. The candidate clone was clean after the suite.

## Scope and remaining verification

Only owned temporary repositories, files, stores, HOME directories, and test
processes were used. No automated safety rejection occurred in this lane; no
blocked historical experiment was retried or reformulated. The original runtime,
repository visibility, remotes, and existing main checkout were not modified.

This receipt is implementation-author macOS evidence. Independent verification,
the coordinated Linux harness, and final candidate-history/working-tree secret
scans are separate release gates to be recorded by the coordinating reviewer.
Synthetic timing proves the specified windows; it is not an exhaustive scheduler
or hardware-failure test. Public launch remains deferred.
