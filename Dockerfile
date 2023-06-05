FROM nginx:latest

# 设置 python 环境变量
ENV PYTHONUNBUFFERED 1
ENV TOKEN=
ENV DJANGO_SUPERUSER_USERNAME=admin
ENV DJANGO_SUPERUSER_EMAIL=admin@eamil.com
ENV DJANGO_SUPERUSER_PASSWORD=adminadmin
ENV DJANGO_WEB_PORT=8000
ENV CELERY_REDIS_CONNECTION="redis://127.0.0.1:6379/10"
ENV CACHE_REDIS_CONNECTION="redis://127.0.0.1:6379/11"
ENV LOGGER_LEVEL="INFO"
ENV MYSQL_CONNECTION=

# 写入pip国内源
COPY pip.conf /root/.pip/pip.conf

RUN mkdir -p /ptools
WORKDIR /ptools
ADD . /ptools
# 更新pip版本，更换USTC源，并安装git
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list
RUN apt update && apt install gcc gettext-base nginx redis git curl python3 python3-dev python3-pip jq mysql-common mariadb-common libmariadb-dev-compat libmariadb-dev libmariadb3 default-libmysqlclient-dev -y \
   && python3 -m pip install --upgrade pip && pip install -r requirements.txt --no-cache-dir && apt autoremove gcc -y && apt-get autoclean && rm -rf /var/lib/apt/lists/* && rm -rf /root/.cache/pip

#RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories
#RUN apk add --no-cache \
#    python3 \
#    python3-dev \
#    curl \
#    git \
#    mariadb-dev \
#    mariadb-connector-c \
#    py3-pip \
#    bash \
#    jq \
#    gettext \
#    mysql-dev \
#    mysql-client \
#    mariadb-connector-c-dev  \
#    gcc musl-dev \
#    && python3 -m pip install --upgrade pip \
#    && pip install --ignore-installed -r requirements.txt --no-cache-dir \
#    && apk del gcc musl-dev


# 给start.sh可执行权限，并安装依赖
RUN chmod +x /ptools/start.sh && rm -rf /ptools/db/* && rm -rf /etc/nginx/conf.d/*

COPY ./nginx/nginx.conf /etc/nginx/conf.d/default.conf.template

# 暴露数据库文件夹
VOLUME ["/ptools/db", "/ptools/logs"]
# 暴露访问端口
EXPOSE  $DJANGO_WEB_PORT
EXPOSE  5566
EXPOSE  9001
EXPOSE  80

# 执行启动文件
ENTRYPOINT ["/bin/bash", "/ptools/start.sh"]
