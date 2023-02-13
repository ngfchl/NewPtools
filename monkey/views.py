import logging
import traceback

from ninja import Router, Form
from ninja.responses import codes_4xx

from my_site.models import MySite
from toolbox import views as toolbox
from .schema import *

# Create your views here.
logger = logging.getLogger('ptools')

router = Router(tags=['monkey'])


@router.get('get_site/{token}/{host}', response={200: WebSiteMonkeySchemaOut, codes_4xx: CommonMessage})
def get_site_by_host(request, token: str, host: str):
    """根据油猴发来的站点host返回站点相关信息"""
    logger.info(token)
    check_token = toolbox.check_token(token)
    if len(token) > 0 and not check_token:
        return 401, {'msg': 'Token认证失败！', 'code': -1}
    # logger.info(url)
    site_list = WebSite.objects.filter(url__contains=host)
    if len(site_list) == 1:
        # data = {'site_id': site.id, 'uid_xpath': site.my_uid_rule}
        return site_list.first()
    return 404, {'msg': '站点信息获取失败！', 'code': -1}


@router.post('save_site/{token}', response=CommonMessage)
def save_site_by_monkey(request, token: str, mysite: MySiteSchemaIn = Form(...)):
    try:
        check_token = toolbox.check_token(token)
        if len(token) > 0 and not check_token:
            return 401, {'msg': 'Token认证失败！', 'code': -1}
        logger.info(mysite)
        # logger.info(site)
        res_my_site = MySite.objects.update_or_create(site=mysite.site, defaults=mysite.dict())
        logger.info(res_my_site[1])
        # todo 结果保存后获取一次数据，并更新一次注册时间
        return {
            'code': 0,
            'msg': f'{res_my_site[0].nickname} Cookie信息 {"添加成功！" if res_my_site[1] else "更新成功！"}'
        }
    except Exception as e:
        logger.info(traceback.format_exc(3))
        return {'msg': f'添加站点信息失败！{e}', 'code': -1}
