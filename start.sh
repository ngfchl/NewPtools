#!/bin/bash

if [ -z "$TOKEN" ]; then
  echo "Authorization failed: No TOKEN received. Exiting..."
  exit 1
fi

CONTAINER_ALREADY_STARTED="CONTAINER_ALREADY_STARTED_PLACEHOLDER"
# Get authorization response
AUTH_RESPONSE=$(curl -s -G -d "token=$TOKEN&email=$DJANGO_SUPERUSER_EMAIL" http://api.ptools.fun/neice/check)

# Extract 'code' from the response
AUTH_CODE=$(echo $AUTH_RESPONSE | jq -r '.code')
echo $AUTH_CODE
if [ -z "$AUTH_CODE" ]; then
  echo "Authorization failed: No auth code received. Exiting..."
  exit 1
elif [ $AUTH_CODE -ne 0 ]; then
  echo "Authorization failed. Exiting..."
  exit 1
fi
# 设置日志级别
LOGGER_LEVEL=${LOGGER_LEVEL:-debug}

for file in /ptools/supervisor/product/*.conf; do
    sed -i "s/-l INFO/-l $LOGGER_LEVEL/g" $file
done

if [ ! -e $CONTAINER_ALREADY_STARTED ]; then
  echo "-- First container startup --"
  # 此处插入你要执行的命令或者脚本文件
  echo "系统初始化中"
  python manage.py migrate
  touch $CONTAINER_ALREADY_STARTED
  echo "创建超级用户"
  DJANGO_SUPERUSER_USERNAME=$DJANGO_SUPERUSER_USERNAME
  DJANGO_SUPERUSER_EMAIL=$DJANGO_SUPERUSER_EMAIL
  DJANGO_SUPERUSER_PASSWORD=$DJANGO_SUPERUSER_PASSWORD
  python manage.py createsuperuser --noinput
  echo "初始化完成"
else
  echo "-- Not first container startup --"
fi

echo "启动服务"
python manage.py migrate
supervisord -c supervisor/prod.conf
#uvicorn auxiliary.asgi:application --reload --host 0.0.0.0 --port $DJANGO_WEB_PORT
# 后台内容完全转移到前端之前，先使用runserver
python manage.py runserver 0.0.0.0:$DJANGO_WEB_PORT
