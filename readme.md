## 说明

> 整个项目近乎完全重构，与旧版本相比，采用celery作为定时与后台任务管理工具，支持集群任务

> 支持数据库MYSQL、MARIADB、SQLITE3

> 前端页面采用NAIVEUI全新打造

> 支持签到、数据统计、下载器聚合管理、刷流

> 辅种正在收集数据

> 等等其他功能，想到再写上来

### 欢迎加入 PTools 的大家庭，ptools 致力于让你更轻松更自动的玩 PT，目前实现了以下功能：

1. 支持从 PTPP 备份文件导入站点信息
2. 支持油猴脚本添加站点和同步站点 Cookie 信息
3. 支持国内大部分 PT 站点的签到
4. 支持站点个人数据信息获取、展示
5. 支持部分站点拉取免费种子
6. 支持RSS刷流、RSS刷流（已支持部分站点，更多站点逐步适配中）
6. 计划任务：自动化功能，支持签到、更新数据、拉取种子等功能的自动化
7. 通知功能：自动任务执行结束后发送任务执行报告，支持企业微信，wxpusher，IYUU，Pushdeer，Bark
8. 日志查看：十分钟左右生成一次执行日志，十分钟期间无操作的，无日志
9. OCR 识别接口：支持百度 OCR 文字识别，用于部分站点签到时的验证码识别
10. 种子管理：查看拉取到本地的免费种子信息，支持推送到下载器，目前仅支持自定义路径
11. 下载器聚合管理，目前支持QB与TR
13. 实现简易终端窗口
14. hosts 文件编辑
15. 支持自动CloudFlareSpeedTest测速并自动更新HOSTS
15. 更多功能等你发现

## 界面展示

### 主页

