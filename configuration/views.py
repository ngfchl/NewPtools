import logging
import os
import re
import subprocess
import traceback
from datetime import datetime
from typing import Optional

import jwt
import toml
from django.conf import settings
from django.contrib import auth
from django.http import FileResponse, HttpResponse
from ninja import Router

from auxiliary.settings import BASE_DIR
from configuration.schema import UpdateSchemaOut, UserIn, SettingsIn
from toolbox import views as toolbox
from toolbox.schema import CommonResponse

# Create your views here.
logger = logging.getLogger('ptools')

router = Router(tags=['config'])


@router.post('/login', response=CommonResponse, description='登录')
def login(request, user_in: UserIn):
    print(user_in)
    user = auth.authenticate(request, **user_in.dict())
    if not user:
        return CommonResponse.error(msg='用户名或密码错误！')
    logger.info(f'{user.username} 登录成功！')
    payload = {
        "id": user.id,
        "username": user.username,
    }
    timeout = 60 * 24 * 30
    token = toolbox.get_token(payload, timeout)
    print(token)
    salt = settings.SECRET_KEY
    res = jwt.decode(token, salt, algorithms=["HS256"])
    print(res)
    return CommonResponse.success(data={
        'auth_token': token,
        'user': user.username
    })


@router.get('/userinfo', response=CommonResponse, description='获取用户信息')
def get_user_info(request):
    user = request.user
    print(user)
    return CommonResponse.success(data={
        'user': user.username
    })


