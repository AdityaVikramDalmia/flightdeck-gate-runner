#!/usr/bin/env python3
"""Repository-local, durable coordination for trusted development commands."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid

VERSION = "0.1.0rc1"
CODES = {"pass": 0, "fail": 1, "running": 3, "missing": 4,
         "died": 5, "error": 6}


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def atomic(path, value):
    """Publish a complete JSON record, then flush the containing directory."""
    temporary = path.with_name(path.name + ".tmp." + uuid.uuid4().hex)
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(value, dict):
        raise ValueError("record must be a JSON object: " + str(path))
    return value


def terminal_result(path):
    value = read_json(path)
    if value is None:
        return None
    verdict = value.get("state")
    ended = value.get("ended")
    code = value.get("exit_code")
    try:
        valid_ended = type(ended) in (int, float) and math.isfinite(ended)
    except OverflowError:
        valid_ended = False
    if (verdict not in ("pass", "fail", "error")
            or not valid_ended
            or set(value) - {"state", "exit_code", "ended", "reason"}):
        raise ValueError("invalid terminal result: " + str(path))
    if verdict in ("pass", "fail"):
        if type(code) is not int or (code == 0) != (verdict == "pass"):
            raise ValueError("terminal verdict disagrees with command exit evidence: " + str(path))
    elif (("exit_code" in value and type(code) is not int)
          or not isinstance(value.get("reason"), str) or not value["reason"]):
        raise ValueError("invalid error result: " + str(path))
    if "reason" in value and not isinstance(value["reason"], str):
        raise ValueError("invalid result reason: " + str(path))
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":")).encode()).hexdigest()


def file_identity(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return ["missing"]
    mode = stat.S_IMODE(info.st_mode)
    if stat.S_ISLNK(info.st_mode):
        # The target spelling and target bytes both matter to a command following it.
        target = os.readlink(path)
        if path.is_file():
            return ["symlink", target, stat.S_IMODE(path.stat().st_mode), hashlib.sha256(path.read_bytes()).hexdigest()]
        raise ValueError("directory or dangling symlinks are unsupported inputs: " + str(path))
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("non-regular input (including submodules) is unsupported: " + str(path))
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return ["file", mode, hasher.hexdigest()]


def snapshot(root, extras):
    head = git(root, "rev-parse", "HEAD").strip().decode("ascii")
    entries = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    files = []
    for name in sorted(set(entries.split(b"\0")) - {b""}):
        text = os.fsdecode(name)
        files.append([text, file_identity(root / text)])
    for name in sorted(set(extras)):
        path = Path(name)
        if not path.is_absolute():
            path = root / path
        if not path.exists() and not path.is_symlink():
            raise ValueError("extra input does not exist: " + str(path))
        files.append(["extra:" + str(path.absolute()), file_identity(path)])
    index = git(root, "ls-files", "--stage", "-z")
    return digest({"head": head, "index": hashlib.sha256(index).hexdigest(), "files": files})


def resolve():
    root = Path(os.fsdecode(git(Path.cwd(), "rev-parse", "--show-toplevel")[:-1])).resolve()
    common = Path(os.fsdecode(git(root, "rev-parse", "--git-common-dir")[:-1]))
    if not common.is_absolute():
        common = root / common
    return root, common.resolve()


def environment(args):
    env = os.environ.copy()
    names = set(args.env_key) | {"PATH"}
    for entry in args.env:
        name, sep, value = entry.partition("=")
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError("--env expects NAME=VALUE")
        env[name] = value
        names.add(name)
    return env, {name: env.get(name) for name in sorted(names)}


def config(args, root):
    env, selected = environment(args)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if args.shell is not None:
        if command:
            raise ValueError("use either --shell or a command after --")
        command = ["/bin/bash", "-c", args.shell]
    command = command or ["make", "test"]
    search_path = os.pathsep.join(
        str(root / component) if not os.path.isabs(component) else component
        for component in env.get("PATH", os.defpath).split(os.pathsep))
    executable = shutil.which(command[0], path=search_path)
    # Relative executable resolution follows the repository root, as execution does.
    if os.sep in command[0]:
        executable = str((root / command[0]).resolve())
    identity = {"schema": 2, "version": VERSION, "tree": str(root), "command": command,
                "executable": executable, "environment": selected,
                "salt": args.salt, "inputs": args.input}
    state = snapshot(root, args.input)
    key = digest({"config": identity, "snapshot": state})
    # Values of environment variables are never persisted in records.
    request = {"key": key, "tree": str(root), "command": command,
               "inputs": args.input, "snapshot": state,
               "configuration_digest": digest(identity)}
    return key, request, env


def latest_file(store, root):
    return store / "latest" / (digest({"tree": str(root)}) + ".json")


def above_stdio(descriptor):
    """Inherited coordination descriptors must survive child stdio redirection."""
    if descriptor >= 3:
        return descriptor
    replacement = fcntl.fcntl(descriptor, fcntl.F_DUPFD_CLOEXEC, 3)
    os.close(descriptor)
    return replacement


def open_lock(store, key):
    locks = store / "locks"
    locks.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(locks / (key + ".lock")), os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
    try:
        descriptor = above_stdio(descriptor)
        return os.fdopen(descriptor, "a+b")
    except BaseException:
        os.close(descriptor)
        raise


def take_lock(stream):
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def current_attempt(store, key):
    pointer = read_json(store / "runs" / key / "current.json")
    if pointer is None:
        return None
    attempt = pointer.get("attempt")
    if not isinstance(attempt, str) or not re.fullmatch(r"[0-9a-f]{32}", attempt):
        raise ValueError("invalid attempt pointer")
    return store / "runs" / key / "attempts" / attempt


def state(store, key):
    with open_lock(store, key) as lock:
        acquired = take_lock(lock)
        attempt = current_attempt(store, key)
        if attempt is None:
            return {"key": key, "state": "running" if not acquired else "missing"}
        meta = read_json(attempt / "meta.json") or {}
        base = {"key": key, "attempt": attempt.name, "path": str(attempt),
                "tree": meta.get("tree"),
                "log": str(attempt / "command.log"), "started": meta.get("started")}
        if not acquired:
            # A surviving command inherits the lock: never start overlapping work
            # just because its supervisor died. Terminal result becomes visible
            # only when every process holding the descriptor has released it.
            return dict(base, state="running")
        result = terminal_result(attempt / "result.json")
        if result:
            return dict(base, **result)
        return dict(base, state="died", reason="no terminal record and no live lock holder")


def emit(record, as_json=False):
    if as_json:
        print(json.dumps(record, sort_keys=True))
    else:
        suffix = " exit=" + str(record["exit_code"]) if "exit_code" in record else ""
        print(record["key"] + " " + record["state"] + suffix)
        if record.get("reason"):
            print(record["reason"])
        if record.get("log"):
            print("log: " + record["log"])
    return CODES[record["state"]]


def wait_for(store, key, timeout):
    deadline = time.monotonic() + timeout if timeout is not None else None
    while True:
        record = state(store, key)
        if record["state"] != "running":
            return record
        if deadline is not None and time.monotonic() >= deadline:
            record["reason"] = "wait timeout; the command continues in the background"
            return record
        time.sleep(0.1)


def start(args, store, key, request, env):
    with open_lock(store, key) as lock:
        if not take_lock(lock):
            return wait_for(store, key, args.timeout) if args.wait else state(store, key)
        old = current_attempt(store, key)
        old_result = terminal_result(old / "result.json") if old and not args.force else None
        if old_result is not None and not args.force:
            # Cannot call state while this descriptor holds the lock.
            return dict(old_result, key=key, attempt=old.name, path=str(old),
                        tree=request["tree"], log=str(old / "command.log"))
        attempt = store / "runs" / key / "attempts" / uuid.uuid4().hex
        attempt.mkdir(parents=True)
        atomic(attempt / "request.json", request)
        atomic(attempt / "meta.json", {"started": time.time(), "starter_pid": os.getpid(), "tree": request["tree"]})
        atomic(store / "runs" / key / "current.json", {"attempt": attempt.name})
        latest = latest_file(store, request["tree"])
        latest.parent.mkdir(parents=True, exist_ok=True)
        atomic(latest, {"key": key})
        try:
            # Command overrides must not configure the supervisor's interpreter or
            # its Git snapshot commands. Transfer the command environment through
            # an anonymous pipe; never write it into an on-disk request or argv.
            read_fd, write_fd = os.pipe()
            try:
                read_fd = above_stdio(read_fd)
                write_fd = above_stdio(write_fd)
                with (attempt / "supervisor.log").open("ab", buffering=0) as log:
                    subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                      "_supervise", str(attempt), str(lock.fileno()), str(read_fd)],
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                     cwd=str(request["tree"]), start_new_session=True,
                                     pass_fds=(lock.fileno(), read_fd))
                os.close(read_fd)
                read_fd = None
                stream = os.fdopen(write_fd, "w", encoding="utf-8")
                write_fd = None
                with stream:
                    json.dump(env, stream, ensure_ascii=True)
            finally:
                if read_fd is not None:
                    os.close(read_fd)
                if write_fd is not None:
                    os.close(write_fd)
        except OSError as exc:
            atomic(attempt / "result.json", {"state": "error", "ended": time.time(),
                                              "reason": "cannot launch supervisor: " + str(exc)})
    return wait_for(store, key, args.timeout) if args.wait else state(store, key)


def supervise(attempt, descriptor, environment_descriptor):
    # The inherited descriptor holds the same open-file-description lock acquired
    # by start. Never unlock it explicitly: close on exit, including SIGKILL.
    child = None
    interrupted = []

    def abort(signum, frame):
        interrupted.append(signum)
        if child is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGTERM)

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, abort)
    result = None
    try:
        request = read_json(attempt / "request.json")
        meta = read_json(attempt / "meta.json")
        if request is None or meta is None:
            raise ValueError("supervisor request or metadata is missing")
        meta["supervisor_pid"] = os.getpid()
        atomic(attempt / "meta.json", meta)
        with os.fdopen(environment_descriptor, "r", encoding="utf-8") as stream:
            command_environment = json.load(stream)
        if (not isinstance(command_environment, dict)
                or any(not isinstance(k, str) or not isinstance(v, str)
                       for k, v in command_environment.items())):
            raise ValueError("invalid command environment transfer")
        if interrupted:
            raise RuntimeError("interrupted before launch")
        with (attempt / "command.log").open("ab", buffering=0) as log:
            child = subprocess.Popen(request["command"], cwd=request["tree"],
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                     env=command_environment, start_new_session=True,
                                     pass_fds=(descriptor,))
            meta["command_pid"] = child.pid
            atomic(attempt / "meta.json", meta)
            while child.poll() is None:
                if interrupted:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(child.pid, signal.SIGKILL)
                time.sleep(0.05)
            rc = child.returncode
            if interrupted:
                # The group may outlive its leader when a child ignores TERM.
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(child.pid, signal.SIGKILL)
        result = {"state": "pass" if rc == 0 else "fail", "exit_code": rc}
        if interrupted:
            result.update(state="error", reason="supervisor interrupted by signal " + str(interrupted[0]))
        elif snapshot(Path(request["tree"]), request["inputs"]) != request["snapshot"]:
            result.update(state="error", reason="repository inputs changed during the run; result is not reusable")
    except Exception as exc:
        result = {"state": "error", "reason": str(exc)}
        if child is not None and child.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
            child.wait()
    result["ended"] = time.time()
    atomic(attempt / "result.json", result)
    os.close(descriptor)


def main():
    if len(sys.argv) == 5 and sys.argv[1] == "_supervise":
        supervise(Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--runs-dir", type=Path, help="state directory; default: Git common dir/gate-runner")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("start", "key"):
        item = sub.add_parser(action)
        item.add_argument("--shell", help="execute a string with /bin/bash -c")
        item.add_argument("--env", action="append", default=[], metavar="NAME=VALUE")
        item.add_argument("--env-key", action="append", default=[], metavar="NAME")
        item.add_argument("--input", action="append", default=[], help="extra file included in cache identity")
        item.add_argument("--salt", default="", help="explicit toolchain/external dependency identity")
        if action == "start":
            item.add_argument("--force", action="store_true", help="retry a terminal record; never overlap a live run")
            item.add_argument("--wait", action="store_true")
            item.add_argument("--timeout", type=float, help="seconds to wait; job continues afterward")
        item.add_argument("command", nargs=argparse.REMAINDER, help="-- COMMAND [ARG ...]; default make test")
    for action in ("status", "wait", "log"):
        item = sub.add_parser(action)
        item.add_argument("key", nargs="?", default="latest")
        if action == "wait":
            item.add_argument("--timeout", type=float)
        if action == "log":
            item.add_argument("--tail", type=int)
    listing = sub.add_parser("list")
    listing.add_argument("--all-worktrees", action="store_true", help="include other worktrees sharing the state store")
    args = parser.parse_args()
    if getattr(args, "timeout", None) is not None:
        if not math.isfinite(args.timeout) or args.timeout < 0:
            parser.error("--timeout must be finite and nonnegative")
    if getattr(args, "tail", None) is not None and args.tail < 0:
        parser.error("--tail must be nonnegative")
    root, common = resolve()
    store = (args.runs_dir or common / "gate-runner").resolve()
    # State inside the worktree could change its own identity every time it runs.
    if store == root or root in store.parents:
        if store != common and common not in store.parents:
            raise ValueError("--runs-dir must be outside the working tree or inside its Git directory")
    if args.action in ("key", "start"):
        key, request, env = config(args, root)
        if args.action == "key":
            print(key)
            return 0
        record = start(args, store, key, request, env)
        code = emit(record, args.json)
        return 0 if not args.wait and code == 3 else code
    if args.action == "list":
        runs = store / "runs"
        records = [state(store, path.name) for path in sorted(runs.iterdir())] if runs.exists() else []
        if not args.all_worktrees:
            records = [record for record in records if record.get("tree") == str(root)]
        if args.json:
            print(json.dumps(records, sort_keys=True))
        else:
            for record in records:
                emit(record)
        return 0
    key = args.key
    if key == "latest":
        latest = read_json(latest_file(store, root))
        if latest is None:
            return emit({"key": "latest", "state": "missing"}, args.json)
        key = latest["key"]
    if not isinstance(key, str) or not re.fullmatch("[0-9a-f]{64}", key):
        raise ValueError("key must be 64 lowercase hexadecimal characters or 'latest'")
    if args.action == "log":
        attempt = current_attempt(store, key)
        if attempt is None:
            return 4
        path = attempt / "command.log"
        if not path.exists():
            return 3 if state(store, key)["state"] == "running" else 5
        with path.open("rb") as stream:
            if args.tail is None:
                shutil.copyfileobj(stream, sys.stdout.buffer)
            elif args.tail:
                import collections
                sys.stdout.buffer.writelines(collections.deque(stream, maxlen=args.tail))
        return 0
    record = wait_for(store, key, args.timeout) if args.action == "wait" else state(store, key)
    return emit(record, args.json)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError) as error:
        print("gate-run: " + str(error), file=sys.stderr)
        sys.exit(6)
