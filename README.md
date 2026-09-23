# Gate Runner

Gate Runner runs a development command (by default `make test`) once per Git code
state, lets other local callers join that run, and keeps its verdict readable after
the launching terminal has gone away.

> **Status:** public Apache-2.0 reference implementation, deprecated for new Claude Code
> integrations as of 2026-09-22. Not a claim that Claude Code replaces every capability; no
> ongoing feature work or support is promised.

## What it does

Gate Runner records command output, the actual exit code, timestamps, and immutable
attempts under your repository's Git directory. Concurrent starts for the same
inputs share one command, and a completed result is reused until `--force` or
changed inputs start a new run. There is no service, account, notification
integration, or model call.

## Why it exists

Two local workers can launch the same expensive check, lose its output when a
terminal closes, or treat a reassuring log line as success despite a nonzero exit.
Gate Runner closes each gap: concurrent starts join one run; the command runs
detached, so killing the launcher or timing out a `wait` does not stop it; and the
verdict comes from the exit code, so a completed failure stays a failure,
regardless of what its log says.

## Install

Version 0.1.0rc1. Requires macOS or Linux with Python **3.9 or newer**, Git, and
Bash; no Python packages are required. The project you test must be a Git working
tree with at least one commit, on a local filesystem.

Install the `gate-run` command with pipx:

```bash
pipx install git+https://github.com/AdityaVikramDalmia/flightdeck-gate-runner
```

Or clone the repository and, from the checkout, install the complete launcher and
module together:

```bash
git clone https://github.com/AdityaVikramDalmia/flightdeck-gate-runner.git
cd flightdeck-gate-runner
mkdir -p "$HOME/.local/share/gate-runner" "$HOME/.local/bin"
cp -rf bin gate_runner "$HOME/.local/share/gate-runner/"
ln -sf "$HOME/.local/share/gate-runner/bin/gate-run" "$HOME/.local/bin/gate-run"
export PATH="$HOME/.local/bin:$PATH"
gate-run --version
```

Alternatively use the absolute path to `bin/gate-run` directly. Run the launcher
from the project you want to test. Installation and target paths may contain spaces.

## Quick use

```bash
cd /path/to/your/git-project

# Defaults to: make test. Returns as soon as the detached run starts.
gate-run start

# Join the latest run and return its verdict.
gate-run wait --timeout 120
gate-run log --tail 50
```

[A complete fixture example](examples/README.md) shows two starts joining one
command, result reuse, and cache invalidation in a disposable repository.

## Commands and exit codes

```bash
gate-run status
gate-run list
gate-run list --all-worktrees

# Explicit argv: no shell interpolation.
gate-run start --wait -- python3 -m unittest discover -s tests

# Shell syntax is opt-in.
gate-run start --wait --shell 'make lint && make test'

# Retry completed work while retaining every prior attempt.
gate-run start --force --wait --shell 'make lint && make test'

# Declare environment, extra inputs, and an explicit toolchain identity.
gate-run start --wait --env-key CI --input .env.test --salt 'toolchain-2026-09' -- make test
```

`status`, `wait`, and `log` default to the latest attempt created for the current
worktree. `list` also selects the current worktree; `list --all-worktrees` includes
every worktree sharing the state store.

| Exit | `status`, `wait`, and `start --wait` |
|---|---|
| `0` | Pass |
| `1` | Command failure |
| `2` | Usage error (any subcommand) |
| `3` | Still running, or wait timeout |
| `4` | No record |
| `5` | Supervisor disappeared without a result |
| `6` | Tool error, or interrupted/invalidated run |

`start` without `--wait` returns 0 when work is launched or joined in progress.
For a cached terminal result it returns that result's status. A command's original
exit code is preserved separately, including negative signal numbers.

Use `--json` before the subcommand for structured records:

```bash
gate-run --json start --wait --env MODE=ci -- python3 -m unittest
gate-run --json status
```

See [the documentation index](docs/README.md) for lifecycle guarantees, stored
records, global options, and recovery.

## Limits

- The cache includes tracked and non-ignored untracked file bytes, executable modes,
  HEAD, staged index entries, command arguments, repository path, and declared
  configuration. Ignored files and most environment variables require explicit
  input selection; read [cache identity](docs/cache-identity.md) before relying on
  a result.
- The project must stay unchanged while the command runs. Detected input changes
  produce an error instead of reusable success.
- Cancellation remains active through final input validation. The supervisor then
  blocks cancellation signals before deciding and publishing its terminal result;
  signals arriving after that [completion boundary](docs/lifecycle.md) do not change
  the completed verdict.
- Windows and shared/network filesystems are unsupported. See
  [operations and supported scope](docs/operations.md) for the full scope.

## Test

Run the self-contained regression suite with `make test`. Tested on macOS with
Bash 3.2 and Python 3.14 on Apple Silicon, and on Linux as an unprivileged user in
an Alpine container with Python 3.14.

## License and maintenance

Copyright 2026 Aditya Dalmia. Licensed under [Apache-2.0](LICENSE), with
[attribution](NOTICE) and [source provenance](PROVENANCE.md). This is a public
reference implementation, deprecated for new Claude Code integrations as of 2026-09-22. See the [release preparation index](docs/release/README.md),
[contributing guide](CONTRIBUTING.md), and [security contact](SECURITY.md).
