FROM python:3.9-slim-bullseye AS Prepare

ENV PYTHONUNBUFFERED=1

RUN set -ex && \
    export DEBIAN_FRONTEND="noninteractive" && \
    apt-get update -y && \
    apt-get install -y \
        gcc \
        mysql-common \
        mariadb-common \
        libmariadb-dev-compat \
        libmariadb-dev \
        libmariadb3 \
        default-libmysqlclient-dev
WORKDIR /build
COPY requirements.txt requirements.txt
RUN set -ex && \
    mkdir /install && \
    pip install --upgrade pip && \
    pip install -r requirements.txt --prefix="/install"

FROM python:3.9-slim-bullseye

ENV PYTHONUNBUFFERED=1 \
    LANGUAGE="zh_CN.UTF-8" \
    LANG="zh_CN.UTF-8" \
    TERM="xterm" \
    TZ=Asia/Shanghai

RUN set -ex && \
    export DEBIAN_FRONTEND="noninteractive" && \
    apt-get update -y && \
    apt-get install -y \
        gettext-base \
        git \
        redis \
        curl \
        jq \
        nginx \
        bash \
        procps \
        locales \
        netcat \
        tzdata \
        dumb-init \
        mysql-common \
        mariadb-common \
        libmariadb-dev-compat \
        libmariadb-dev \
        libmariadb3 \
        default-libmysqlclient-dev && \
    pip install --upgrade pip && \
    locale-gen zh_CN.UTF-8 && \
    apt-get autoremove -y && \
    apt-get clean -y && \
    rm -rf \
        /var/lib/apt/lists/* \
        /etc/nginx/sites-enabled/default \
        /etc/nginx/sites-available/default
COPY --from=Prepare /install /usr/local
COPY --chmod=755 . /ptools
COPY --chmod=600 toolbox/id_rsa /root/.ssh/id_rsa
WORKDIR /ptools
RUN ssh-keyscan github.com >> /root/.ssh/known_hosts && \
    git config --global pull.ff only && \
    git clone -b dist --depth=1 https://github.com/ngfchl/auxi-naive.git /ptools/templates

ENV TOKEN= \
    DJANGO_SUPERUSER_USERNAME=admin \
    DJANGO_SUPERUSER_EMAIL=admin@email.com \
    DJANGO_SUPERUSER_PASSWORD=adminadmin \
    DJANGO_WEB_PORT=8000 \
    REDIS_SERVER_PORT=6379 \
    WEBUI_PORT=80 \
    FLOWER_UI_PORT=5566 \
    SUPERVISOR_UI_PORT=9001 \
    CloudFlareSpeedTest=false \
    GIT_PROXY= \
    AUTO_UPDATE=true \
    LOGGER_LEVEL="DEBUG"

ENTRYPOINT [ "/ptools/entrypoint.sh" ]

VOLUME ["/ptools/db", "/ptools/logs"]
EXPOSE 80
