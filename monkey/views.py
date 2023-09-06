import json
import logging
import traceback

from ninja import Router, Form

from my_site.models import MySite, TorrentInfo
from toolbox import views as toolbox
from toolbox.schema import CommonResponse
from .schema import *

# Create your views here.
logger = logging.getLogger('ptools')

router = Router(tags=['monkey'])


@router.get('get_site/{token}/{host}', response=CommonResponse[WebSiteMonkeySchemaOut])
def get_site_by_host(request, token: str, host: str):
    """根据油猴发来的站点host返回站点相关信息"""
    try:
        logger.info(token)
        check_token = toolbox.check_token(token)
        if len(token) > 0 and not check_token:
            return CommonResponse.error(msg='Token认证失败！')
        # logger.info(url)
        site_list = WebSite.objects.filter(url__contains=host)
        if len(site_list) == 1:
            # data = {'site_id': site.id, 'uid_xpath': site.my_uid_rule}
            # return site_list.first()
            return CommonResponse.success(data=site_list.first())
        msg = f'{host} 站点信息获取失败！'
        return CommonResponse.error(msg=msg)
    except Exception as e:
        msg = f'站点信息获取失败！{e}'
        logger.error(msg)
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg=msg)


@router.post('save_site/{token}', response=CommonResponse)
def save_site_by_monkey(request, token: str, mysite: MySiteSchemaIn = Form(...)):
    try:
        check_token = toolbox.check_token(token)
        if len(token) > 0 and not check_token:
            return CommonResponse.error(msg='Token认证失败！')
        logger.info(mysite)
        # logger.info(site)
        params = mysite.dict()
        if mysite.time_join is None:
            params.pop('time_join')
        if mysite.passkey is None:
            params.pop('passkey')
        logger.info(params)
        res_my_site = MySite.objects.update_or_create(site=mysite.site, defaults=params)
        logger.info(res_my_site[1])
        # todo 结果保存后获取一次数据，并更新一次注册时间
        msg = f'{res_my_site[0].nickname} Cookie信息 {"添加成功！" if res_my_site[1] else "更新成功！"}'
        return CommonResponse.success(msg=msg)
    except Exception as e:
        msg = f'添加站点信息失败！{e}'
        logger.error(msg)
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg=msg)


@router.post('parse_torrents', response=CommonResponse)
def get_torrents_from_monkey(request):
    try:
        torrents = json.loads(request.body)
        count_create = 0
        count_updated = 0
        count_failed = 0
        for torrent in torrents:
            try:
                torrent = {key: value for key, value in torrent.items() if value}
                torrent['size'] = toolbox.FileSizeConvert.parse_2_byte(torrent['size'].strip())
                logger.info(torrent)
                t, created = TorrentInfo.objects.update_or_create(
                    site_id=torrent.get('site_id'),
                    tid=torrent.get('tid'),
                    defaults=torrent
                )
                if created:
                    count_create += 1
                else:
                    count_updated += 1
            except Exception as e:
                logger.error(f'{torrent.get("title")} 解析保存失败！{e}')
                logger.error(traceback.format_exc(3))
                count_failed += 1
                continue
        msg = f'种子信息同步完成！成功新增种子 {count_create}，更新 {count_updated}，失败 {count_failed}'
        return CommonResponse.success(msg=msg)
    except Exception as e:
        msg = f'种子信息同步失败！{e}'
        logger.error(msg)
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg=msg)
