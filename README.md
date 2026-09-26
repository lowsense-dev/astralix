<div align="center">
<img src="assets/astralix.png" alt="astralix Userbot" width="520">
</div>

# astralix Userbot

Telegram userbot with **astralix-tl**, installed from [PyPI](https://pypi.org/project/astralix-tl/).
[Project repository](https://git.astralix.cc/lowsense-dev/astralix). Both repositories are public. There are no project Telegram channels or support chats.

## Install from the source directory

Install Python 3.10+ and uv, then run from this directory:

```bash
uv sync --locked --inexact
.venv/bin/python -m astralix --no-git
```

The `--no-git` option is required for an archive checkout. Dependencies are installed explicitly; starting the application does not install or update packages. Optional dependencies:

```bash
uv sync --locked --inexact --all-extras
```

Explicit module installation and explicit application updates may install dependencies through uv. Third-party modules execute with the same privileges as the userbot; review their source before loading them.

Dependencies are defined in `pyproject.toml` and pinned in `uv.lock`. `requirements.txt` is a generated compatibility export for older updaters. After changing dependencies, run `uv lock` and `uv export --locked --no-hashes --no-emit-project --output-file requirements.txt`.

On first login, choose the RU/EN web interface through `tunnel.astralix.cc` or locally on `127.0.0.1`. The choice is saved. Use `--web-mode tunnel` or `--web-mode local` to change it, or `--no-web` for interactive console login. Tunnel links expire after 15 minutes and allow one browser connection; restart login for a new link if disconnected.

Existing Heroku data is not automatically renamed: keep its backup and use a separate data directory for the rebranded application until migration is reviewed.

## Development

```bash
uv pip check --python .venv/bin/python
```

See [upstream attribution](THIRD_PARTY_NOTICES.md). The userbot retains its AGPL-3.0 license; the separately installed Telegram library retains its MIT license.
