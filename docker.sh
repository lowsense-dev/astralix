#!/bin/bash
# ©️ radiocycle, 2026
# This file is a part of astralix Userbot
# 🌐 https://github.com/radiocycle/astralix
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

touch astralix-install.log

if ! sudo docker compose version >/dev/null 2>&1; then
    printf "\033[0;34mInstalling docker...\e[0m"
    if [ -f /etc/debian_version ]; then
        sudo apt-get install \
            apt-transport-https \
            ca-certificates \
            curl \
            gnupg-agent \
            software-properties-common -y 1>astralix-install.log 2>&1
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg |
            sudo apt-key add - 1>astralix-install.log 2>&1
        sudo add-apt-repository \
            "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
            $(lsb_release -cs) \
            stable" 1>astralix-install.log 2>&1
        sudo apt-get update -y 1>astralix-install.log 2>&1
        sudo apt-get install docker-ce docker-ce-cli containerd.io -y 1>astralix-install.log 2>&1
    elif [ -f /etc/arch-release ]; then
        sudo pacman -Syu docker --noconfirm 1>astralix-install.log 2>&1
    elif [ -f /etc/redhat-release ]; then
        sudo yum install -y yum-utils 1>astralix-install.log 2>&1
        sudo yum-config-manager \
            --add-repo \
            https://download.docker.com/linux/centos/docker-ce.repo
        sudo yum install docker-ce docker-ce-cli containerd.io -y 1>astralix-install.log 2>&1
    fi
    printf "\033[0;32m - success\e[0m\n"
    # astralix uses docker-compose so we need to install that too
    printf "\033[0;34mInstalling docker-compose...\e[0m"
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get install -y docker-compose-plugin 1>astralix-install.log 2>&1
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --needed --noconfirm docker-compose 1>astralix-install.log 2>&1
    else
        sudo yum install -y docker-compose-plugin 1>astralix-install.log 2>&1
    fi
    printf "\033[0;32m - success\e[0m\n"
else
    printf "\033[0;32mDocker is already installed\e[0m\n"
fi

printf "\033[0;34mBuilding docker image...\e[0m"
sudo docker compose build 1>astralix-install.log 2>&1
printf "\033[0;32m - success\e[0m\n"

printf "\033[0;32mStarting astralix setup in console mode...\e[0m\n"
sudo docker compose run --rm worker
