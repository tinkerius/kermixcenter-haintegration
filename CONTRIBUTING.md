# Contribution guidelines

Contributing to this project should be as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features

## Github is used for everything

Github is used to host code, to track issues and feature requests, as well as accept pull requests.

Pull requests are the best way to propose changes to the codebase.

1. Fork the repo and create your branch from `main`.
2. If you've changed something, update the documentation.
3. Make sure your code lints (using `scripts/lint`).
4. Test you contribution.
5. Issue that pull request!

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be under the same [MIT License](http://choosealicense.com/licenses/mit/) that covers the project. Feel free to contact the maintainers if that's a concern.

## Report bugs using Github's [issues](../../issues)

GitHub issues are used to track public bugs.
Report a bug by [opening a new issue](../../issues/new/choose); it's that easy!

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

People *love* thorough bug reports. I'm not even kidding.

## Use a Consistent Coding Style

Run `scripts/lint` (which runs [ruff](https://docs.astral.sh/ruff/) format and
check) before submitting. CI enforces it.

## Test your code modification

This custom component was bootstrapped from the
[integration_blueprint template](https://github.com/ludeeus/integration_blueprint).

It comes with a development environment in a container, easy to launch if you use
Visual Studio Code. With this container you get a standalone Home Assistant
instance running, already configured with the included
[`configuration.yaml`](./config/configuration.yaml). Run `scripts/develop` to
start it.

## Developing with Claude Code

The repository ships with a [Claude Code](https://claude.com/claude-code) setup, so an AI
assistant can pick up the project context without re-deriving it:

- [`CLAUDE.md`](./CLAUDE.md) — architecture, commands, invariants and gotchas (worth reading
  as a human, too).
- [`.claude/settings.json`](./.claude/settings.json) — shared permissions (lint, probe, read-only
  git are pre-approved; `.env` and `config/.storage/` are blocked) and a hook that runs
  `ruff format` on every edited Python file.
- [`.claude/skills/`](./.claude/skills) — project workflows: `/add-datapoint`,
  `/add-endpoint`, `/run`.

The devcontainer installs Claude Code automatically; run `claude` in the terminal. Personal
overrides go in `CLAUDE.local.md` or `.claude/settings.local.json` (both gitignored). If
you learn something new about the portal API, put it in [`docs/api.md`](./docs/api.md) and,
if it's an invariant, in `CLAUDE.md` — not only in your private Claude memory.

## License

By contributing, you agree that your contributions will be licensed under its MIT License.
