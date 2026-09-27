# Working on astralix

astralix Userbot is a Python Telegram userbot using `astralixtl`. The main
repository is https://git.astralix.cc/lowsense-dev/astralix; GitHub mirrors it at
https://github.com/lowsense-dev/astralix. The transport library `astralix-tl` has
its own repository and is not vendored here.

## Development conventions

- Work on `dev` unless the user explicitly requests another branch. Commit and
  push from the development checkout, not a production server.
- Do not bump versions or merge into `main` without an explicit request.
- Preserve existing authorship and license notices. New project code uses
  `© LowSense, 2026` and GNU AGPLv3; do not replace upstream license terms.
- Prefer focused file patches. Do not use broad search-and-replace scripts to
  rewrite source files or language packs.
- Do not add a `tests/` directory or a `docs/` directory unless requested.
  Public websites and relay deployment files are maintained outside this repo.
- Keep credentials, Telegram sessions, account configs, private signing keys,
  generated environments and runtime data out of commits and command output.
- Never restart an actual userbot, log into Telegram, or change production
  infrastructure merely to validate a local change.

## Commands

Python 3.10+ is supported. Dependencies belong in `pyproject.toml`; `uv.lock`
must be updated with dependency changes.

```sh
uv sync --locked
uv run --no-sync python -m astralix
uv run --no-sync python -m astralix --no-web
uv run --no-sync python -m compileall -q astralix tools
uv run --no-sync python tools/check_langpacks.py --base HEAD^
uv pip check
git diff --check
```

For uncommitted language changes use `--base HEAD`. Run checks appropriate to
the change. Use temporary fixtures outside the repository when a security or
recovery change requires a runtime check. Report what was actually verified.

Do not install dependencies during normal startup. `install.sh` handles initial
installation and optional systemd setup; `--systemd` only configures and enables
a service for an existing installation.

## Code map

- `astralix/__main__.py`, `main.py`: entry point, account lifecycle and dispatcher
  initialization. Importing `main` initializes application state and parses argv;
  use isolated arguments and data directories for import checks.
- `astralix/loader.py`, `modules/loader.py`: module lifecycle, `.lm`/`.dlm`, saved
  module sources, dependency installation and update prompts. Failed loading
  must not erase an installed module's source or registry entry.
- `astralix/_module_inventory.py`, `_module_archive.py`: module provenance,
  requirements, source hashes and import/export.
- `astralix/modules/updater.py`, `_updates.py`: manual update UI and preparation.
- `astralix/_release_runner.py`: release supervision, snapshots, health checks
  and recovery. It also runs as a standalone script outside the release tree.
- `astralix/_release_trust.py`, `_release_integrity.py`, `release-keys.json`:
  signature verification and release file integrity.
- `astralix/_web_login.py`, `_tunnel_login.py`, `web/`: local and tunnel login,
  including QR. Relay server code is deployed separately. Preserve session
  state across browser refreshes without reusing encryption nonces.
- `astralix/inline/`, `utils/messages.py`, `utils/rich.py`: Telegram rendering
  and media delivery. Rich and ordinary HTML are separate rendering paths.
- `astralix/langpacks/en.yml`, `ru.yml`: user-facing translations.
- `astralix/_internal.py`: shared security helpers, secret redaction and restart.
- `astralix/_diagnostics.py`: shareable reports built from an explicit allowlist.

## Update and release invariants

- `.update` checks for a published update, reports an already-current version,
  or shows changes and asks for confirmation. `-f` skips confirmation only.
  Do not introduce `check`, `prepare`, `apply` or `cancel` subcommands.
- Never fall through to installation when inline confirmation is unavailable.
- Pin the confirmed commit. If the selected release changes, require a fresh
  check instead of silently installing a different commit.
- Verify the signed manifest before dependency installation or candidate code
  execution. Enforce its channel, expiry, sequence and SHA-256 file inventory.
- Prepare a separate checkout and virtual environment. Do not reset or modify
  the running checkout/environment, or copy its entire `pip freeze` as module
  dependencies. Use declared/inferred module requirements and core constraints.
- Keep update locking and durable atomic writes. Recheck integrity before
  switching, require fresh account heartbeats and expected modules, and retain
  the last working release on failure.
- Reject incompatible data schemas. Do not silently restore old account data
  during a code rollback; data restoration requires an explicit user choice.
- Release signing is separate from CI and Forgejo. `release-keys.json` contains
  public keys only. Private keys remain on the signing machine with mode 0600.
- After validating a reviewed commit and pushing it to `dev` or `main`, the
  maintainer runs `tools/publish_release.py --channel <channel> --commit <SHA>`.
  It publishes signed metadata to `release-metadata` without a force push.
  An unsigned branch tip is not a published update. Metadata expires after
  30 days and must be renewed by the signer when necessary.
- Pin CI actions to commit SHAs; default workflow permissions are read-only.
  Do not give pull-request jobs release keys or production credentials.

## Interface and translations

- Update English and Russian together, including config descriptions and command
  help. Preserve matching format placeholders and valid HTML.
- `info` and `ping` use matching text in ordinary and rich modes. `astralix` and
  `help` retain their distinct rich layouts. Do not change custom user templates
  when changing defaults; `custom_message = None` selects the language pack.
- The info placeholder for the transport version is `{atl_version}`.
- Banner config defaults use repository raw URLs. Do not substitute local file
  paths or silently drop user-selected media.
- Keep styling and emoji consistent with astralix; do not reintroduce removed
  hosting integrations, community links or deleted language packs.
