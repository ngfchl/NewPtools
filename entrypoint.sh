#!/bin/bash

Green="\033[32m"
Red="\033[31m"
Yellow='\033[33m'
Font="\033[0m"
INFO="[${Green}INFO${Font}]"
ERROR="[${Red}ERROR${Font}]"
WARN="[${Yellow}WARN${Font}]"
function INFO {
    echo -e "${INFO} ${1}"
}
function ERROR {
    echo -e "${ERROR} ${1}"
}
function WARN {
    echo -e "${WARN} ${1}"
}

CONTAINER_ALREADY_STARTED="CONTAINER_ALREADY_STARTED_PLACEHOLDER"

if [ -z "$TOKEN" ]; then
  ERROR "Authorization: No TOKEN received. Exiting..."
  exit 1
fi
# Get authorization response
AUTH_RESPONSE=$(curl -s -G -d "token=$TOKEN&email=$DJANGO_SUPERUSER_EMAIL" http://api.ptools.fun/neice/check)
INFO "$AUTH_RESPONSE"
# Extract 'code' from the response
AUTH_CODE=$(echo "$AUTH_RESPONSE" | jq -r '.code')
INFO "$AUTH_CODE"
if [ -z "$AUTH_CODE" ]; then
  ERROR "Authorization: No AUTH_CODE received.  Exiting..."
  exit 1
elif [ "$AUTH_CODE" -ne 0 ]; then
  ERROR "Authorization. Exiting..."
  exit 1
fi

if [ ! -f db/hosts ] || [ ! -f db/nowip_hosts.txt ]; then
    INFO "HOSTS文件不存在，写入默认"
    cp -n hosts/hosts db/hosts
    cp -n hosts/nowip_hosts.txt db/nowip_hosts.txt
else
    INFO '存在自定义HOSTS文件，apply'
fi
if [ "$CloudFlareSpeedTest" = "true" ]; then
    INFO "启动测速..."
    bash cfst_hosts.sh
else
    INFO "跳过测速."
fi

envsubst "\$DJANGO_WEB_PORT,\$WEBUI_PORT,\$FLOWER_UI_PORT" </ptools/nginx/nginx.conf >/etc/nginx/conf.d/default.conf

for file in /ptools/supervisor/product/*.ini; do
    sed -i "s/-l INFO/-l $LOGGER_LEVEL/g" "$file"
done
sed -i "s/--port 6379/--port $REDIS_SERVER_PORT/g" /ptools/supervisor/product/redis.ini

if [ ! -e $CONTAINER_ALREADY_STARTED ]; then
    INFO "First container startup"
    INFO "系统初始化中"
    python3 manage.py migrate
    touch $CONTAINER_ALREADY_STARTED
    INFO "创建超级用户"
    DJANGO_SUPERUSER_USERNAME=$DJANGO_SUPERUSER_USERNAME
    DJANGO_SUPERUSER_EMAIL=$DJANGO_SUPERUSER_EMAIL
    DJANGO_SUPERUSER_PASSWORD=$DJANGO_SUPERUSER_PASSWORD
    python3 manage.py createsuperuser --noinput
    INFO "初始化完成"
else
    INFO "Not first container startup"
fi

INFO "启动服务"
python3 manage.py migrate
supervisord -c supervisor/prod.conf
uvicorn auxiliary.asgi:application --reload --host 0.0.0.0 --port "$DJANGO_WEB_PORT"
