# astralix: architecture and targeted security review

## Scope

Reviewed the local dev archive's entrypoint, lifecycle, dispatcher/security, loader, library imports, updater, inline account login, database/session storage, installation scripts, and the vendored Telegram transport/authentication/download/upload code. This is a source review with local regression checks, not an exhaustive audit or a live Telegram penetration test.

## Architecture and dependencies

`astralix.__main__` validates dependencies and starts `main`; the dispatcher routes commands through permission checks, the loader executes modules and their libraries, and the inline manager routes Telegram UI callbacks. The database stores configuration and account state. `modules/astralix_web.py` implements inline account management; this archive does not contain a standalone HTTP web server.

All dependency installation call sites use uv with the current interpreter explicitly selected. Startup installation and hash-based reinstall/restart are removed. A missing dependency results in an actionable error and exit. Startup module restoration and its nested library loads cannot invoke the installer. Explicit module installation and explicit updates retain dependency installation through uv. Requirements remain the runtime manifest; uv sync is deliberately not used because it would remove packages installed for plugins.

## Patched boundaries

- Transport: packet bounds before body allocation, bounded gzip decompression, rejection of malformed TL byte/vector encodings.
- Authentication: explicit checks instead of assert; decrypted DH response hash verification and a pinned Telegram DH prime/generator set. MTProto plaintext/ciphertext lengths, authenticated payload lengths and padding validated, constant-time message-key comparison.
- Web documents: HTTPS certificate validation, public-address URL/DNS filtering on each redirect, rejection of private/loopback/link-local targets, connection/total timeouts and a 256 MiB streamed output limit. Packet and decompressed gzip limits are 16 MiB. These limits may reject previously accepted large inputs.
- Sessions: POSIX mode 0600, regular-file checks and symlink rejection. Renamed/base64 session payload inspection works without optional aiofiles. This does not sandbox arbitrary third-party code.
- Inline login: callbacks tied to their target actor, per-session serialization, one-time completion, five-minute lifetime, cleanup after failures/expiry/unload and replacement of an earlier login. Existing dispatcher permission checks remain in place. Account-switch and ordinary add-account behavior still require a live end-to-end check.
- Fork operation: removed remote beta-allowlist enforcement that could reset a checkout and log out an account. Removed upstream broadcast polling, project-channel promotion and automatic project-channel joins.

## Branding and state compatibility

Application: astralix Userbot. Distribution: astralix-tl. Import namespaces: astralix and astralixtl. Project links point to radiocycle/astralix and radiocycle/astralix-tl. There are no project community channels or chats. Telegram service channels used for private backups/assets are application storage, not community links.

Licenses and upstream copyright notices are preserved. Original URLs in source headers and attribution identify provenance. Copyright notices for astralix modifications supplement them.

The rebrand changes environment-variable prefixes, module identifiers, session prefixes and database namespaces. Existing Heroku account data is not automatically migrated. Keep its backup and use a separate data root until that migration is reviewed. Third-party modules hardcoding old imports may require changes.

## Validation and limits

Regression tests cover installer argument boundaries and startup policy, missing dependencies, account-login actor/expiry/replay checks, gzip/packet/TL limits, invalid authentication responses, MTProto padding, web URL/DNS filtering, session permissions/symlinks and disguised session uploads. Run both ordinary Python and `python -O`. YAML, Python and shell syntax are checked; the CLI help path is exercised without login.

The patched library is built and installed locally from source. No Docker daemon or live Telegram credentials are used for testing. Tests do not establish the absence of other vulnerabilities. Dynamic plugins, terminal/eval commands and explicit remote-code installations retain full process privileges.
