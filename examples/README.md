# Disposable example

From the Gate Runner checkout, capture its launcher path and create a small Git
project. The fixture identity is local to this repository:

```bash
GATE_RUN="$(pwd)/bin/gate-run"
DEMO_DIR="$(mktemp -d)"
cd "$DEMO_DIR"
git init -q
git config user.name 'Example Fixture'
git config user.email 'fixture@example.invalid'
printf 'output/\n' > .gitignore
printf 'example source\n' > source.txt
git add .
git commit -qm 'Initial fixture'

"$GATE_RUN" start --shell 'mkdir -p output; echo started >> output/count; sleep 2; echo finished'
"$GATE_RUN" start --shell 'mkdir -p output; echo started >> output/count; sleep 2; echo finished'
"$GATE_RUN" wait --timeout 10
"$GATE_RUN" log
cat output/count
```

Both starts join one command. The log prints `finished`; `output/count` contains
one `started` line. Repeating the same start after completion reuses the result.
Adding `--force` creates another retained attempt and another count line.

Edit an untracked source file to demonstrate cache invalidation:

```bash
"$GATE_RUN" key
printf 'new test input\n' > new-test.txt
"$GATE_RUN" key
printf 'changed test input\n' > new-test.txt
"$GATE_RUN" key
```

All three keys differ. Test outputs belong in the ignored `output/` directory so
they do not invalidate the run that generated them.
