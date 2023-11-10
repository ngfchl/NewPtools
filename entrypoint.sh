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

function token_verification {
    if [ -z "$TOKEN" ]; then
        WARN "未检测到授权码TOKEN，正在进入未授权模式"
        AUTH_RESPONSE='{"code":-1,"msg":"未授权模式","data":null}'
    else
      if [ ! -f db/encrypted_key.bin ];then
          WARN "未检测到授权文件，开始从服务器申请授权信息..."
          AUTH_RESPONSE=$(curl -s -k -G -d "token=$TOKEN&email=$DJANGO_SUPERUSER_EMAIL" https://repeat.ptools.fun/api/user/verify)
      else
          INFO "检测到授权文件，正在解析..."
          AUTH_RESPONSE=$(./encrypt_tool/$(uname -m)/main.bin)
      fi
    fi
  # Get authorization response
  INFO "$AUTH_RESPONSE"
  AUTH_CODE=$(echo "$AUTH_RESPONSE" | jq -r '.code')
  INFO "$AUTH_CODE"
  if [ ! -z "$AUTH_CODE" ] && [ "$AUTH_CODE" -eq 0 ]; then
      # 在 if 语句块中，你可以添加处理 AUTH_CODE 不为空且等于 0 的情况的代码
      INFO "获取授权信息成功，开始启动所有服务..."
  else
      WARN "授权失败或访问授权服务器失败，将进入未授权模式..."
      mv /ptools/supervisor/product/supervisor_celery_beat.ini /ptools/supervisor/product/supervisor_celery_beat.bak
  fi

}

function cloudflarespeedtest_host {

  if [ ! -f db/hosts ] || [ ! -f db/nowip_hosts.txt ]; then
    INFO "HOSTS文件不存在，写入默认"
    cp -n hosts/hosts db/hosts
    cp -n hosts/nowip_hosts.txt db/nowip_hosts.txt
  else
    INFO '存在自定义HOSTS文件，apply'
  fi
  if [ "$CloudFlareSpeedTest" = "true" ]; then
    counter_file="/ptools/db/counter.txt"
    current_date=$(date +%Y-%m-%d)
    if [ ! -f "$counter_file" ]; then
      echo "1" >"$counter_file"
    fi
    counter=$(<"$counter_file")
    if [ "$current_date" != "$counter" ]; then
      INFO "启动测速..."
      bash cfst_hosts.sh
      echo "$current_date" >"$counter_file"
    else
      INFO "今日已测速，跳过测速."
    fi
  else
    INFO "跳过测速."
  fi

}

function first_start {

  INFO "程序初始化中..."
  touch db/ptools.toml

  python3 manage.py migrate



  INFO "创建超级用户"
  python3 manage.py createsuperuser --noinput
  INFO "初始化完成"

}

function init_supervisor() {

  INFO "Nginx 初始化中..."
  envsubst "\$DJANGO_WEB_PORT,\$WEBUI_PORT,\$FLOWER_UI_PORT" </ptools/nginx/nginx.conf >/etc/nginx/conf.d/default.conf

  INFO "Supervisor 初始化中..."
  sed -i "s/:9001/:$SUPERVISOR_UI_PORT/g" /ptools/supervisor/prod.conf
  for file in /ptools/supervisor/product/*.ini; do
    sed -i "s/-l INFO/-l $LOGGER_LEVEL/g" "$file"
  done

  if [ $DISTRIBUTE_CLIENT = true ]; then
      INFO "检测到本实例为分布式客户端，不再启动定时任务检测"
      mv /ptools/supervisor/product/supervisor_celery_beat.ini /ptools/supervisor/product/supervisor_celery_beat.ini.bak
      mv /ptools/supervisor/product/redis.ini /ptools/supervisor/product/redis.ini.bak
  else
    INFO "初始化 Redis 。。。"
    if [ $CACHE_REDIS_CONNECTION ]; then
      INFO "检测到外部 Redis 设置，屏蔽内部 Redis"
      mv /ptools/supervisor/product/redis.ini /ptools/supervisor/product/redis.ini.bak
    else
      sed -i "s/--port 6379/--port $REDIS_SERVER_PORT/g" /ptools/supervisor/product/redis.ini
    fi
  fi

  INFO "初始化 Celery Flower 。。。"
  sed -i "s/--port=5566/--port=$FLOWER_UI_PORT/g" /ptools/supervisor/product/supervisor_celery_flower.ini

}

function upgrade() {

  if [ ! -e "$GIT_PROXY" ]; then
    git config --global http.proxy "$GIT_PROXY"
    git config --global https.proxy "$GIT_PROXY"
  fi
  git config --global core.sshCommand 'ssh -o StrictHostKeyChecking=no'
  git config pull.ff only
  git config --global user.email $DJANGO_SUPERUSER_EMAIL
  git config --global user.name $DJANGO_SUPERUSER_NAME
  INFO "后端更新中..."
  git reset --hard
  git pull git@gitee.com:ngfchl/auxiliary.git "$BRANCH"
  if [ $? -eq 0 ]; then
    INFO "后端更新成功"
  else
    ERROR "后端更新失败，请重新拉取镜像"
  fi
  INFO "重设脚本权限中..."
  chmod -R 0755 /ptools
  if [ $? -eq 0 ]; then
    INFO "重设脚本权限成功"
  else
    ERROR "重设脚本权限失败，请重新拉取镜像"
    exit 1
  fi
  INFO "前端更新中..."
  cd /ptools/templates
  git reset --hard
  git remote set-url origin https://gitee.com/ngfchl/auxi-naive.git
  git pull https://gitee.com/ngfchl/auxi-naive.git dist
  if [ $? -eq 0 ]; then
    INFO "前端更新成功"
  else
    ERROR "前端更新失败，请重新拉取镜像"
  fi
  cd /ptools

}

if [ "${AUTO_UPDATE}" == true ]; then
  upgrade
fi

token_verification

cloudflarespeedtest_host

init_supervisor

CONTAINER_ALREADY_STARTED="CONTAINER_ALREADY_STARTED_PLACEHOLDER"
if [ ! -e $CONTAINER_ALREADY_STARTED ]; then
  INFO "首次启动，开始初始化"
  touch $CONTAINER_ALREADY_STARTED
  first_start
else
  INFO "非首次启动，跳过初始化"
fi

INFO "同步数据库结构"
python3 manage.py migrate
INFO "启动supervisor服务"
supervisord -c supervisor/prod.conf
INFO "启动 Django 服务"
exec dumb-init uvicorn auxiliary.asgi:application --reload --host 0.0.0.0 --port "$DJANGO_WEB_PORT"