![image-20231210204416027](https://img.ptools.fun/blog/image-20231210204416027.png)

### 数据卡片

[![image-1685520601989.png](http://img.ptools.fun/blog/image-1685520601989.png)](http://img.ptools.fun/blog/image-1685520601989.png)

### 站点列表

[![image-1685520630149.png](http://img.ptools.fun/blog/image-1685520630149.png)](http://img.ptools.fun/blog/image-1685520630149.png)

### 种子列表

[![image-1685520663215.png](http://img.ptools.fun/blog/image-1685520663215.png)](http://img.ptools.fun/blog/image-1685520663215.png)

### 下载器列表

![](http://img.ptools.fun/blog/image-1685520691254.png)

### 下载器聚合管理

[![image-1685520719715.png](http://img.ptools.fun/blog/image-1685520719715.png)](http://img.ptools.fun/blog/image-1685520719715.png)

### 计划任务

[![image-1685521139558.png](http://img.ptools.fun/blog/image-1685521139558.png)](http://img.ptools.fun/blog/image-1685521139558.png)

[![image-1685520743237.png](http://img.ptools.fun/blog/image-1685520743237.png)](http://img.ptools.fun/blog/image-1685520743237.png)

### PTPP导入

[![image-1685520782690.png](http://img.ptools.fun/blog/image-1685520782690.png)](http://img.ptools.fun/blog/image-1685520782690.png)

## 三板斧

> 部分站点比较特殊，例如：瓷器的 cookie 经常过期，站点访问性较差，自动任务总是失败，所以总结了三板斧操作

1. 出问题之后更新 Cookie

- 瓷器的 Cookie 有大佬测试可以试用手机浏览器 alook 获取，成功率很高
- 由于瓷器 Cookie 的特殊性，如果依旧失败，可以尝试以分号为单位，删除 `phpsession` 字段

2. 提取填写浏览器 User-Agent

## 提问

1. 请先详细阅读文档，文档讲解的很详细，当然可能有个别点不会很清晰，但很少吧？

2. 使用中遇到问题请先检查一下几个地方

1. 请先检查工具是否为最新版本，使用中遇到问题的，大部分很快就更新解决了，保持更新会解决很多问题，更新完别忘了同步数据库，想简单点，就遇到问题先重启一下。

2. 群里多爬爬楼，也能解决很多问题，或者直接搜一搜

3. 运行日志，搜索 `traceback`
   关键字即可看到运行中出现的错误信息，求助时，可将这一块完整截图，支持下载日志文件，不找到怎么查找的，可以下载日志文件求助（虽然在代码中尽量避免在日志中出现敏感信息，但是每个人对敏感信息的定义有所不同，请注意咯）。

# 安装

## docker

拉取镜像：`docker pull newptools/ptools`

- <font color="red">无论是命令还是界面化安装，如果你不懂这个参数是什么意思，请保持右侧的参数不变，左边可以尽情发挥</font>
- <font color="red">HOST模式的问题已经解决，部分站点需要V6，有条件直接使用HOST模式部署</font>
- <font color="red">支持docker-compose的设备尽量使用docker-compose部署，更灵活</font>

### 参数详解

#### 端口

- WEBUI_PORT： <font color="orange">前端页面地址，所有服务均走此端口，默认80，HOST模式冲突时根据需要修改</font>
- DJANGO_WEB_PORT:  <font color="orange">API端口，默认：8000，一般无需映，HOST模式冲突时根据需要修改</font>
- SUPERVISOR_UI_PORT: <font color="orange">服务进程管理端口，默认9001，一般无需映，HOST模式端口冲突时根据需要修改</font>
- FLOWER_UI_PORT: <font color="orange">后台任务管理端口，默认5566，一般无需映，HOST模式冲突时根据需要修改</font>
- REDIS_SERVER_PORT: <font color="orange">redis缓存服务端口，默认6379，一般无需映，HOST模式冲突时根据需要修改</font>

#### 其他参数

- CloudFlareSpeedTest：<font color="orange">开机测速开关，为true则启动测速，为false则关闭测速</font>
- MYSQL_CONNECTION：非必填，必填默认使用sqlite3文件数据库，存储位置为：ptools/db，MYSQL，MARIADB数据库连接地址,root:
  password@host:port/database，分别是：数据库的用户名，密码，IP，端口，所连接的数据库名称，第一次连接数据库要保证数据库为空，数据库编码格式为UTF8mb4
- CELERY_REDIS_CONNECTION: 非必填，自定义Redis服务器时需要。填写redis连接地址，192.168.123.5:
  6379/8，分别是：IP，端口，第几个数据库，redis的数据库有0-15，一共16个，随便选一个即可。另，根据需要可以自行设置连接密码，自行百度
- CACHE_REDIS_CONNECTION：非必填，自定义Redis服务器时需要。尽量与CELERY_REDIS_CONNECTION保持不同的数据库
- DJANGO_SUPERUSER_USERNAME：登录账号
- DJANGO_SUPERUSER_PASSWORD：登录密码
- LOGGER_LEVEL：设置日志级别，内测请设置为DEBUG，可以看到详细日志各NAS安装方法与旧版本一直，根据需要设置环境变量、文件夹映射以及端口映射即可
- AUTO_UPDATE：自动更新代码，默认值`false`关闭自动更新；当值为`true`时，开机或重启是会自动拉取最新代码，成功与否看Github连接性。
-

GIT_PROXY：代码托管在Github，连接性问题，可以设置代理来解决，这里直接填写你的http代理地址就可以了，比如：`http://192.168.1.2:1088`

- `DISTRIBUTE_CLIENT`: 默认值为 false 表示不启用客户端模式，设置为 true 时，此 docker 容器不再发布定时任务，不启动 Redis

## 1. 命令行

```bash
docker run -d \
-p 8001:8000 \
-p 5566:5566 \
-p 9001:9001 \
-p 4173:80 \
-v /root/ptools/db:/ptools/db \
-v /root/ptools/logs:/ptools/logs \
-e MYSQL_CONNECTION='mysql://root:password@host:port/database?charset=utf8mb4' \
-e CELERY_REDIS_CONNECTION='redis://192.168.123.5:6379/8' \
-e CACHE_REDIS_CONNECTION='redis://192.168.123.5:6379/9' \
-e DJANGO_SUPERUSER_USERNAME='admin' \
-e DJANGO_SUPERUSER_EMAIL='admin@admin.com' \
-e DJANGO_SUPERUSER_PASSWORD='adminadmin' \
-e DJANGO_WEB_PORT='8000' \
-e LOGGER_LEVEL='DEBUG' \
-e DISTRIBUTE_CLIENT=false \
newptools/ptools
```

### 最简配置

```bash
# 使用默认用户名admin密码adminadmin
# 使用默认SQLite3数据库，存在  
docker run -d \
  -p 4173:80 \
  -e DJANGO_SUPERUSER_EMAIL='*******@126.com' \
  -v '/mnt/user/appdata/newptools/db':'/ptools/db':'rw' \
  -v '/mnt/user/appdata/newptools/logs':'/ptools/logs':'rw' \
  newptools/ptools
```

### 威联通Compose

先编辑compose文件，按照实际需求选择自己的路径和端口即可

```yml
version: "3"
services:
  backend:
    image: newptools/ptools:latest
    network_mode: host
    volumes:
      - /share/docker/db:/ptools/db
      - /share/docker/logs:/ptools/logs
    environment:
      - DJANGO_SUPERUSER_USERNAME=admin
      - DJANGO_SUPERUSER_EMAIL=邮箱
      - DJANGO_SUPERUSER_PASSWORD=adminadmin
      - WEBUI_PORT=5173
    restart: always
    hostname: backend
    container_name: backend
```

## docker-compose

### bridge模式

```yaml
version: "3"
services:
  backend:
    image: newptools/ptools:latest
    ports:
      - 8000:8000
      - 5566:5566
      - 8080:80
    volumes:
      - ./backend_db:/ptools/db
      - ./backend_log:/ptools/logs
    environment:
      - DJANGO_SUPERUSER_USERNAME=admin
      - DJANGO_SUPERUSER_EMAIL=邮箱
      - DJANGO_SUPERUSER_PASSWORD=adminadmin
      - DJANGO_WEB_PORT=8000
      - REDIS_CONNECTION="redis://redis_ip:6379/13"
    restart: always
    hostname: backend
    container_name: backend
  redis:
    image: redis:5
    privileged: true
    ports:
      - 6379:6379
    restart: always
    hostname: redis
    container_name: redis

```

### host模式

```yaml
version: "3"
services:
  newptools:
    network_mode: host
    image: newptools/ptools:latest
    volumes:
      - ./db:/ptools/db
      - ./logs:/ptools/logs
    environment:
      - DJANGO_SUPERUSER_USERNAME=admin
      - DJANGO_SUPERUSER_EMAIL=
      - DJANGO_SUPERUSER_PASSWORD=adminadmin
      - DJANGO_WEB_PORT=22223 # 默认8000，根据需要更改
      - WEBUI_PORT=22222 # 默认80，根据需要更改
      - SUPERVISOR_UI_PORT=22225 # 默认9001，根据需要更改
      - FLOWER_UI_PORT=22226 # 默认5566，根据需要更改
      - REDIS_SERVER_PORT=22227 # 默认6379，根据需要更改
    restart: always
    hostname: newptools
    container_name: newptools
```

## 添加站点

### 1. PTPP导入

这个与旧版保持一致，不过无需再页面等待了，变为后台任务，执行完毕会发送通知

### 2. 油猴脚本

<font color="red">油猴脚本不仅仅支持同步Cookie，也支持添加站点</font>

![image-20230629145646264](https://img.ptools.fun/blog/image-20230629145646264.png)

![image-20230629145705594](https://img.ptools.fun/blog/image-20230629145705594.png)

![image-20230629145735151](https://img.ptools.fun/blog/image-20230629145735151.png)

使用方法与旧版本保持一致，目前支持添加与更新站点cookie等信息，更多功能请等待

![image-20230629130723114](https://img.ptools.fun/blog/image-20230629130723114.png)

1. URL直接修改为前端访问地址

2. 系统配置中添加如下内容：

   ```toml
   [token]
   token="ptools"
   ```
   ![](https://img.ptools.fun/blog/202306291309849.png)

3. 脚本中的TOKEN与系统配置中的TOKEN保持一致即可。

4. 点击`同步Cookie`按钮，会有提示，无反应，要么不支持站点，要么出错了

   ![image-20230630100344886](https://img.ptools.fun/blog/image-20230630100344886.png)

   ![image-20230630100403178](https://img.ptools.fun/blog/image-20230630100403178.png)

### 错误处理

1. 检查是否为红猴，不是的请换红猴

2. 检查黑猴中是否有PTOOLS的脚本，有的请删除或者关闭

3. 仍不能使用的，按F12打开开发者模式，找到应用程序标签，尝试清除会话存储后重试

   ![image-20230630100951854](https://img.ptools.fun/blog/image-20230630100951854.png)

   ![](https://img.ptools.fun/blog/image-20230630100951854.png)

4. 仍不能用的，看控制台(或Console)报错信息

   ![image-20230630100916831](https://img.ptools.fun/blog/image-20230630100916831.png)

### 3. 手动添加

以上两个方法可以快速添加站点，但是难免会有失败的，这时候就需要手动添加了

- 选择相关功能的开启
- 填写删种规则
- 填写RSS地址与刷流地址
- 选择指定的刷流下载器
- 支持单站设置代理

[![image-1685521315072.png](http://img.ptools.fun/blog/image-1685521315072.png)](http://img.ptools.fun/blog/image-1685521315072.png)
