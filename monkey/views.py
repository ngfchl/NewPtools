import json
import logging
import traceback

from django.core.cache import cache
from ninja import Router, Form

from my_site.models import MySite, TorrentInfo
from spider.views import PtSpider
from toolbox import views as toolbox
from toolbox.schema import CommonResponse
from .schema import *

# Create your views here.
logger = logging.getLogger('ptools')

router = Router(tags=['monkey'])
pt_spider = PtSpider()


@router.get('get_site/{token}/{host}', response=CommonResponse[Optional[WebSiteMonkeySchemaOut]])
def get_site_by_host(request, token: str, host: str):
    """根据油猴发来的站点host返回站点相关信息"""
    try:
        logger.info(token)
        check_token = toolbox.check_token(token)
        if len(token) > 0 and not check_token:
            return CommonResponse.error(msg='Token认证失败！')
        # logger.info(url)
        site_list = WebSite.objects.filter(url__contains=host)
        if not site_list:
            my_site = MySite.objects.filter(mirror__contains=host).first()
            if not my_site:
                msg = f'{host} 站点信息获取失败，请检查网址是否正确！'
                return CommonResponse.error(msg=msg)
            return CommonResponse.success(data=WebSite.objects.get(id=my_site.site))
        if len(site_list) == 1:
            # data = {'site_id': site.id, 'uid_xpath': site.my_uid_rule}
            # return site_list.first()
            logger.info(site_list.first())
            return CommonResponse.success(data=site_list.first())
        msg = f'{host} 站点信息获取失败，请检查网址是否正确！'
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
                sale_expire = torrent["sale_expire"]
                if '限时' in sale_expire:
                    torrent["sale_expire"] = toolbox.parse_and_calculate_expiry(sale_expire)
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


@router.post('torrents/iyuu', response=CommonResponse[Optional[MonkeyRepeatTorrentListOut]])
def get_torrents_list_from_iyuu(request, hash_string: str = Form(...), site_id: str = Form(...)):
    """从IYUU获取种子辅种信息"""
    monkey_iyuu_data = cache.get("monkey_iyuu_data", {})
    data = monkey_iyuu_data.get(hash_string)
    if not data:
        res = toolbox.get_torrents_hash_from_iyuu([hash_string])
        if res.code != 0:
            logger.warning(res.msg)
            return CommonResponse.error(msg=res.msg)
        torrents = res.data.get(hash_string)
        website_list = WebSite.objects.exclude(id=site_id)
        mysite_list = MySite.objects.exclude(site=site_id)
        had_list = []
        url_list = []
        if len(torrents) <= 0:
            return CommonResponse.success(data={
                "url_list": url_list,
                "can_list": list(website_list),
            })
        for torrent in torrents:
            sid = torrent.get('site_id')
            try:
                website = website_list.filter(id=sid).first()
                if not website:
                    logger.info(f'不支持的站点：{sid}')
                    continue
                my_site = mysite_list.filter(site=sid).first()
                if not my_site:
                    logger.info(f'未添加的站点：{website.name}')
                    continue
                had_list.append(sid)
                url_list.append({
                    "download_url": pt_spider.generate_magnet_url(sid, torrent, my_site, website),
                    "details_url": f'{website.url}{website.page_detail.format(torrent.get("tid"))}',
                    "site": website
                })
            except Exception as e:
                logger.error(f'{torrent.get("hash_string")} 解析失败！{e}')
                continue
        id_list = [site.site for site in mysite_list.exclude(site__in=had_list)]
        can_list = list(website_list.filter(id__in=id_list))
        logger.info(id_list)
        logger.info(f"当前种子有{len(can_list)}个站点未发布！")
        data = {
            "url_list": url_list,
            "can_list": can_list,
        }
        monkey_iyuu_data[hash_string] = data
        cache.set("monkey_iyuu_data", monkey_iyuu_data)
    return CommonResponse.success(data=data)
