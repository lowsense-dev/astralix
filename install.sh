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
SYSTEMD_ONLY=false
SERVICE_UNIT=""
APP_ARGS=()
for arg in "$@"; do
	if [ "$arg" = --systemd ]; then
		SYSTEMD_ONLY=true
	else
		APP_ARGS+=("$arg")
	fi
done
set -- "${APP_ARGS[@]}"

if [ "${SUDO_USER:-}" != "" ] && command -v sudo >/dev/null 2>&1; then
	RUN_AS_USER=(sudo -H -u "$SUDO_USER")
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

	if command -v apt-get >/dev/null 2>&1; then
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
	if [ -d "$MODULE_NAME" ] && [ -f "pyproject.toml" ]; then
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
	"${RUN_AS_USER[@]}" env UV_PROJECT_ENVIRONMENT="$VENV_DIR" "$UV_CMD" sync --locked --inexact --python "$VENV_DIR/bin/python" >>"$LOG_FILE" 2>&1 || fail "Dependency sync failed." 4
}

start_app() {
	info "Starting..."
	local git_args=()
	[ -d .git ] || git_args=(--no-git)
	[ "$("${RUN_AS_USER[@]}" id -u)" -ne 0 ] || git_args+=(--root)
	if ( : </dev/tty ) 2>/dev/null; then
		"${RUN_AS_USER[@]}" "$VENV_DIR/bin/python" -m "$MODULE_NAME" "${git_args[@]}" "$@" </dev/tty
	else
		"${RUN_AS_USER[@]}" "$VENV_DIR/bin/python" -m "$MODULE_NAME" "${git_args[@]}" "$@"
	fi
}

check_service_stopped() {
	local -a ctl=(systemctl)
	command -v systemctl >/dev/null 2>&1 || return 0
	[ "$(id -u)" -eq 0 ] || ctl+=(--user)
	if "${ctl[@]}" is-active --quiet "$SERVICE_UNIT"; then
		fail "Stop the running service before reinstalling: ${ctl[*]} stop $SERVICE_UNIT" 5
	fi
}

ask_yes_no() {
	local answer
	while true; do
		printf '%s [y/N]: ' "$1" >/dev/tty
		IFS= read -r answer </dev/tty || return 1
		case "$answer" in
			[yY]|[yY][eE][sS]|да|Да) return 0 ;;
			''|[nN]|[nN][oO]|нет|Нет) return 1 ;;
			*) printf 'Please answer y or n.\n' >/dev/tty ;;
		esac
	done
}

