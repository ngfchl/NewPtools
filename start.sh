#!/bin/sh

if [ -z "$TOKEN" ]; then
  echo "Authorization failed: No TOKEN received. Exiting..."
  exit 1
fi

CONTAINER_ALREADY_STARTED="CONTAINER_ALREADY_STARTED_PLACEHOLDER"
# Get authorization response
AUTH_RESPONSE=$(curl -s -G -d "token=$TOKEN&email=$DJANGO_SUPERUSER_EMAIL" http://api.ptools.fun/neice/check)
echo "$AUTH_RESPONSE"
# Extract 'code' from the response
AUTH_CODE=$(echo "$AUTH_RESPONSE" | jq -r '.code')
echo "$AUTH_CODE"
if [ -z "$AUTH_CODE" ]; then
  echo "Authorization failed: No AUTH_CODE received.  Exiting..."
  exit 1
elif [ "$AUTH_CODE" -ne 0 ]; then
  echo "Authorization failed. Exiting..."
  exit 1
fi

if [ ! -f db/hosts ]; then
  echo "未自定义HOSTS，默认写入"
  echo 172.64.153.252 u2.dmhy.org >>/etc/hosts
  echo 104.25.26.31 u2.dmhy.org >>/etc/hosts
  echo 104.25.61.106 u2.dmhy.org >>/etc/hosts
  echo 104.25.62.106 u2.dmhy.org >>/etc/hosts
  echo 172.67.98.15 u2.dmhy.org >>/etc/hosts
else
  echo '存在自定义HOSTS文件，apply'
  ./cfst_hosts.sh
  cp -f /ptools/db/hosts /etc/hosts
fi

cd /ptools
# 替换nginx配置文件
envsubst "\$DJANGO_WEB_PORT" </etc/nginx/conf.d/default.conf.template >/etc/nginx/conf.d/default.conf

# 设置日志级别
LOGGER_LEVEL=${LOGGER_LEVEL:-debug}

for file in /ptools/supervisor/product/*.ini; do
  sed -i "s/-l INFO/-l $LOGGER_LEVEL/g" "$file"
done

if [ ! -e $CONTAINER_ALREADY_STARTED ]; then
  echo "-- First container startup --"
  # 此处插入你要执行的命令或者脚本文件
  echo "系统初始化中"
  python3 manage.py migrate
  touch $CONTAINER_ALREADY_STARTED
  echo "创建超级用户"
  DJANGO_SUPERUSER_USERNAME=$DJANGO_SUPERUSER_USERNAME
  DJANGO_SUPERUSER_EMAIL=$DJANGO_SUPERUSER_EMAIL
  DJANGO_SUPERUSER_PASSWORD=$DJANGO_SUPERUSER_PASSWORD
  python3 manage.py createsuperuser --noinput
  echo "初始化完成"
else
  echo "-- Not first container startup --"
fi

echo "启动服务"
python3 manage.py migrate
supervisord -c supervisor/prod.conf
uvicorn auxiliary.asgi:application --reload --host 0.0.0.0 --port "$DJANGO_WEB_PORT"
# 后台内容完全转移到前端之前，先使用runserver
#python3 manage.py runserver 0.0.0.0:"$DJANGO_WEB_PORT"
