# Provenance

This private release candidate extracts and generalizes the durable test-run
coordination design from source commit:

`494799eea3b9e7ce8686506a288c297ccf96be8d`

Source files reviewed:

- `bin/gate-run.sh`: code-state identity, start/join, detached supervision,
  status/wait/log interfaces, persistent verdicts, and retained previous attempts.
- `bin/gate-run-test.sh`: behavioral precedent for concurrency, interruption,
  input hashing, and detached survival tests.
- `bin/lib/lock.sh`: lock ownership and stale-holder race requirements.
- `bin/lib/detach.sh`: separation from the launcher's process group.
- `bin/lib/fmt.sh` and `bin/lib/registry.sh`: integration boundaries inspected;
  formatting, identity lookup, and notification dependencies are not carried over.

The coordinator and regression tests were reimplemented for standalone use with
Python's standard library and a Bash 3-compatible entry point. OS advisory locks
replace shared temporary-directory lock state; immutable attempts replace mutable
verdict archiving. The key adds exact command identity, declared environment and
extra inputs, staged index entries, and canonical worktree path. Generic commands
are judged by their exit status. Project-specific suite parsing, automatic reruns,
notifications, and private integration hooks were removed.

No public remote, personal filesystem path, or private incident history is needed
to build or run this repository. The owner selected Apache-2.0 on 2026-09-22. See LICENSE and NOTICE; public launch remains deferred.