# systemd quoting is different from shell quoting. Escape specifiers as well
# as ExecStart's environment expansion; never interpolate arguments into a shell.
unit_quote() {
	local value="$1"
	value=${value//\\/\\\\}
	if [ "${2:-}" != path ]; then value=${value//\"/\\\"}; fi
	value=${value//%/%%}
	value=${value//$'\n'/\\n}
	value=${value//$'\r'/\\r}
	value=${value//$'\t'/\\t}
	if [ "${2:-}" = path ]; then printf '%s' "$value"; else printf '"%s"' "$value"; fi
}

exec_quote() {
	local value="$1"
	unit_quote "${value//\$/\$\$}"
}

set_service_unit() {
	local name="${1##*/}"
	case "$name" in
		''|*[!a-zA-Z0-9_.:@-]*)
			command -v systemd-escape >/dev/null 2>&1 \
				|| fail "Cannot derive a valid systemd unit name from the installation directory." 5
			name="$(systemd-escape -- "$name")"
			;;
	esac
	SERVICE_UNIT="$name.service"
}

configure_service() {
	if ! command -v systemctl >/dev/null 2>&1 || [ ! -d /run/systemd/system ]; then
		[ "$SYSTEMD_ONLY" = false ] || fail "--systemd requires a running systemd installation." 5
		info "systemd is unavailable; starting astralix without a service."
		return
	fi
	if [ "$SYSTEMD_ONLY" = false ] && ! ( : </dev/tty ) 2>/dev/null; then
		info "No interactive terminal; skipping optional systemd setup."
		return
	fi
	local unit_dir target account account_home work_dir python_path unit_file temp_file arg
	local -a ctl=(systemctl) app_args=(-m "$MODULE_NAME")
	account="$("${RUN_AS_USER[@]}" id -un)"
	account_home="$("${RUN_AS_USER[@]}" sh -c 'printf "%s" "$HOME"')"
	work_dir="$(pwd -P)"
	set_service_unit "$work_dir"
	if [ "$SYSTEMD_ONLY" = false ]; then
		ask_yes_no "Create systemd unit $SERVICE_UNIT?" || return 0
	fi
	# Do not resolve the python symlink: that would bypass the virtual environment.
	python_path="$(cd "$VENV_DIR/bin" && pwd -P)/python"
	if [ "$(id -u)" -eq 0 ]; then
		unit_dir=/etc/systemd/system
		target=multi-user.target
	else
		unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
		target=default.target
		ctl+=(--user)
	fi
	unit_file="$unit_dir/$SERVICE_UNIT"
	if [ -e "$unit_file" ] || [ -L "$unit_file" ]; then
		if [ "$SYSTEMD_ONLY" = false ]; then
			ask_yes_no "Replace existing $unit_file?" || return 0
		fi
	fi
	# Never replace/reconfigure a service while it owns the Telegram session.
	if [ "$SYSTEMD_ONLY" = false ] && "${ctl[@]}" is-active --quiet "$SERVICE_UNIT"; then
		info "$SERVICE_UNIT is already running. Stop it before reinstalling."
		exit 1
	fi
	[ -d .git ] || app_args+=(--no-git)
	[ "$account" != root ] || app_args+=(--root)
	# Destructive and one-shot installer arguments must not run at every boot.
	for arg in "$@"; do
		case "$arg" in
			-w|--wipe|-h|--help) fail "Run $arg separately; it cannot be saved in an autostart service." 5 ;;
		esac
	done
	app_args+=("$@")
	temp_file="$(mktemp)"
	{
		printf '[Unit]\nDescription=astralix Userbot\n'
		if [ "$target" = multi-user.target ]; then
			printf 'Wants=network-online.target\nAfter=network-online.target\n'
		fi
		printf '\n[Service]\nType=simple\n'
		if [ "$target" = multi-user.target ]; then
			printf 'User=%s\n' "$account"
		fi
		printf 'WorkingDirectory=%s\n' "$(unit_quote "$work_dir" path)"
		printf 'Environment=%s\n' "$(unit_quote "HOME=$account_home")"
		printf 'Environment=%s\n' "$(unit_quote "PATH=${python_path%/python}:$account_home/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")"
		printf 'Environment=PYTHONUNBUFFERED=1\n'
		printf 'ExecStart=%s' "$(exec_quote "$python_path")"
		for arg in "${app_args[@]}"; do printf ' %s' "$(exec_quote "$arg")"; done
		printf '\nRestart=on-failure\nRestartSec=5\nTimeoutStopSec=30\nUMask=0077\n'
		printf '\n[Install]\nWantedBy=%s\n' "$target"
	} >"$temp_file"
	mkdir -p "$unit_dir"
	install -m 600 "$temp_file" "$unit_file"
	rm -f "$temp_file"
	"${ctl[@]}" daemon-reload || fail "Unit saved to $unit_file, but systemd could not reload it." 5
	ok "Service created: $unit_file"
	if [ "$SYSTEMD_ONLY" = true ] || ask_yes_no "Start $SERVICE_UNIT automatically at boot?"; then
		if [ "$target" = default.target ]; then
			if ! loginctl enable-linger "$account"; then
				if ! command -v sudo >/dev/null 2>&1 || ! sudo loginctl enable-linger "$account"; then
					info "Could not enable linger. The unit will only start when you log in."
				fi
			fi
		fi
		"${ctl[@]}" enable "$SERVICE_UNIT" || fail "Could not enable $SERVICE_UNIT." 5
	else
		"${ctl[@]}" disable "$SERVICE_UNIT" || fail "Could not disable autostart." 5
	fi
	if [ "$SYSTEMD_ONLY" = true ]; then
		"${ctl[@]}" restart "$SERVICE_UNIT" || fail "Could not start $SERVICE_UNIT." 5
		ok "$SERVICE_UNIT started; autostart enabled."
		printf '  %s status %s\n' "${ctl[*]}" "$SERVICE_UNIT"
		return
	fi
	info "This first run stays in the terminal for login. After stopping it with Ctrl+C:"
	printf '  %s start %s\n' "${ctl[*]}" "$SERVICE_UNIT"
	printf '  %s status %s\n' "${ctl[*]}" "$SERVICE_UNIT"
}

if [ "$SYSTEMD_ONLY" = true ]; then
	# This mode must never clone, recreate a venv, install packages or run login.
	if [ ! -d "$MODULE_NAME" ] || [ ! -f pyproject.toml ]; then
		if [ -d "$APP_NAME/$MODULE_NAME" ] && [ -f "$APP_NAME/pyproject.toml" ]; then
			cd "$APP_NAME"
		else
			fail "Run --systemd from the installed astralix directory." 5
		fi
	fi
	[ -x "$VENV_DIR/bin/python" ] || fail "Virtual environment missing. Install astralix before using --systemd." 5
	# A daemon cannot read the first-login prompts from a terminal.
	"${RUN_AS_USER[@]}" "$VENV_DIR/bin/python" - "$@" <<'PY' || fail "Complete the first login before enabling the service." 5
import pathlib
import sys

root = pathlib.Path.cwd()
for index, arg in enumerate(sys.argv[1:], 1):
    if arg == "--data-root" and index + 1 < len(sys.argv):
        root = pathlib.Path(sys.argv[index + 1]).expanduser()
    elif arg.startswith("--data-root="):
        root = pathlib.Path(arg.split("=", 1)[1]).expanduser()
if not any((root / "sessions").glob("*.session")) and not any(root.glob("*.session")):
    raise SystemExit("No saved Telegram sessions found.")
PY
	configure_service "$@"
	exit 0
fi

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
set_service_unit "$(pwd -P)"
check_service_stopped
check_python "$PYTHON"
ensure_uv
create_venv "$PYTHON"
install_python_packages

touch .setup_complete
rm -f "$LOG_FILE"

ok "Installation complete."
configure_service "$@"
start_app "$@"
