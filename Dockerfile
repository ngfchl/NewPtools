FROM nginx:latest

# 设置 python 环境变量
ENV PYTHONUNBUFFERED 1
ENV TOKEN=
ENV DJANGO_SUPERUSER_USERNAME=admin
ENV DJANGO_SUPERUSER_EMAIL=admin@eamil.com
ENV DJANGO_SUPERUSER_PASSWORD=adminadmin
ENV DJANGO_WEB_PORT=8000
ENV REDIS_SERVER_PORT=9736
ENV WEBUI_PORT=80
ENV FLOWER_UI_PORT=5566
ENV SUPERVISOR_UI_PORT=9001
ENV CELERY_REDIS_CONNECTION="redis://127.0.0.1:6379/10"
ENV CACHE_REDIS_CONNECTION="redis://127.0.0.1:6379/11"
ENV LOGGER_LEVEL="INFO"
ENV MYSQL_CONNECTION=

RUN mkdir -p /ptools/db
WORKDIR /ptools
ADD . /ptools
# 给start.sh可执行权限，并安装依赖
RUN chmod +x /ptools/start.sh /ptools/cfst_hosts.sh \
    && chmod +x ./CloudflareST_linux_amd64/CloudflareST  \
    && chmod +x ./CloudflareST_linux_arm64/CloudflareST  \
    && rm -rf /ptools/db/* && rm -rf /etc/nginx/conf.d/*

COPY ./nginx/nginx.conf /etc/nginx/conf.d/default.conf.template
# 更新pip版本，更换USTC源，并安装git
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list \
    && apt update \
    && apt install gcc gettext-base nginx redis git curl \
    python3 python3-dev python3-pip jq mysql-common \
    mariadb-common libmariadb-dev-compat libmariadb-dev \
    libmariadb3 default-libmysqlclient-dev -y \
    && pip config set global.index-url https://pypi.douban.com/simple/ \
    && pip install --upgrade pip &&  pip install -r requirements.txt --no-cache-dir \
    && apt autoremove gcc python3-dev -y && apt-get autoclean && rm -rf /var/lib/apt/lists/* \
    && rm -rf /root/.cache/pip

#RUN apt update \
#    && apt install gcc gettext-base nginx redis git curl \
#    python3 python3-dev python3-pip jq mysql-common \
#    mariadb-common libmariadb-dev-compat libmariadb-dev \
#    libmariadb3 default-libmysqlclient-dev -y \
#    && pip install --upgrade pip &&  pip install -r requirements.txt --no-cache-dir \
#    && apt autoremove gcc python3-dev -y && apt-get autoclean && rm -rf /var/lib/apt/lists/* \
#    && rm -rf /root/.cache/pip && sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list

# 暴露数据库文件夹
VOLUME ["/ptools/db", "/ptools/logs"]
# 暴露访问端口
EXPOSE  $DJANGO_WEB_PORT
EXPOSE  $FLOWER_UI_PORT
EXPOSE  $SUPERVISOR_UI_PORT
EXPOSE  $WEBUI_PORT

# 执行启动文件
ENTRYPOINT ["/bin/bash", "/ptools/start.sh"]
