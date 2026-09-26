FROM ghcr.io/astral-sh/uv:0.12.17 AS uv
FROM python:3.14

COPY --from=uv /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_HTTP_TIMEOUT=100 \
    VIRTUAL_ENV=/opt/astralix-venv \
    UV_PROJECT_ENVIRONMENT=/opt/astralix-venv \
    PATH="/opt/astralix-venv/bin:$PATH" \
    DOCKER=true \
    GIT_PYTHON_REFRESH=quiet

RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    curl \
    ffmpeg \
    gcc \
    git \
    libavcodec-dev \
    libavdevice-dev \
    libavformat-dev \
    libavutil-dev \
    libcairo2 \
    libmagic1 \
    libswscale-dev \
    openssh-server \
    xfonts-75dpi \
    xfonts-base \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install --no-install-recommends -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /data
RUN mkdir /data/private

WORKDIR /data/astralix
COPY . /data/astralix

RUN uv sync --locked --python /usr/local/bin/python

CMD ["python", "-m", "astralix", "--root", "--no-git"]
