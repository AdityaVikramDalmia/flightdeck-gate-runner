# Contributing

Run `make test` before proposing a change. Use synthetic temporary fixtures and
keep tests independent of user accounts, global agent configuration, and network
services. Include a reproducer for behavior fixes and update the documented CLI
or failure contract when it changes.

This repository is a public reference implementation under Apache-2.0, deprecated for new Claude Code integrations as of 2026-09-22. Contributions
intentionally submitted for inclusion use that license unless explicitly stated otherwise. Do not import private operational data or credentials.

The GitHub workflow is manual (`workflow_dispatch`);
no cloud jobs run on push. Local validation is recorded in the companion examples
repository. Check account usage before starting paid cloud CI jobs.
