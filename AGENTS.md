# Gate Runner

Use [.agents/skills/gate-runner-maintainer/SKILL.md](.agents/skills/gate-runner-maintainer/SKILL.md)
for work in this repository. Contracts and installation start at [README.md](README.md).

- Preserve code-state and command identity, immutable attempts, detached-process ownership, and explicit exit evidence. A reused result covers only declared inputs; it is not a hermetic build.
- Release record: [docs/release/README.md](docs/release/README.md).
- Run `make test` and relevant documented demos before committing changes.
- Keep tests synthetic and isolated; preserve unrelated user edits.
- Keep source-history dates truthful and retain license/notice attribution.
- Public launch is deferred. Do not change visibility or modify the original
  Flightdeck runtime while preparing this component.

These are deprecated reference artifacts for new Claude Code integrations as of
2026-09-22. Preserve that status in README, examples, skills, and release material;
do not imply native feature equivalence without evidence.
