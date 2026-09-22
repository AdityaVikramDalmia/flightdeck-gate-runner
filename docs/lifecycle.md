# Lifecycle and durable records

A start takes a nonblocking operating-system advisory lock for its key. The same
open file descriptor is inherited by a detached supervisor and its command.
Coordination descriptors are always above standard input/output/error, so closing
a caller stream cannot cause child redirection to discard the lock.
Contending starts join the current attempt. `--force` bypasses terminal evidence;
it never starts over a lock held by a running attempt.

The command and supervisor run in separate sessions, disconnected from the
launcher's terminal and process group. Killing the launcher or timing out a
`wait` does not terminate the run. An interruption during the startup handoff can leave an `error` or `died` attempt;
no success is inferred before the command finishes. All standard input is `/dev/null`; interactive
commands are unsupported.

## Terminal states

- **pass**: command exit 0 and unchanged declared inputs.
- **fail**: nonzero command exit and unchanged declared inputs.
- **error**: launch/tool error, supervisor interruption, or changed inputs.
- **died**: no terminal record and no remaining lock holder.

A SIGTERM/SIGINT/SIGHUP accepted before the completion boundary records `error`.
While the command is active, cancellation also terminates its group, with a
SIGKILL fallback after two seconds. Cancellation remains accepted during final
input validation, even after a successful command exit. Once validation finishes,
the supervisor atomically blocks these three signals, checks accepted
interruptions again, and publishes the terminal result while they remain blocked.
This blocking operation is the completion boundary: signals arriving afterward
do not cancel the completed attempt or change its verdict. The already-reaped
command's historical PID is not targeted during final validation/publication.

SIGKILL allows no cleanup:
if the command still holds the inherited lock, status remains `running` and starts
continue joining. Once that lock is gone, status becomes `died`; the next start
creates a fresh attempt. The tool never guesses liveness from a reused PID.

The supervisor is not a full process-tree manager. Commands must stay in the
foreground and wait for their own children. A program that daemonizes, deliberately
closes inherited descriptors, or moves children into other sessions can outlive
this coordination model. Such commands are unsupported. Do not kill the command
by an unverified historical PID from a record.

## On-disk layout

The default store is `<git-common-dir>/gate-runner/`, shared by linked worktrees
but keyed separately for each canonical worktree path:

```text
gate-runner/
  latest/<worktree-digest>.json
  locks/<key>.lock
  runs/<key>/
    current.json
    attempts/<attempt-id>/
      request.json
      meta.json
      command.log
      supervisor.log
      result.json
```

`request.json` records command argv, input names, tree path, and digests. Command
environment values travel through an anonymous inherited pipe, are consumed before
the command starts, and are never written into a request file or supervisor argv. `meta.json`
contains timestamps and diagnostic PIDs. `result.json` contains the verdict,
original command exit code when available, completion timestamp, and error reason
when applicable. `command.log` merges stdout/stderr. `supervisor.log` records
unexpected interpreter diagnostics. Results and pointers are published with an
atomic rename and `fsync`; logs are streamed and may lose a final buffer on sudden
machine/power failure. No guarantee is made beyond local filesystem semantics.

Every rerun gets a new immutable attempt directory. The previous log and result
are retained; `current.json` points to the current attempt. Each worktree's latest
pointer means its most recently *created* attempt, not the most recently joined record. A status
read never reports an older terminal verdict while a new attempt holds its lock.

Do not delete lock files while any command can be using the store: deleting an
inode that is still locked defeats advisory locking. Store paths and records are
trusted local data, not an interface for untrusted writers or multiple machines.

Terminal records are checked before reuse: `pass` requires integer exit code 0,
`fail` requires a nonzero integer exit code, and terminal timestamps and error
reasons must have the expected types. Malformed JSON, pointers, or terminal
evidence produces tool error 6 rather than reusable success. This is consistency
validation of trusted local state, not tamper-proof attestation.
