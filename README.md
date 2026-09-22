# Gate Runner

> **Deprecated for new Claude Code integrations — 2026-09-22.** Retained as an
> Apache-2.0 reference project. Public launch remains deferred and the repository
> remains private. This is a maintainer status decision, not a claim that Claude
> Code replaces every capability. No ongoing feature work or support is promised.

Run a development command once for a Git code state, join an existing run, and
read its result after the launching terminal has gone away.

**Private release candidate: 0.1.0rc1.** Licensed under Apache-2.0; public launch is deferred.

Gate Runner records command output, the actual exit code, timestamps, and immutable
attempts under your repository's Git directory. Concurrent starts for the same
inputs share one command. A completed failure stays a failure, regardless of what
its log says. There is no service, account, notification integration, or model call.

## Requirements

- macOS, tested with Bash 3.2 and Python 3.14 on Apple Silicon.
- Linux, tested as an unprivileged user in an Alpine container with Python 3.14.
- Python **3.9 or newer**, Git, and Bash. No Python packages are required.
- A Git working tree with at least one commit, on a local filesystem.
- Windows and shared/network filesystems are unsupported.

## Install

From this checkout, install the complete launcher and module together:

```bash
mkdir -p "$HOME/.local/share/gate-runner" "$HOME/.local/bin"
cp -rf bin gate_runner "$HOME/.local/share/gate-runner/"
ln -sf "$HOME/.local/share/gate-runner/bin/gate-run" "$HOME/.local/bin/gate-run"
export PATH="$HOME/.local/bin:$PATH"
gate-run --version
```

Alternatively use the absolute path to `bin/gate-run` directly. Run the launcher
from the project you want to test. Installation and target paths may contain spaces.

## Use

```bash
cd /path/to/your/git-project

# Defaults to: make test. Returns as soon as the detached run starts.
gate-run start

# Join the latest run and return its verdict.
gate-run wait --timeout 120

gate-run status
gate-run log --tail 50
gate-run list
gate-run list --all-worktrees

# Explicit argv: no shell interpolation.
gate-run start --wait -- python3 -m unittest discover -s tests

# Shell syntax is opt-in.
gate-run start --wait --shell 'make lint && make test'

# Retry completed work while retaining every prior attempt.
gate-run start --force --wait --shell 'make lint && make test'
```

`start` without `--wait` returns 0 when work is launched or joined in progress.
For a cached terminal result it returns that result's status. `status`, `wait`, and
`start --wait` return: **0** pass, **1** command failure, **3** still running or wait
timeout, **4** no record, **5** supervisor disappeared without a result, **6** tool
error or interrupted/invalidated run. Usage errors return 2. A command's original
exit code is preserved separately, including negative signal numbers.

Use `--json` before the subcommand for structured records:

```bash
gate-run --json start --wait --env MODE=ci -- python3 -m unittest
gate-run --json status
```

The cache includes tracked and non-ignored untracked file bytes, executable modes,
HEAD, staged index entries, command arguments, repository path, and declared
configuration. Ignored files and most environment variables require explicit input
selection; read [cache identity](docs/cache-identity.md) before relying on a result.
The project must stay unchanged while the command runs. Detected input changes
produce an error instead of reusable success.

Cancellation remains active through final input validation. The supervisor then
blocks cancellation signals before deciding and publishing its terminal result;
signals arriving after that [completion boundary](docs/lifecycle.md) do not change
the completed verdict.

`status`, `wait`, and `log` default to the latest attempt created for the current
worktree. `list` also selects the current worktree; `list --all-worktrees` includes
every worktree sharing the state store.

```bash
gate-run start --wait --env-key CI --input .env.test --salt 'toolchain-2026-09' -- make test
```

Run the self-contained regression suite with `make test`.
See [the documentation index](docs/README.md) for lifecycle guarantees, stored
records, limits, and [a complete fixture example](examples/README.md).

## License and maintenance

Copyright 2026 Aditya Dalmia. Licensed under [Apache-2.0](LICENSE), with
[attribution](NOTICE) and [source provenance](PROVENANCE.md). Public launch is
deferred; repository access remains private. See the [release preparation index](docs/release/README.md),
[contributing guide](CONTRIBUTING.md), and [security contact](SECURITY.md).
