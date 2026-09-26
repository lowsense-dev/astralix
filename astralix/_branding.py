# ©️ LowSense, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/lowsense-dev/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

"""Names and local assets shared by astralix interfaces."""
from pathlib import Path

APP_NAME = "astralix Userbot"
REPO_URL = "https://github.com/lowsense-dev/astralix"
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "astralix.png"
BOT_AVATAR_PATH = LOGO_PATH.with_name("astralix-bot.png")
CHAT_AVATAR_PATH = LOGO_PATH.with_name("astralix-chat.png")


WORDMARK = (
    "              __             ___",
    "  ____ ______/ /__________ _/ (_)  __",
    " / __ `/ ___/ __/ ___/ __ `/ / / |/_/",
    "/ /_/ (__  ) /_/ /  / /_/ / / />  <",
    "\\__,_/____/\\__/_/   \\__,_/_/_/_/|_|",
)


def startup_banner(version, commit, branch, status, *, color=False, width=80):
    """Render a static wordmark; no figlet dependency or network at startup."""
    reset = "\033[0m" if color else ""
    muted = "\033[38;5;245m" if color else ""
    bright = "\033[1;37m" if color else ""
    palette = (193,) * len(WORDMARK)
    lines = [""]
    if width >= 44:
        for row, shade in zip(WORDMARK, palette):
            paint = f"\033[38;5;{shade}m" if color else ""
            lines.append(f"  {paint}{row}{reset}")
        lines.append(f"  {muted}U S E R B O T{reset}")
    else:
        lines.append(f"  {bright}{APP_NAME}{reset}")
    lines.append("")
    lines.append(f"  {muted}{'─' * min(48, max(12, width - 4))}{reset}")
    for label, value in (
        ("version", version),
        ("commit", commit[:7] if commit != "unknown" else "archive"),
        ("branch", branch),
        ("status", status),
    ):
        lines.append(f"  {muted}{label:<9}{reset}{bright}{value}{reset}")
    lines.append(f"  {muted}{'─' * min(48, max(12, width - 4))}{reset}")
    lines.append("")
    return "\n".join(lines)


LOGIN_STAGES = {
    "banner.txt": ("ACCOUNT SETUP", "Connect your Telegram account"),
    "2fa.txt": ("TWO-STEP VERIFICATION", "Enter your Telegram cloud password"),
    "success.txt": ("CONNECTED", "Your account is ready"),
    "download.txt": ("INSTALLATION", "Preparing astralix Userbot"),
}


def login_banner(stage, *, color=False, width=80):
    title, subtitle = LOGIN_STAGES[stage]
    reset = "\033[0m" if color else ""
    accent = "\033[38;5;193m" if color else ""
    muted = "\033[38;5;245m" if color else ""
    rows = [""]
    if width >= 44:
        for line, shade in zip(WORDMARK, (193,) * len(WORDMARK)):
            paint = f"\033[38;5;{shade}m" if color else ""
            rows.append(f"  {paint}{line}{reset}")
    rows += [
        "", f"  {accent}✦{reset} astralix Userbot", "",
        f"  {muted}{'─' * min(48, max(12, width - 4))}{reset}",
        f"  {accent}{title}{reset}", f"  {muted}{subtitle}{reset}", "",
    ]
    return "\n".join(rows)
