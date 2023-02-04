import logging
import traceback

from ninja import Router
from ninja.responses import codes_4xx

from toolbox import views as toolbox
from .schema import *

# Create your views here.
logger = logging.getLogger('ptools')

router = Router(tags=['monkey'])


@router.get('get_site/{token}/{host}', response={200: WebSiteMonkeySchemaOut, codes_4xx: CommonMessage})
def get_site_by_host(request, token: str, host: str):
    """根据油猴发来的站点host返回站点相关信息"""
    own_token = toolbox.parse_token('token')
    # url = request.GET.get('url')
    # token = request.GET.get('token')
    # token = params.token
    if len(token) > 0 and token != own_token.get('token'):
        return 401, {'msg': 'Token认证失败！', 'code': -1}
    # logger.info(url)
    site_list = WebSite.objects.filter(url__contains=host)
    if len(site_list) == 1:
        # data = {'site_id': site.id, 'uid_xpath': site.my_uid_rule}
        return site_list.first()
    return 404, {'msg': '站点信息获取失败！', 'code': -1}


def save_site_by_monkey(request):
    own_token = toolbox.parse_token('token').data
    logger.info(request.POST)
    my_site_params = request.POST.copy()
    logger.info(my_site_params)
    token = my_site_params.get('token')
    if len(token) > 0 and token != own_token.get('token'):
        return CommonResponse.error(msg='Token认证失败！').to_dict()
    site_id = my_site_params.get('site_id')
    logger.info(site_id)
    my_site_params.pop('token')
    try:
        res_my_site = MySite.objects.update_or_create(site_id=site_id, defaults=my_site_params)
        logger.info(res_my_site[1])
        return CommonResponse.success(
            msg=f'{res_my_site[0].site.name} Cookie信息 {"添加成功！" if res_my_site[1] else "更新成功！"}'
        ).to_dict()
    except:
        logger.info(traceback.format_exc(3))
        return CommonResponse.error(msg='站点信息添加失败！').to_dict()
