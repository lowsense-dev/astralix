#!/usr/bin/env bash
# ©️ LowSense, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/lowsense-dev/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

set -euo pipefail

APP_NAME="astralix"
MODULE_NAME="astralix"
REPO_URL="${ASTRALIX_REPO_URL:-https://github.com/lowsense-dev/astralix.git}"
VENV_DIR="${ASTRALIX_VENV_DIR:-.venv}"
LOG_FILE="astralix-install.log"

if [ "${SUDO_USER:-}" != "" ] && command -v sudo >/dev/null 2>&1; then
	RUN_AS_USER=(sudo -u "$SUDO_USER")
else
	RUN_AS_USER=()
fi

info() {
	printf "\033[0;34m%s\033[0m\n" "$1"
}

ok() {
	printf "\033[0;32m%s\033[0m\n" "$1"
}

fail() {
	printf "\033[1;31m%s\033[0m\n" "$1" >&2
	[ -f "$LOG_FILE" ] && cat "$LOG_FILE" >&2
	exit "${2:-1}"
}

run() {
	"$@" >>"$LOG_FILE" 2>&1
}

sudo_run() {
	if [ "$(id -u)" -eq 0 ]; then
		run "$@"
	elif command -v sudo >/dev/null 2>&1; then
		run sudo "$@"
	else
		fail "Root privileges or sudo are required to install system packages." 2
	fi
}

python_cmd() {
	if command -v python3 >/dev/null 2>&1; then
		printf "python3"
	elif command -v python >/dev/null 2>&1; then
		printf "python"
	else
		fail "Python is not installed." 2
	fi
}

install_system_packages() {
	info "Installing system packages..."

	if echo "${OSTYPE:-}" | grep -qE "^linux-android"; then
		run pkg update -y
		run pkg install -y \
			build-essential \
			curl \
			ffmpeg \
			git \
			libcairo \
			libffi \
			libjpeg-turbo \
			libwebp \
			ncurses-utils \
			openssl \
			python \
			uv
	elif command -v apt-get >/dev/null 2>&1; then
		sudo_run apt-get update
		sudo_run apt-get install -y \
			build-essential \
			curl \
			ffmpeg \
			git \
			imagemagick \
			libcairo2 \
			libffi-dev \
			libjpeg-dev \
			libmagic1 \
			libopenjp2-7 \
			libtiff-dev \
			libwebp-dev \
			libz-dev \
			python3 \
			python3-dev \
			python3-venv
	elif command -v pacman >/dev/null 2>&1; then
		sudo_run pacman -Sy --needed --noconfirm \
			base-devel \
			ffmpeg \
			file \
			git \
			imagemagick \
			python \
			uv
	elif command -v dnf >/dev/null 2>&1; then
		sudo_run dnf install -y \
			ffmpeg \
			file-libs \
			gcc \
			gcc-c++ \
			git \
			imagemagick \
			python3 \
			python3-devel \
			curl
	elif command -v brew >/dev/null 2>&1; then
		run brew install git jpeg webp uv
	else
		info "Unknown package manager, skipping system package installation."
	fi
}

check_python() {
	local py="$1"

	"$py" - <<'PY'
import sys

if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required")
PY
}

prepare_repo() {
	if [ -d "$MODULE_NAME" ] && [ -f "requirements.txt" ]; then
		return
	fi

	if [ -d "$APP_NAME/$MODULE_NAME" ]; then
		cd "$APP_NAME"
		return
	fi

	info "Cloning repo..."
	[ ! -e "$APP_NAME" ] || fail "Destination $APP_NAME already exists; refusing to overwrite it." 3
	"${RUN_AS_USER[@]}" git clone "$REPO_URL" "$APP_NAME" >>"$LOG_FILE" 2>&1 || fail "Clone failed." 3
	cd "$APP_NAME"
}

ensure_uv() {
	if UV_CMD="$("${RUN_AS_USER[@]}" sh -c 'command -v uv')"; then
		return
	fi

	local uv_dir installer
	uv_dir="$("${RUN_AS_USER[@]}" sh -c 'printf "%s" "$HOME/.local/bin"')"
	UV_CMD="$uv_dir/uv"
	if [ -x "$UV_CMD" ]; then
		return
	fi
	info "Installing uv..."
	installer="$(mktemp)"
	run curl -LsSf https://astral.sh/uv/install.sh -o "$installer" || fail "uv download failed." 4
	chmod 644 "$installer"
	"${RUN_AS_USER[@]}" env UV_UNMANAGED_INSTALL="$uv_dir" sh "$installer" >>"$LOG_FILE" 2>&1 || fail "uv installation failed." 4
	rm -f "$installer"
}

create_venv() {
	local py="$1"
	info "Creating virtual environment with uv..."
	"${RUN_AS_USER[@]}" "$UV_CMD" venv --python "$py" "$VENV_DIR" >>"$LOG_FILE" 2>&1 || fail "Virtual environment creation failed." 4
}

install_python_packages() {
	info "Installing Python dependencies with uv..."
	"${RUN_AS_USER[@]}" "$UV_CMD" pip install --python "$VENV_DIR/bin/python" --upgrade -r requirements.txt >>"$LOG_FILE" 2>&1 || fail "Requirements installation failed." 4
}

start_app() {
	info "Starting..."
	local git_args=()
	[ -d .git ] || git_args=(--no-git)
	"${RUN_AS_USER[@]}" "$VENV_DIR/bin/python" -m "$MODULE_NAME" "${git_args[@]}" "$@"
}

clear || true
[ ! -f assets/download.txt ] || cat assets/download.txt
printf "\033[3;34;40m Installing %s...\033[0m\n\n" "$APP_NAME"

: >"$LOG_FILE"

if [ "${SUDO_USER:-}" != "" ]; then
	chown "$SUDO_USER:" "$LOG_FILE" >/dev/null 2>&1 || true
fi

install_system_packages
PYTHON="$(python_cmd)"
prepare_repo
check_python "$PYTHON"
ensure_uv
create_venv "$PYTHON"
install_python_packages

touch .setup_complete
rm -f "$LOG_FILE"

ok "Installation complete."
start_app "$@"