@router.get('update/log', response=CommonResponse[Optional[UpdateSchemaOut]], description='更新日志')
def update_page(request):
    """更新日志"""
    try:
        local_logs = toolbox.get_git_log(n=1)
        logger.info('本地代码日志{} \n'.format(local_logs))
        update_notes = toolbox.get_git_log('origin/master', n=10)
        logger.info('远程代码日志{} \n'.format(update_notes))
        return CommonResponse.success(data={
            'local_logs': local_logs[0],
            'update_notes': update_notes,
            'update': datetime.strptime(update_notes[0].get('date'), '%Y-%m-%d %H:%M:%S') > datetime.strptime(
                local_logs[0].get('date'), '%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        msg = f'更新日志获取失败：{e}'
        logger.error(msg)
        logger.error(traceback.format_exc(5))
        return CommonResponse.error(msg=msg)


@router.get('update/migrate', response=CommonResponse, description='同步数据库')
def do_xpath(request):
    """同步数据库，初始化Xpath规则"""
    migrate_commands = {
        '备份数据库': 'cp db/db.sqlite3 db/db.sqlite3-$(date "+%Y%m%d%H%M%S")',
        '同步数据库': 'python manage.py migrate',
    }
    try:
        logger.info('开始初始化Xpath规则')
        # p = subprocess.run('cp db/db.sqlite3 db/db.sqlite3-$(date "+%Y%m%d%H%M%S")', shell=True)
        # logger.info('备份数据库 命令执行结果：\n{}'.format(p))
        # result = {
        #     'command': '备份数据库',
        #     'res': p.returncode
        # }
        result = toolbox.exec_command(migrate_commands)
        logger.info('初始化Xpath规则 命令执行结果：\n{}'.format(result))
        return CommonResponse.success(
            msg='初始化Xpath规则成功！',
            data={'result': result}
        )
    except Exception as e:
        # raise
        msg = '初始化Xpath失败!{}'.format(str(e))
        logger.error(msg)
        return CommonResponse.error(msg=msg)


@router.get('update/restart/{cid}', response=CommonResponse, description='重启容器')
def do_restart(request, cid: str):
    """重启容器"""
    try:
        logger.info('重启中')
        subprocess.Popen('docker restart {}'.format(cid), shell=True, stdout=subprocess.PIPE, )
        return CommonResponse.success(
            msg='重启指令发送成功，容器重启中 ... 15秒后自动刷新页面 ...'
        )
    except Exception as e:
        return CommonResponse.error(msg=f'重启指令发送失败!{e}')


@router.get('log', response=CommonResponse, description='获取日志列表')
def get_log_list(request):
    path = os.path.join(BASE_DIR, 'logs')
    # logger.info(path)
    # logger.info(os.listdir(path))
    names = [name for name in os.listdir(path)
             if os.path.isfile(os.path.join(path, name))]
    names = sorted(names, key=lambda x: os.stat(os.path.join(BASE_DIR, f'logs/{x}')).st_ctime, reverse=True)
    # logger.info(names)
    return CommonResponse.success(data=names)


@router.get('log/content', response=CommonResponse, description='获取日志内容')
def get_log_content(request, file_name: str):
    path = os.path.join(BASE_DIR, 'logs/' + file_name)
    with open(path, 'r') as f:
        logs = f.readlines()
    logs.reverse()
    return CommonResponse.success(data=''.join(logs))


@router.delete('log', response=CommonResponse, description='删除日志文件')
def remove_log_api(request, file_name: str):
    path = os.path.join(BASE_DIR, f'logs/{file_name}')
    try:
        os.remove(path)
        return CommonResponse.success(msg='删除成功！')
    except Exception as e:
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg='删除文件出错啦！详情请查看日志')


@router.get('log/download', response=CommonResponse, description='下载日志文件')
def download_log_file(request, file_name: str):
    try:
        file_path = os.path.join(BASE_DIR, f'logs/{file_name}')
        response = FileResponse(open(file_path, 'rb'))
        response['content-type'] = "application/octet-stream;charset=utf-8"
        response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(file_path)
        return response
    except Exception as e:
        return CommonResponse.error(msg=f'文件不存在？！{e}')


@router.get('/shell', description='执行简易终端命令')
def exec_shell_command(request, command: str):
    logger.info(f'当前命令：{command}')
    p = subprocess.getoutput(command)
    logger.info(f'命令执行结果：{p}')
    return CommonResponse.success(data=p)


"""
@router.get('helper/license/', response=CommonResponse, description='更新License')
def get_helper_license(request):
    result = pt_site.auto_update_license()
    if result.code == 0:
        return JsonResponse(data=result.to_dict(), safe=False)
    return JsonResponse(data=CommonResponse.error(
        msg='License更新失败！'
    ).to_dict(), safe=False)
  
# 保存配置文件  
def save_config_api(request):
    content = json.loads(request.body.decode())
    logger.info(content.get('settings'))
    if content.get('name') == 'ptools.toml':
        file_path = os.path.join(BASE_DIR, 'db/ptools.toml')
    if content.get('name') == 'hosts':
        file_path = os.path.join(BASE_DIR, 'db/hosts')
    try:
        with open(file_path, 'w') as f:
            f.write(content.get('settings'))
            return JsonResponse(data=CommonResponse.success(
                msg='配置文件保存成功！'
            ).to_dict(), safe=False)
    except Exception as e:
        # raise
        return JsonResponse(data=CommonResponse.error(
            msg=f'获取配置文件信息失败！{e}'
        ).to_dict(), safe=False)
"""


@router.get('/system', response=CommonResponse, )
def parse_toml(request):
    try:
        file_path = os.path.join(BASE_DIR, 'db/ptools.toml')
        if not os.path.exists(file_path):
            subprocess.getoutput('touch db/ptools.toml')
            logger.info(f'配置文件生成成功!')
        return CommonResponse.success(data=toml.load(file_path))
    except toml.decoder.TomlDecodeError as e:
        # Key name found without value. Reached end of line. (line 7 column 2 char 77)
        pattern = r"line (\d+)"  # 匹配 "Line 7: " 后面的数字，并捕获为一个组
        result = re.search(pattern, str(e))
        return CommonResponse.error(msg=f'配置文件加载失败！错误出现在第{result.group(1)}行。配置项未设定值！{e}')
    except Exception as e:
        return CommonResponse.error(msg=f'配置文件加载失败！{e}')


@router.get('/config', response=CommonResponse, )
def get_config_api(request, name: str):
    try:
        if name == 'ptools.toml':
            file_path = os.path.join(BASE_DIR, 'db/ptools.toml')
            if not os.path.exists(file_path):
                subprocess.getoutput('touch db/ptools.toml')
                logger.info(f'配置文件生成成功!')
        if name == 'hosts':
            file_path = os.path.join(BASE_DIR, 'db/hosts')
            if not os.path.exists(file_path):
                subprocess.getoutput('touch db/hosts')
        with open(file_path, 'rb') as f:
            response = HttpResponse(f)
            logger.info(response)
            return CommonResponse.success(data=response.content.decode('utf8'))
    except Exception as e:
        return CommonResponse.error(msg='获取配置文件信息失败！')


@router.put('/config', response=CommonResponse, )
def save_config_api(request, setting: SettingsIn):
    if setting.name == 'ptools.toml':
        file_path = os.path.join(BASE_DIR, 'db/ptools.toml')
    if setting.name == 'hosts':
        file_path = os.path.join(BASE_DIR, 'db/hosts')
    try:
        with open(file_path, 'w') as f:
            f.write(setting.content)
            return CommonResponse.success(msg='配置文件保存成功！')
    except Exception as e:
        # raise
        return CommonResponse.error(msg=f'获取配置文件信息失败！{e}')


@router.get("/notify/test", response=CommonResponse)
def get_notify(request, title: str, message: str):
    try:
        res = toolbox.send_text(title=title, message=message)
        return CommonResponse.success(data=res)
    except Exception as e:
        logger.error(traceback.format_exc(3))
        msg = f'通知获取失败:{e}'
        logger.error(msg)
        return CommonResponse.error(msg=msg)

# @router.get("/notifies", response=CommonResponse[List[NotifySchema]])
# def get_all_notify(request):
#     notifies = Notify.objects.all()
#     return CommonResponse.success(data=list(notifies))
#
#
# @router.get("/notify", response=CommonResponse[Optional[NotifySchema]])
# def get_notify(request, id: int):
#     try:
#         notify = Notify.objects.get(id=id)
#         return CommonResponse.success(data=notify)
#     except Exception as e:
#         logger.error(traceback.format_exc(3))
#         msg = f'通知获取失败:{e}'
#         logger.error(msg)
#         return CommonResponse.error(msg=msg)
#
#
# @router.post("/notify", response=CommonResponse[NotifySchema])
# def create_notify(request, notify: NotifySchema):
#     try:
#         notify_obj = Notify.objects.create(**notify.dict())
#         return CommonResponse.success(data=notify_obj)
#     except Exception as e:
#         logger.error(traceback.format_exc(3))
#         msg = f'通知修改失败:{e}'
#         logger.error(msg)
#         return CommonResponse.error(msg=msg)
#
#
# @router.put("/notify", response=CommonResponse[NotifySchema])
# def update_notify(request, notify: NotifySchema):
#     try:
#         notify_obj = Notify.objects.get(id=notify.id)
#         for attr, value in notify.dict().items():
#             setattr(notify_obj, attr, value)
#         notify_obj.save()
#         return CommonResponse.success(data=notify_obj)
#     except Exception as e:
#         logger.error(traceback.format_exc(3))
#         msg = f'通知修改失败:{e}'
#         logger.error(msg)
#         return CommonResponse.error(msg=msg)
#
#
# @router.delete("/notify", response=CommonResponse)
# def delete_notify(request, id: int):
#     try:
#         notify = Notify.objects.get(id=id)
#         notify.delete()
#         msg = f'{notify.name} 删除成功！'
#         logger.info(msg)
#         return CommonResponse.success(msg=msg)
#     except Exception as e:
#         logger.error(traceback.format_exc(3))
#         msg = f'通知删除失败:{e}'
#         logger.error(msg)
#         return CommonResponse.error(msg=msg)
