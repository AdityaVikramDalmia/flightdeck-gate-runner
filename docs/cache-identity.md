# Cache identity

The key is a full SHA-256 digest of these inputs:

| Input | Included behavior |
| --- | --- |
| Repository | Canonical absolute worktree path; different worktrees never join |
| Git | HEAD commit ID and the staged index entries, including conflict stages |
| Working files | Every tracked and non-ignored untracked filename, bytes, and permission mode |
| Symlinks | Link target spelling, regular-file target bytes, and target permission mode |
| Command | Exact argv; `--shell` becomes `/bin/bash -c STRING` |
| Executable | Resolved executable path |
| Environment | `PATH`, every `--env NAME=VALUE`, and every `--env-key NAME` |
| Additional inputs | Each `--input FILE`, including ignored or external regular files |
| Explicit version | The `--salt STRING` value and Gate Runner version |

Untracked files are hashed by content, including binary files and filenames with
spaces or newlines. Staging an edit changes the key even when working bytes stay
the same. Ignored files are excluded unless tracked or explicitly selected using
`--input`. Empty directories do not contribute. Submodules, non-regular files,
and directory/dangling symlinks are rejected, rather than silently omitted.

The command runs from the repository root even when launched in a subdirectory.
A relative `--input` is interpreted relative to that root. Commands and inputs
are never evaluated while computing a key. `key` accepts the same command,
environment, input, and salt options as `start`:

```bash
gate-run key --env MODE=ci -- python3 -m unittest
gate-run start --wait --env MODE=ci -- python3 -m unittest
```

## Environment and external dependencies

The command inherits the caller's complete environment. Only declared variables
and `PATH` enter the identity. Declare all variables affecting results, including
locale, feature flags, credentials selecting a remote test dataset, and runtime
search paths. `--env-key NAME` hashes the inherited value; `--env NAME=VALUE` sets
and hashes a value. Selected environment values are not written into records,
although a command may print them itself. Command arguments and shell strings
are recorded, so avoid putting secrets there.

Tool binary contents, package caches, remote service state, clock time, global Git
configuration, and the contents of ignored build directories are not automatically
fingerprinted. Use `--input` for files and `--salt` for toolchain, dependency, or
external dataset versions. Use `--force` to deliberately repeat completed work.
For time-sensitive checks, set a fresh salt or force a rerun.

## Mutable worktrees

This tool runs against the live working tree; it does not create a source snapshot
or sandbox. It hashes inputs before launch and after the command ends. A mismatch
produces state `error`, even if the command returned 0. Generated output should go
into an ignored directory or outside the worktree.

Hashing is not an atomic filesystem snapshot. A concurrent edit, especially one
that is reverted before the final check, can escape detection. Keep the working
tree and declared inputs stable during execution. Other Git internal state beyond
HEAD/index entries (for example reflogs and branch names) is not tracked. Commands
whose result depends on those values need a suitable salt.
