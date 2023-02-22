import logging
import os
import subprocess
import traceback
from datetime import datetime

import docker
from django.contrib import auth
from django.http import FileResponse
from ninja import Router
from ninja.responses import codes_4xx

from auxiliary.settings import BASE_DIR
from configuration.schema import UpdateSchemaOut, UserIn
from monkey.schema import CommonMessage
from toolbox import views as toolbox
from toolbox.schema import CommonResponse

# Create your views here.
logger = logging.getLogger('ptools')

router = Router(tags=['config'])


@router.post('/login', description='登录')
def login(request, user_in: UserIn):
    print(user_in)
    res = auth.authenticate(request, username=user_in.username, password=user_in.password)
    print(type(res))
    return 'ok'


@router.get('update/log', response={200: UpdateSchemaOut, codes_4xx: CommonMessage}, description='更新日志')
def update_page(request):
    """更新日志"""
    try:
        # 获取docker对象
        client = docker.from_env()
        # 从内部获取容器id
        cid = ''
        delta = 0
        restart = 'false'
        for c in client.api.containers():
            if 'ngfchl/ptools' in c.get('Image'):
                cid = c.get('Id')
                delta = c.get('Status')
                restart = 'true'
    except Exception as e:
        cid = ''
        restart = 'false'
        delta = '程序未在容器中启动？'
    branch = os.getenv('DEV') if os.getenv('DEV') else 'master'
    local_logs = toolbox.get_git_log(branch)
    logger.info('本地代码日志{} \n'.format(local_logs))
    update_notes = toolbox.get_git_log('origin/' + branch)
    logger.info('远程代码日志{} \n'.format(update_notes))
    if datetime.strptime(
            update_notes[0].get('date'), '%Y-%m-%d %H:%M:%S') > datetime.strptime(
        local_logs[0].get('date'), '%Y-%m-%d %H:%M:%S'
    ):
        update = 'true'
        update_tips = '已有新版本，请根据需要升级！'
    else:
        update = 'false'
        update_tips = '目前您使用的是最新版本！'
    return {
        'cid': cid,
        'delta': delta,
        'restart': restart,
        'local_logs': local_logs,
        'update_notes': update_notes,
        'update': update,
        'update_tips': update_tips,
        'branch': ('开发版：{}，更新于{}' if branch == 'dev' else '稳定版：{}，更新于{}').format(
            local_logs[0].get('hexsha'), local_logs[0].get('date'))
    }


@router.get('update/migrate', response=CommonMessage, description='同步数据库')
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


@router.get('update/restart/{cid}', response=CommonMessage, description='重启容器')
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


@router.get('file/list/{filename}', response=CommonResponse, description='获取日志列表')
def get_log_list(request, filename: str):
    path = os.path.join(BASE_DIR, 'db')
    # logger.info(path)
    # logger.info(os.listdir(path))
    names = [name for name in os.listdir(path)
             if os.path.isfile(os.path.join(path, name)) and name.startswith(filename)]
    names = sorted(names, key=lambda x: os.stat(os.path.join(BASE_DIR, f'db/{x}')).st_ctime, reverse=True)
    # logger.info(names)
    return CommonResponse.success(data={'path': path, 'names': names})


@router.get('file/content/{filename}', response=CommonResponse, description='获取日志内容')
def get_log_content(request, filename: str):
    path = os.path.join(BASE_DIR, 'db/' + filename)
    with open(path, 'r') as f:
        logs = f.readlines()
    logger.info(f'日志行数：{len(logs)}')
    return CommonResponse.success(data={'path': path, 'logs': logs, })


@router.get('file/content/{filename}', response=CommonResponse, description='删除日志文件')
def remove_log_api(request, filename: str):
    path = os.path.join(BASE_DIR, f'db/{filename}')
    try:
        os.remove(path)
        return CommonResponse.success(msg='删除成功！')
    except Exception as e:
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg='删除文件出错啦！详情请查看日志')


@router.get('file/remove/{filename}', response=CommonResponse, description='下载日志文件')
def download_log_file(request, filename: str):
    try:
        file_path = os.path.join(BASE_DIR, f'db/{filename}')
        response = FileResponse(open(file_path, 'rb'))
        response['content-type'] = "application/octet-stream;charset=utf-8"
        response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(file_path)
        return response
    except Exception as e:
        return CommonResponse.error(msg=f'文件不存在？！{e}')


@router.get('/shell/{command}', description='执行简易终端命令')
def exec_shell_command(request, command: str):
    p = subprocess.getoutput(command)
    logger.info(p)
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
