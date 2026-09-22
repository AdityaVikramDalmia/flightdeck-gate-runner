# Operations and supported scope

## CLI

Global options go before the subcommand:

```bash
gate-run --runs-dir /absolute/path/to/state --json start --wait -- make test
```

`--runs-dir` defaults to the Git common directory's `gate-runner` subdirectory.
Custom state must be outside the worktree or inside its Git directory, so it cannot
change its own cache identity. All participants must use the same state directory
and filesystem to coordinate; two stores are independent.

`status [KEY]`, `wait [KEY]`, and `log [KEY]` default to the current worktree's
`latest`. `list` selects that worktree as well; use `list --all-worktrees` to inspect
the entire shared store. Pass the full key
from a `start`, `key`, or JSON response when coordinating multiple commands.
`wait --timeout SECONDS` stops waiting with exit 3; it does not cancel anything.
`log --tail N` prints the last N lines. There is no follow mode; ordinary `tail -f`
on the returned log path works. `list` shows the current attempt for every key.

A cached `pass`, `fail`, or `error` is reused until `--force` or changed inputs give
a new run. A `died` attempt retries automatically on the next start. There is no
automatic failure rerun or log-parsing adapter: a generic command's failure cannot
be turned into success by printed summary text.

## Recovery and retention

Use `status` and inspect `supervisor.log` if a run behaves unexpectedly. A live
lock without progress can be a hung command, or a surviving command after its
supervisor was killed. Identify and stop the actual process using normal OS tools;
Gate Runner intentionally has no PID-based cancel command.

State is retained without an automatic size cap. Archive old attempt directories
when no run is active. To remove the entire state store, first make sure every
command and supervisor using it has stopped. Never remove individual lock files
while clients may still be running. No remote synchronization is provided.

## Platform and dependency validation

The current release candidate was exercised locally on macOS with the system
Bash 3.2 launcher, Git, and Python 3.14. Its implementation uses Python 3.9+ standard
library APIs, `fcntl.flock`, detached POSIX sessions, and Git's NUL-delimited file
listing. Python 3.9 is the declared syntax/API floor, not a separately exercised
runtime in this validation environment. Linux has not been verified; Windows,
network filesystems, submodule repositories, and hostile multi-user state stores
are outside the supported scope.

Run `make test` for self-contained fixture tests. They create disposable Git
repositories, execute local commands, and send signals only to processes launched
by those tests. No network, paid service, or model calls are made. A test suite
success establishes the checked lifecycle cases; it is not a benchmark or a
claim that every filesystem, command tree, or failure mode is covered.
