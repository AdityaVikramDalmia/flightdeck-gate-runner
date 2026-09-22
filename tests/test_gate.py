import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

SOURCE = Path(__file__).resolve().parents[1]


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gate tests ")
        self.base = Path(self.tmp.name)
        self.root = self.base / "project with spaces"
        self.root.mkdir()
        self.tool = SOURCE / "bin" / "gate-run"
        self.git("init", "-q")
        self.git("config", "user.name", "Test Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.root / "source.txt").write_text("one\n")
        (self.root / ".gitignore").write_text("output/\nignored.txt\n")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")

    def tearDown(self):
        # A failed test must not leave detached workers running.
        for meta_file in (self.root / ".git" / "gate-runner").glob("runs/*/attempts/*/meta.json"):
            meta = json.loads(meta_file.read_text())
            for field in ("command_pid", "supervisor_pid"):
                if field in meta:
                    try:
                        os.killpg(meta[field], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)

    def run_gate(self, *args, expected=None, cwd=None, env=None):
        result = subprocess.run([str(self.tool), *args], cwd=cwd or self.root,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, timeout=20)
        if expected is not None:
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def record(self, *args, expected=None):
        result = self.run_gate("--json", *args, expected=expected)
        return json.loads(result.stdout)

    def key(self, *args):
        return self.run_gate("key", *args, expected=0).stdout.strip()

    def wait_meta(self, record, field="command_pid"):
        path = Path(record["path"]) / "meta.json"
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            meta = json.loads(path.read_text())
            if field in meta:
                return meta
            time.sleep(0.02)
        self.fail("worker did not publish " + field)

    def test_generic_pass_log_and_exact_exit(self):
        record = self.record("start", "--wait", "--shell", "printf 'hello\\n'; exit 0", expected=0)
        self.assertEqual(record["state"], "pass")
        self.assertEqual(record["exit_code"], 0)
        self.assertEqual(self.run_gate("log", expected=0).stdout, "hello\n")
        result = self.record("start", "--wait", "--shell", "exit 37", expected=1)
        self.assertEqual(result["exit_code"], 37)

    def test_green_words_never_override_nonzero(self):
        result = self.record("start", "--wait", "--shell", "echo 'ALL SUITES GREEN'; exit 9", expected=1)
        self.assertEqual(result["exit_code"], 9)

    def test_argv_preserves_spaces_and_metacharacters(self):
        text = "space 'quote' $HOME ; no expansion"
        self.record("start", "--wait", "--", sys.executable, "-c", "import sys; print(sys.argv[1])", text, expected=0)
        self.assertEqual(self.run_gate("log").stdout.strip(), text)

    def test_default_make_test(self):
        (self.root / "Makefile").write_text("test:\n\t@echo fixture-green\n")
        self.record("start", "--wait", expected=0)
        self.assertIn("fixture-green", self.run_gate("log").stdout)

    def test_untracked_content_and_binary_change_key(self):
        initial = self.key()
        file = self.root / "new file\nwith newline.bin"
        file.write_bytes(b"\x00first\xff")
        one = self.key()
        file.write_bytes(b"\x00second\xff")
        two = self.key()
        self.assertEqual(len({initial, one, two}), 3)

    def test_tracked_staged_unstaged_deletion_and_mode(self):
        first = self.key()
        file = self.root / "source.txt"
        file.write_text("two\n")
        second = self.key()
        self.git("add", "source.txt")
        self.assertNotEqual(self.key(), second)
        file.chmod(0o755)
        third = self.key()
        file.unlink()
        fourth = self.key()
        self.assertEqual(len({first, second, third, fourth}), 4)

    def test_command_environment_and_salt_identity(self):
        one = self.key("--shell", "true")
        self.assertNotEqual(one, self.key("--shell", "false"))
        self.assertNotEqual(one, self.key("--shell", "true", "--env", "MODE=one"))
        self.assertNotEqual(self.key("--env", "MODE=one"), self.key("--env", "MODE=two"))
        self.assertNotEqual(one, self.key("--shell", "true", "--salt", "compiler-v2"))
        env = os.environ.copy()
        env["GATE_TEST_VALUE"] = "alpha"
        a = self.run_gate("key", "--env-key", "GATE_TEST_VALUE", env=env).stdout
        env["GATE_TEST_VALUE"] = "beta"
        b = self.run_gate("key", "--env-key", "GATE_TEST_VALUE", env=env).stdout
        self.assertNotEqual(a, b)

    def test_explicit_environment_executes_without_recording_values(self):
        result = self.record("start", "--wait", "--env", "TOKEN=fixture-secret", "--shell",
                             'test "$TOKEN" = fixture-secret', expected=0)
        request = (Path(result["path"]) / "request.json").read_text()
        self.assertNotIn('"TOKEN"', request)

    def test_ignored_and_extra_inputs(self):
        first = self.key()
        file = self.root / "ignored.txt"
        file.write_text("one")
        self.assertEqual(first, self.key())
        extra = self.key("--input", "ignored.txt")
        file.write_text("two")
        self.assertNotEqual(extra, self.key("--input", "ignored.txt"))
        self.run_gate("key", "--input", "missing.txt", expected=6)

    def test_success_reuse_and_force_preserve_attempts(self):
        cmd = "mkdir -p output; echo run >> output/count"
        first = self.record("start", "--wait", "--shell", cmd, expected=0)
        second = self.record("start", "--wait", "--shell", cmd, expected=0)
        third = self.record("start", "--force", "--wait", "--shell", cmd, expected=0)
        self.assertEqual(first["attempt"], second["attempt"])
        self.assertNotEqual(second["attempt"], third["attempt"])
        self.assertEqual((self.root / "output/count").read_text(), "run\nrun\n")
        self.assertTrue((Path(first["path"]) / "result.json").is_file())

    def test_concurrent_starts_join_one_run_including_force(self):
        cmd = "mkdir -p output; echo run >> output/count; sleep 1"
        def contender(index):
            extra = ["--force"] if index % 2 else []
            return self.record("start", *extra, "--wait", "--shell", cmd, expected=0)
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(contender, range(10)))
        self.assertEqual(len({r["attempt"] for r in results}), 1)
        self.assertEqual((self.root / "output/count").read_text(), "run\n")

    def test_wait_timeout_does_not_cancel(self):
        result = self.record("start", "--wait", "--timeout", "0.05", "--shell", "sleep .4", expected=3)
        self.assertEqual(result["state"], "running")
        self.record("wait", result["key"], "--timeout", "3", expected=0)

    def test_sigterm_records_interruption(self):
        record = self.record("start", "--shell", "sleep 30", expected=0)
        meta = self.wait_meta(record)
        os.kill(meta["supervisor_pid"], signal.SIGTERM)
        result = self.record("wait", record["key"], "--timeout", "5", expected=6)
        self.assertEqual(result["state"], "error")
        self.assertIn("interrupted", result["reason"])

    def test_sigkill_supervisor_keeps_child_lock_then_reports_died(self):
        record = self.record("start", "--shell", "sleep 1.5", expected=0)
        meta = self.wait_meta(record)
        os.kill(meta["supervisor_pid"], signal.SIGKILL)
        running = self.record("status", record["key"], expected=3)
        self.assertEqual(running["state"], "running")
        joined = self.record("start", "--force", "--shell", "sleep 1.5", expected=0)
        self.assertEqual(record["attempt"], joined["attempt"])
        self.record("wait", record["key"], "--timeout", "5", expected=5)
        rerun = self.record("start", "--wait", "--shell", "sleep 1.5", expected=0)
        self.assertNotEqual(record["attempt"], rerun["attempt"])

    def test_caller_process_group_death_does_not_kill_worker(self):
        process = subprocess.Popen([str(self.tool), "--json", "start", "--wait", "--shell", "sleep .8"],
                                   cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        deadline = time.monotonic() + 5
        store = self.root / ".git/gate-runner"
        while time.monotonic() < deadline:
            latest = store / "latest"
            if latest.exists() and any(latest.glob("*.json")):
                current = self.record("status")
                if "path" in current:
                    self.wait_meta(current)
                    break
            time.sleep(.03)
        else:
            self.fail("worker did not start")
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate(timeout=3)
        self.record("wait", "--timeout", "5", expected=0)

    def test_input_mutation_never_caches_pass(self):
        result = self.record("start", "--wait", "--shell", "echo changed > source.txt", expected=6)
        self.assertEqual(result["state"], "error")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("inputs changed", result["reason"])

    def test_invalid_command_is_error(self):
        record = self.record("start", "--wait", "--", "definitely-missing-gate-command", expected=6)
        self.assertEqual(record["state"], "error")

    def test_missing_status_and_invalid_keys(self):
        self.record("status", expected=4)
        self.record("status", "0" * 64, expected=4)
        self.run_gate("status", "../../escape", expected=6)

    def test_subdirectory_resolves_same_root(self):
        sub = self.root / "output/subdirectory"
        sub.mkdir(parents=True)
        self.assertEqual(self.key(), self.run_gate("key", cwd=sub, expected=0).stdout.strip())

    def test_relocation_and_install_path_with_spaces(self):
        installed = self.base / "installed tool with spaces"
        shutil.copytree(SOURCE / "gate_runner", installed / "gate_runner")
        shutil.copytree(SOURCE / "bin", installed / "bin")
        self.tool = installed / "bin/gate-run"
        before = self.key()
        relocated = self.base / "relocated project"
        self.root.rename(relocated)
        self.root = relocated
        self.assertNotEqual(before, self.key())
        self.record("start", "--wait", "--shell", "true", expected=0)

    def test_custom_store_and_unsafe_store(self):
        external = self.base / "state directory with spaces"
        result = self.run_gate("--runs-dir", str(external), "--json", "start", "--wait", "--shell", "true", expected=0)
        self.assertTrue(json.loads(result.stdout)["path"].startswith(str(external.resolve())))
        self.run_gate("--runs-dir", "untracked-state", "start", expected=6)

    def test_worktree_isolation(self):
        other = self.base / "linked worktree"
        self.git("worktree", "add", "--detach", str(other))
        self.assertNotEqual(self.key(), self.run_gate("key", cwd=other, expected=0).stdout.strip())
        self.run_gate("start", "--wait", "--shell", "true", cwd=other, expected=0)

    def test_worktree_latest_status_and_listing_are_isolated(self):
        other = self.base / "second worktree"
        self.git("worktree", "add", "--detach", str(other))
        first = self.record("start", "--wait", "--shell", "true", expected=0)
        second = json.loads(self.run_gate("--json", "start", "--wait", "--shell", "false", cwd=other, expected=1).stdout)
        self.assertEqual(self.record("status", expected=0)["key"], first["key"])
        self.assertEqual(json.loads(self.run_gate("--json", "status", cwd=other, expected=1).stdout)["key"], second["key"])
        self.assertEqual([row["key"] for row in self.record("list", expected=0)], [first["key"]])
        self.assertEqual(len(self.record("list", "--all-worktrees", expected=0)), 2)

    def test_symlink_target_mode_changes_identity(self):
        target = self.base / "external-command"
        target.write_text("#!/bin/sh\nexit 0\n")
        target.chmod(0o644)
        (self.root / "external-link").symlink_to(target)
        initial = self.key()
        target.chmod(0o755)
        self.assertNotEqual(initial, self.key())

    def test_symlink_input_content_and_dangling_rejection(self):
        external = self.base / "external.txt"
        external.write_text("one")
        (self.root / "link.txt").symlink_to(external)
        first = self.key()
        external.write_text("two")
        self.assertNotEqual(first, self.key())
        external.unlink()
        self.run_gate("key", expected=6)

    def test_list_log_tail_and_json(self):
        self.record("start", "--wait", "--shell", "printf 'one\\ntwo\\nthree\\n'", expected=0)
        self.assertEqual(self.run_gate("log", "--tail", "2", expected=0).stdout, "two\nthree\n")
        self.assertEqual(self.run_gate("log", "--tail", "0", expected=0).stdout, "")
        listing = self.record("list", expected=0)
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]["state"], "pass")

    def test_stale_attempt_is_recovered_once_under_contention(self):
        cmd = "mkdir -p output; echo run >> output/count; sleep 1"
        key = self.key("--shell", cmd)
        store = self.root / ".git/gate-runner"
        attempt = store / "runs" / key / "attempts" / ("a" * 32)
        attempt.mkdir(parents=True)
        (attempt / "meta.json").write_text(json.dumps({"supervisor_pid": 99999999}))
        (attempt.parent.parent / "current.json").write_text(json.dumps({"attempt": attempt.name}))
        self.record("status", key, expected=5)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.record("start", "--wait", "--shell", cmd, expected=0), range(8)))
        self.assertEqual(len({r["attempt"] for r in results}), 1)
        self.assertNotEqual(results[0]["attempt"], attempt.name)
        self.assertTrue((attempt / "meta.json").exists())
        self.assertEqual((self.root / "output/count").read_text(), "run\n")

    def test_failed_attempt_reuses_failure_until_forced(self):
        first = self.record("start", "--wait", "--shell", "exit 17", expected=1)
        second = self.record("start", "--wait", "--shell", "exit 17", expected=1)
        self.assertEqual(first["attempt"], second["attempt"])
        third = self.record("start", "--force", "--wait", "--shell", "exit 17", expected=1)
        self.assertNotEqual(first["attempt"], third["attempt"])

    def test_non_git_and_unborn_repo_fail_honestly(self):
        self.run_gate("key", cwd=self.base, expected=6)
        unborn = self.base / "unborn"
        unborn.mkdir()
        subprocess.run(["git", "init", "-q", str(unborn)], check=True)
        self.run_gate("start", cwd=unborn, expected=6)

    def test_symlink_install_entry_point(self):
        installed = self.base / "install folder"
        shutil.copytree(SOURCE / "gate_runner", installed / "gate_runner")
        shutil.copytree(SOURCE / "bin", installed / "bin")
        link = self.base / "linked executable"
        link.symlink_to("install folder/bin/gate-run")
        self.tool = link
        self.run_gate("--version", expected=0)
        self.record("start", "--wait", "--shell", "true", expected=0)

    def test_system_bash_entry_point(self):
        result = subprocess.run(["/bin/bash", str(self.tool), "--json", "start", "--wait", "--shell", "true"],
                                cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["state"], "pass")

    def test_relative_path_resolution_uses_project_root(self):
        folder = self.root / "tools"
        folder.mkdir()
        executable = folder / "fixture-tool"
        executable.write_text("#!/bin/sh\necho root-tool\n")
        executable.chmod(0o755)
        nested = self.root / "output/nested"
        nested.mkdir(parents=True)
        env = os.environ.copy()
        env["PATH"] = "tools:" + env["PATH"]
        first = self.run_gate("key", "--", "fixture-tool", env=env, expected=0).stdout
        second = self.run_gate("key", "--", "fixture-tool", cwd=nested, env=env, expected=0).stdout
        self.assertEqual(first, second)
        self.run_gate("start", "--wait", "--", "fixture-tool", cwd=nested, env=env, expected=0)
        self.assertEqual(self.run_gate("log").stdout.strip(), "root-tool")

    def test_interrupt_kills_term_ignoring_descendant(self):
        import shlex
        script = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready',flush=True); time.sleep(30)"
        command = shlex.quote(sys.executable) + " -c " + shlex.quote(script) + " & wait"
        record = self.record("start", "--shell", command, expected=0)
        meta = self.wait_meta(record)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            path = Path(record["log"])
            if path.exists() and "ready" in path.read_text():
                break
            time.sleep(.02)
        else:
            self.fail("descendant did not start")
        os.kill(meta["supervisor_pid"], signal.SIGTERM)
        result = self.record("wait", record["key"], "--timeout", "5", expected=6)
        self.assertEqual(result["state"], "error")

    def test_invalid_timeouts(self):
        for value in ("-1", "nan", "inf"):
            self.run_gate("wait", "--timeout", value, expected=2)


if __name__ == "__main__":
    unittest.main()
