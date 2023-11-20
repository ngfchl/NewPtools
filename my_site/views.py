import json
import logging
import traceback
from datetime import timedelta
from math import inf

import demjson3
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from ninja import Router, Query

from my_site.schema import *
from my_site.schema import MySiteDoSchemaIn
from schedule import tasks as autopt
from spider.views import PtSpider
from toolbox import views as toolbox
from toolbox.schema import CommonResponse, CommonPaginateSchema
from website.models import UserLevelRule

# Create your views here.
logger = logging.getLogger('ptools')
pt_spider = PtSpider()
router = Router(tags=['mysite'])


@router.get('/mysite', response=CommonResponse[List[MySiteSchemaOut]], description='我的站点-列表')
def get_mysite_list(request):
    return CommonResponse.success(data=list(MySite.objects.order_by('time_join')))


@router.get('/mysite/get', response=CommonResponse[Optional[MySiteSchemaEdit]], description='我的站点-单个')
def get_mysite(request, mysite_id: int):
    try:
        my_site = MySite.objects.get(id=mysite_id)
        print(my_site.downloader)
        print(my_site.downloader_id)
        return CommonResponse.success(data=my_site)
    except Exception as e:
        print(e)
        return CommonResponse.error(msg='没有这个站点的信息哦')


@router.post('/mysite', response=CommonResponse, description='我的站点-添加')
def add_mysite(request, my_site_params: MySiteSchemaIn):
    try:
        if not my_site_params.site:
            return CommonResponse.error(msg=f'{my_site_params.nickname} 保存失败，请先完成必填项')
        logger.info(f'开始处理：{my_site_params.nickname}')
        logger.info(my_site_params)
        my_site_params.id = None
        params = my_site_params.dict()

        if not my_site_params.nickname:
            site = get_object_or_404(WebSite, id=my_site_params.site)
            params.update({
                "nickname": site.name
            })
        downloader = get_object_or_404(Downloader,
                                       id=my_site_params.downloader) if my_site_params.downloader else None
        params.update({
            "downloader": downloader,
            "remove_torrent_rules": json.dumps(demjson3.decode(my_site_params.remove_torrent_rules),
                                               indent=2) if my_site_params.remove_torrent_rules else '{}'
        })
        logger.info(params)
        my_site = MySite.objects.create(**params)
        if my_site:
            msg = f'处理完毕：{my_site.nickname}，保存成功！'
            logger.info(msg)
            return CommonResponse.success(msg=msg)
        return CommonResponse.error(msg=f'处理完毕：{my_site.nickname}，保存失败！')
    except IntegrityError as e:
        msg = f'{my_site_params.nickname} 站点信息已存在，请勿重复添加~！'
        return CommonResponse.error(msg=msg)
    except Exception as e:
        logger.info(traceback.format_exc(3))
        msg = f'{my_site_params.nickname} 参数有误，请确认后重试！{e}'
        return CommonResponse.error(msg=msg)


@router.put('/mysite', response=CommonResponse, description='我的站点-更新')
def edit_mysite(request, my_site_params: MySiteSchemaIn):
    try:
        logger.info(f'开始更新：{my_site_params.nickname}')
        print(my_site_params)
        params = my_site_params.dict()
        downloader = get_object_or_404(Downloader, id=my_site_params.downloader) if my_site_params.downloader else None
        params.update({
            "downloader": downloader,
            "remove_torrent_rules": json.dumps(demjson3.decode(my_site_params.remove_torrent_rules),
                                               indent=2) if my_site_params.remove_torrent_rules else '{}'
        })
        logger.info(params)
        my_site_res = MySite.objects.filter(id=my_site_params.id).update(**my_site_params.dict())
        if my_site_res > 0:
            logger.info(f'处理完毕：{my_site_params.nickname}，成功处理 {my_site_res} 条数据！')
            return CommonResponse.success(
                msg=f'{my_site_params.nickname} 信息更新成功！'
            )
        return CommonResponse.error(
            msg=f'{my_site_params.nickname} 信息更新失败！'
        )
    except Exception as e:
        logger.info(traceback.format_exc(3))
        msg = f'{my_site_params.nickname} 参数有误，请确认后重试！{e}'
        logger.info(msg)
        return CommonResponse.error(msg=msg)


@router.delete('/mysite', response=CommonResponse, description='我的站点-删除')
def remove_mysite(request, site_id: int):
    try:
        logger.info(f'开始删除站点：{site_id}')
        my_site_res = MySite.objects.get(id=site_id).delete()
        logger.info(my_site_res)
        if my_site_res[0] > 0:
            my_site = my_site_res[1]
            logger.info(f'删除成功：，成功删除 {my_site_res[0]} 条数据！')
            return CommonResponse.success(
                msg=f'站点删除成功！'
            )

        return CommonResponse.error(
            msg=f'站点删除失败！'
        )
    except Exception as e:
        logger.info(traceback.format_exc(30))
        msg = f'站点删除失败！{e}'
        logger.info(msg)
        return CommonResponse.error(msg=msg)


@router.get('/status', response=List[SiteStatusSchemaOut], description='每日状态-列表')
def get_status_list(request):
    return SiteStatus.objects.order_by('id').select_related('site')


@router.post('/status', response=CommonResponse[Optional[SiteStatusSchemaOut]], description='每日状态-更新')
def do_status(request, my_site: MySiteDoSchemaIn):
    return pt_spider.send_status_request(MySite.objects.get(id=my_site.site_id))


def get_status_by_mysite(request, my_site: MySiteDoSchemaIn):
    status = SiteStatus.objects.filter(site_id=my_site.site_id).last()
    print(status)
    return CommonResponse.success(data=status)


@router.post('/status/get', response=CommonResponse[Optional[StatusSchema]], description='每日状态-最新')
def get_newest_status(request, my_site: MySiteDoSchemaIn):
    try:
        my_site = MySite.objects.get(id=my_site.site_id)
        status = SiteStatus.objects.filter(site=my_site).order_by('-created_at').first()
        sign = SignIn.objects.filter(site=my_site, created_at__date=datetime.today().date()).first()
        level = UserLevelRule.objects.filter(site_id=my_site.site, level=status.my_level).first() if status else None
        next_level = None
        if level and level.level != 0:
            next_level = UserLevelRule.objects.filter(
                site_id=my_site.site,
                level_id=level.level_id + 1
            ).first() if level else None
            levels = UserLevelRule.objects.filter(
                site_id=my_site.site,
                level_id__lte=level.level_id,
                level_id__gt=0,
            ) if level else None
            if levels is not None and len(levels) > 0:
                rights = [l.rights for l in levels]
                level.rights = '||'.join(rights)
        return CommonResponse.success(data={
            'my_site': my_site,
            'site': WebSite.objects.filter(id=my_site.site).first(),
            'status': status if status else SiteStatus(site=my_site),
            'sign': sign,
            'level': level,
            'next_level': next_level
        })
    except Exception as e:
        print(e)
        return CommonResponse.success(data=None)


@router.get('/status/newest', response=CommonResponse[List[StatusSchema]], description='最新状态-列表')
def get_newest_status_list(request):
    my_site_list = MySite.objects.all()
    id_list = [SiteStatus.objects.filter(site=my_site.id).order_by('-created_at').first().id for my_site in
               my_site_list if SiteStatus.objects.filter(site=my_site.id).order_by('created_at').first()]
    status_list = SiteStatus.objects.filter(id__in=id_list)
    # my_site_id_list = [my_site.id for my_site in my_site_list]
    site_id_list = [my_site.site for my_site in my_site_list]
    site_list = WebSite.objects.all()
    sign_list = SignIn.objects.all()
    level_list = UserLevelRule.objects.filter(site_id__in=site_id_list)
    info_list = []
    for my_site in my_site_list:
        status = status_list.filter(site=my_site).first()
        sign = sign_list.filter(site=my_site, created_at__date=datetime.today().date()).first()
        level = level_list.filter(site_id=my_site.site, level=status.my_level).first() if status else None
        next_level = None
        if level and level.level != 0:
            next_level = level_list.filter(site_id=my_site.site, level_id=level.level_id + 1).first() if level else None
            levels = level_list.filter(
                site_id=my_site.site, level_id__lte=level.level_id,
                level_id__gt=0) if level else None
            if levels and len(levels) > 0:
                # logger.info(len(levels))
                rights = [l.rights for l in levels]
                level.rights = '||'.join(rights)
        info = {
            'my_site': my_site,
            'site': site_list.filter(id=my_site.site).first(),
            'status': status if status else SiteStatus(site=my_site),
            'sign': sign,
            'level': level,
            'next_level': next_level
        }
        logger.debug(info)
        info_list.append(info)
    print(len(info_list))
    return CommonResponse.success(data=info_list)


@router.get('/status/new', response=CommonResponse[List], description='更新最新状态-列表')
def get_newest_status_list_new(request):
    my_site_list = MySite.objects.all()
    id_list = [SiteStatus.objects.filter(site=my_site.id).order_by('-created_at').first().id for my_site in
               my_site_list if SiteStatus.objects.filter(site=my_site.id).order_by('created_at').first()]
    status_list = SiteStatus.objects.filter(id__in=id_list)
    # my_site_id_list = [my_site.id for my_site in my_site_list]
    site_id_list = [my_site.site for my_site in my_site_list]
    site_list = WebSite.objects.all()
    sign_list = SignIn.objects.all()
    level_list = UserLevelRule.objects.filter(site_id__in=site_id_list)
    info_list = []
    for my_site in my_site_list:
        site = site_list.filter(id=my_site.site).first()
        status = status_list.filter(site=my_site).first()
        level = level_list.filter(site_id=my_site.site, level=status.my_level).first() if status else None
        sign = sign_list.filter(site=my_site, created_at__date=datetime.today().date()).first()
        next_level = None
        if level and level.level != 0:
            next_level = level_list.filter(site_id=my_site.site, level_id=level.level_id + 1).first() if level else None
            levels = level_list.filter(
                site_id=my_site.site, level_id__lte=level.level_id,
                level_id__gt=0) if level else None
            if levels and len(levels) > 0:
                # logger.info(len(levels))
                rights = [l.rights for l in levels]
                level.rights = '||'.join(rights)
        info = {
            "site_name": site.name,
            "site_url": site.url,
            "site_logo": site.logo,
            "support_sign_in": site.sign_in,
            "site_get_info": site.get_info,
            # "site_upgrade_day": site.upgrade_day,
            "site_sp_full": site.sp_full,
            "site_page_message": site.page_message,

            "my_site_id": my_site.id,
            "my_site_sort_id": my_site.sort_id,
            "my_site_nickname": my_site.nickname,
            "my_site_get_info": my_site.get_info,
            "my_site_sign_in": my_site.sign_in,
            "my_site_joined": my_site.time_join,
        }
        if status:
            logger.debug(status.created_at)
            logger.debug(status.ratio)
            logger.debug(status.ratio == inf)

            info.update({
                # "status_torrents": status.torrents,
                "status_seed": status.seed,
                "status_uploaded": status.uploaded,
                "status_mail": status.mail,
                "status_my_hr": status.my_hr,
                "status_seed_volume": status.seed_volume,
                "status_my_bonus": float(status.my_bonus),
                "status_downloaded": status.downloaded,
                "status_bonus_hour": status.bonus_hour,
                "status_invitation": status.invitation,
                "status_my_score": float(status.my_score),
                "status_leech": status.leech,
                "status_my_level": status.my_level,
                "status_updated_at": status.updated_at,

                "status_ratio": float(0) if status.ratio == inf else float(status.ratio),

                "sign_sign_in_today": sign.sign_in_today if sign else False,
            })
        if level:
            info.update({
                "level_level": level.level,
                "level_rights": level.rights,
            })
        if next_level:
            info.update({
                "next_level_level": next_level.level,
                "next_level_downloaded": next_level.downloaded,
                "next_level_torrents": next_level.torrents,
                "next_level_uploaded": next_level.uploaded,
                "next_level_rights": next_level.rights,
                "next_level_score": float(next_level.score),
                "next_level_bonus": float(next_level.bonus),
                "next_level_ratio": float(next_level.ratio),
            })
        logger.debug(info)
        info_list.append(info)
    print(len(info_list))
    return CommonResponse.success(data=info_list)


@router.get('/torrents/rss', response=CommonResponse, description='RSS解析种子信息')
def get_status(request, site_id: int):
    res = autopt.auto_get_rss_torrent_detail.delay(site_id)
    return CommonResponse.success(msg=f'任务正在执行，任务ID：{res.id}')


@router.get('/torrents/update', response=CommonResponse[Optional[TorrentInfoSchemaOut]], description='更新单个种子信息')
def get_update_torrent(request, torrent_id: Union[int, str] = None):
    try:
        if isinstance(torrent_id, int):
            torrent = get_object_or_404(TorrentInfo, id=torrent_id)
            return pt_spider.get_update_torrent(torrent)
        else:
            res = autopt.auto_get_update_torrent.delay(torrent_id)
            return CommonResponse.success(msg=f'正在更新，任务ID：{res.id}')
    except Exception as e:
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg='种子信息拉取失败！')


@router.get('/signin', response=CommonResponse[CommonPaginateSchema[SignInSchemaOut]],
            description='每日签到-列表')
def get_signin_list(request, filters: PaginateQueryParamsSchemaIn = Query(...)):
    try:
        logger.info(filters.site_id)
        logger.info(filters.page * filters.limit)
        sign_list = SignIn.objects.filter(site_id=filters.site_id).order_by('-updated_at')
        page_list = Paginator(sign_list, filters.limit)
        print(page_list.get_page(filters.page))
        data = {
            'items': list(page_list.get_page(filters.page).object_list),
            'per_page': filters.page,
            'total': page_list.count
        }
        logger.info(data)
        return CommonResponse.success(data=data)
    except Exception as e:
        msg = f'获取签到历史失败：{e}'
        logger.error(msg)
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg=msg)


@router.post('/signin', response=CommonResponse, description='每日签到-手动签到')
def do_signin(request, sign_in: MySiteDoSchemaIn):
    """手动签到"""
    try:
        logger.info(f'手动签到中，站点id：{sign_in.site_id}')
        my_site = MySite.objects.get(id=sign_in.site_id)
        res = pt_spider.sign_in(my_site)
        logger.info(f'正在签到：{res}')
        # if res.code == 0:
        #     return CommonResponse.success(msg=res[0])
        return res
    except Exception as e:
        msg = f'签到失败：{e}'
        logger.error(msg)
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg=msg)


@router.post('/sign/do', response=CommonResponse, description='每日签到')
def sign_in_api(request):
    try:
        res = autopt.auto_sign_in.delay()
        return CommonResponse.success(msg=f'签到指令已发送，请注意查收推送消息！任务id：{res.id}')
    except Exception as e:
        logger.error(f'签到失败：{e}')
        logger.error(traceback.format_exc(limit=3))
        return CommonResponse.error(msg=f'签到失败：{e}')


@router.get('/signin/{int:signin_id}', response=SignInSchemaOut, description='每日状态-单个')
def get_signin(request, signin_id):
    return get_object_or_404(SignIn, id=signin_id)


@router.post('/import', response=CommonResponse, description='PTPP备份导入')
def import_from_ptpp(request, data: ImportSchema):
    try:
        data_list = toolbox.parse_ptpp_cookies(data)
        res = autopt.import_from_ptpp.delay(data_list)
        return CommonResponse.success(msg=f'正在导入站点信息，请注意查收推送消息！任务id：{res.id}')
    except Exception as e:
        logger.info(traceback.format_exc(3))
        return CommonResponse.error(msg='站点数据导入失败！')


@router.get('/status/chart', response=CommonResponse, description='站点数据展示')
def site_data_api(request, site_id: int = 0, days: int = -7):
    """站点数据(柱状图)"""
    # my_site_id = request.GET.get('id')
    logger.info(f'ID值：{type(site_id)}')
    if int(site_id) == 0:
        my_site_list = MySite.objects.all()
        diff_list = []
        # 提取日期
        date_list_set = set([
            status.created_at.date().strftime('%Y-%m-%d') for status in SiteStatus.objects.all()
        ])
        date_list = list(date_list_set)
        date_list.sort()
        logger.info(date_list)
        # for my_site in my_site_list:
        #     try:
        #         site_info = parse_site_data_to_chart(my_site)
        #         inner_date_list = site_info.get('date_list')
        #         diff_uploaded_list = site_info.get('diff_uploaded_list')
        #         diff_downloaded_list = site_info.get('diff_downloaded_list')
        #         uploaded_list = site_info.get('uploaded_list')
        #         downloaded_list = site_info.get('downloaded_list')
        #         diff_date_list = date_list_set - set(inner_date_list)
        #         logger.info(diff_date_list)
        #         diff_list.append(site_info)
        #     except Exception as e:
        #         logger.error(f'{my_site.nickname} 尚未获取过数据！')
        #         logger.error(traceback.format_exc(limit=3))
        #         continue
        # logger.info(f'日期列表：{date_list}')
        logger.info(f'日期数量：{len(date_list)}')

        for my_site in my_site_list:
            # 每个站点获取自己站点的所有信息
            site_status_list = my_site.sitestatus_set.order_by('created_at').all()
            # logger.info(f'站点数据条数：{len(site_status_list)}')
            info_list = [
                {
                    'uploaded': site_info.uploaded,
                    'downloaded': site_info.downloaded,
                    'date': site_info.created_at.date().strftime('%Y-%m-%d')
                } for site_info in site_status_list
            ]
            # logger.info(f'提取完后站点数据条数：{len(info_list)}')

            # 生成本站点的增量列表，并标注时间
            '''
            site_info_list = [{
                'name': my_site.site.name,
                'type': 'bar',
                'stack': info_list[index + 1]['date'],
                'value': info_list[index + 1]['uploaded'] - info['uploaded'] if index < len(
                    info_list) - 1 else 0,
                'date': info['date']
            } for (index, info) in enumerate(info_list) if index < len(info_list) - 1]
            '''
            # diff_info_list = {
            #     info['date']: info['uploaded'] - info_list[index - 1]['uploaded'] if
            #     info['uploaded'] - info_list[index - 1]['uploaded'] > 0 else 0 for
            #     (index, info) in enumerate(info_list) if 0 < index < len(info_list)
            #
            # }
            diff_info_list = {}
            for (index, info) in enumerate(info_list):
                if index == 0:
                    diff_uploaded = info['uploaded']
                    diff_downloaded = info['downloaded']
                else:
                    diff_uploaded = info['uploaded'] - info_list[index - 1]['uploaded'] if \
                        info['uploaded'] > info_list[index - 1]['uploaded'] else 0
                    diff_downloaded = info['downloaded'] - info_list[index - 1]['downloaded'] if \
                        info['downloaded'] > info_list[index - 1]['downloaded'] else 0
                diff_info = {
                    info['date']: {
                        'diff_uploaded': diff_uploaded,
                        'diff_downloaded': diff_downloaded
                    }
                }
                diff_info_list.update(diff_info)

            # logger.info(f'处理完后站点数据条数：{len(diff_info_list)}')
            for date in date_list[days:]:
                if not diff_info_list.get(date):
                    diff_info_list[date] = {
                        'diff_uploaded': 0,
                        'diff_downloaded': 0
                    }
            # logger.info(diff_info_list)
            # logger.info(len(diff_info_list))
            diff_info_list = sorted(diff_info_list.items(), key=lambda x: x[0])
            diff_list.append({
                'name': my_site.nickname,
                'diff_uploaded_list': [value[1].get('diff_uploaded') for value in diff_info_list][days:],
                'diff_downloaded_list': [value[1].get('diff_downloaded') for value in diff_info_list][days:]
            })

        return CommonResponse.success(
            data={'date_list': date_list[days:], 'diff': diff_list}
        )
    else:
        logger.info(f'前端传来的站点ID：{site_id}')
        my_site = MySite.objects.filter(id=site_id).first()
        if not my_site:
            return CommonResponse.error(
                msg='访问出错咯！没有这个站点...'
            )
        return CommonResponse.success(data=parse_site_data_to_chart(my_site, days))


def generate_date_list(num_days):
    # Get today's date
    today = datetime.now().date()

    # Generate a list of dates for the specified number of days
    date_list = [today - timedelta(days=i) for i in range(num_days, -1, -1)]

    return date_list


@router.get('/status/chart/v2', response=CommonResponse[List[SiteDataToChart]], description='站点数据展示')
def get_site_data_to_chart(request, site_id: int = 0, days: int = 7):
    site_status_list = []
    date_list = generate_date_list(days)
    if int(site_id) == 0:
        my_site_list = MySite.objects.all()
        for my_site in my_site_list:
            status_list = list(
                my_site.sitestatus_set.filter(updated_at__date__in=date_list).order_by('created_at'))
            for status in status_list:
                if status.downloaded == 0:
                    status.ratio = 0
            site_status_list.append({
                "site": my_site,
                'data': status_list,
            })
        return CommonResponse.success(data=site_status_list)


def parse_site_data_to_chart(my_site: MySite, days: int = -7):
    site_info_list = my_site.sitestatus_set.order_by('created_at').all()
    if len(site_info_list) <= 0:
        raise '你还没有获取过这个站点的数据...'
    logger.info(site_info_list)
    site = get_object_or_404(WebSite, id=my_site.site)

    uploaded_list = []
    diff_uploaded_list = []
    downloaded_list = []
    diff_downloaded_list = []
    bonus_list = []
    score_list = []
    ratio_list = []
    seeding_size_list = []
    seeding_list = []
    leeching_list = []
    invitation_list = []
    bonus_hour_list = []
    date_list = []
    for (index, site_info) in enumerate(list(site_info_list)[days:]):
        # for (index, info) in enumerate(info_list):
        if index == 0:
            diff_uploaded = site_info.uploaded
            diff_downloaded = site_info.downloaded
        else:
            diff_uploaded = site_info.uploaded - site_info_list[index - 1].uploaded
            diff_downloaded = site_info.downloaded - site_info_list[index - 1].downloaded
        diff_uploaded_list.append(diff_uploaded)
        diff_downloaded_list.append(diff_downloaded)
        uploaded_list.append(site_info.uploaded)
        downloaded_list.append(site_info.downloaded)
        bonus_list.append(site_info.my_bonus)
        score_list.append(site_info.my_score)
        ratio_list.append(0 if site_info.ratio == float('inf') else site_info.ratio)
        seeding_size_list.append(site_info.seed_volume)
        seeding_list.append(site_info.seed)
        leeching_list.append(site_info.leech)
        invitation_list.append(site_info.invitation)
        bonus_hour_list.append(site_info.bonus_hour)
        date_list.append(site_info.updated_at.strftime('%Y-%m-%d'))
    logger.info(site)
    # logger.info(site_status_list)
    my_site_info = {
        'id': my_site.id,
        'name': site.name,
        'icon': site.logo,
        'url': site.url,
        'level': site_info_list.first().my_level,
        'last_active': site_info_list.first().updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        'uploaded_list': uploaded_list,
        'downloaded_list': downloaded_list,
        'diff_uploaded_list': diff_uploaded_list,
        'diff_downloaded_list': diff_downloaded_list,
        'bonus_list': bonus_list,
        'score_list': score_list,
        'ratio_list': ratio_list,
        'seeding_size_list': seeding_size_list,
        'seeding_list': seeding_list,
        'leeching_list': leeching_list,
        'invitation_list': invitation_list,
        'bonus_hour_list': bonus_hour_list,
        'date_list': date_list,
    }
    return my_site_info


@router.post('/status/do', response=CommonResponse, description='刷新站点数据')
def update_site_api(request):
    try:
        res = autopt.auto_get_status.delay()
        return CommonResponse.success(msg=f'数据更新指令已发送，请注意查收推送消息！任务id：{res}')
    except Exception as e:
        logger.error(f'数据更新失败：{e}')
        logger.error(traceback.format_exc(limit=3))
        return CommonResponse.error(msg=f'数据更新失败：{e}')


@router.get('/sign/show/{site_id}', response=CommonResponse, description='站点签到信息')
def show_sign_api(request, site_id: int):
    try:
        my_site = MySite.objects.filter(id=site_id).first()
        site = get_object_or_404(WebSite, id=my_site.site)
        sign_in_list = my_site.signin_set.order_by('-pk')[:15]
        sign_in_list = [
            {'created_at': sign_in.created_at.strftime('%Y-%m-%d %H:%M:%S'), 'sign_in_info': sign_in.sign_in_info}
            for sign_in in sign_in_list]
        site_info = {
            'id': site.id,
            'name': site.name,
            'icon': site.logo,
            'url': site.url,
            'last_active': datetime.strftime(my_site.updated_at, '%Y年%m月%d日%H:%M:%S'),
        }
        return CommonResponse.success(data={'site': site_info, 'sign_in_list': sign_in_list})
    except Exception as e:
        logger.error(f'签到历史数据获取失败：{e}')
        logger.error(traceback.format_exc(limit=3))
        return CommonResponse.error(
            msg=f'签到历史数据获取失败：{e}'
        )


@router.post('/sort', response=CommonResponse, description='站点排序')
def site_sort_api(request, my_site: MySiteDoSchemaIn):
    try:
        MySite.objects.filter(pk=my_site.site_id).update(sort_id=my_site.sort_id)
        return CommonResponse.success(msg='排序成功！')
    except Exception as e:
        logger.error(f'数据更新失败：{e}')
        logger.error(traceback.format_exc(limit=3))
        return CommonResponse.error(msg=f'数据更新失败：{e}')


@router.get('/status/today', response=CommonResponse)
def today_data(request):
    total_upload, total_download, increase_info_list = toolbox.today_data()
    return CommonResponse.success(data={
        'total_upload': total_upload,
        'total_download': total_download,
        'data': increase_info_list
    })


@router.get('/torrents', response=CommonResponse[CommonPaginateSchema[TorrentInfoSchemaOut]],
            description='种子-列表')
def get_torrent_list(request, filters: PaginateQueryParamsSchemaIn = Query(...)):
    try:
        logger.info(filters.site_id)
        logger.info(filters.page * filters.limit)
        if filters.site_id:
            site = MySite.objects.get(id=filters.site_id)
            torrent_list = TorrentInfo.objects.filter(site=site).order_by('-updated_at')
        else:
            torrent_list = TorrentInfo.objects.all().order_by('-updated_at')
        page_list = Paginator(torrent_list, filters.limit)
        print(page_list.get_page(filters.page))
        data = {
            'items': list(page_list.get_page(filters.page).object_list),
            'per_page': filters.page,
            'total': page_list.count
        }
        logger.info(data)
        return CommonResponse.success(data=data)
    except Exception as e:
        msg = f'获取签到历史失败：{e}'
        logger.error(msg)
        logger.error(traceback.format_exc(3))
        return CommonResponse.error(msg=msg)


@router.post('/torrents/get', response=CommonResponse, description='获取种子')
def update_torrents(request):
    try:
        res = autopt.auto_get_torrents.delay()
        return CommonResponse.success(msg=f'抓取种子指令已发送，请注意查收推送消息！任务id：{res}')
    except Exception as e:
        logger.error(f'抓取种子失败：{e}')
        logger.error(traceback.format_exc(limit=3))
        return CommonResponse.error(msg=f'抓取种子失败：{e}')


@router.post('/search', response=CommonResponse[Optional[SearchResultSchema]], description='聚合搜索')
def search(request, params: SearchParamsSchema):
    try:
        print(params)
        from schedule.tasks import pool
        key = params.key
        site_list = params.site_list
        my_site_list = MySite.objects.filter(id__in=site_list, search_torrents=True) if len(
            site_list) > 0 else MySite.objects.filter(search_torrents=True)
        print(my_site_list)
        param_list = [(my_site, key) for my_site in my_site_list]
        # results = pool.starmap(pt_spider.search_torrents, params)
        search_result = {
            "results": [],
            "warning": [],
            "error": []
        }
        for result in pool.imap_unordered(lambda p: pt_spider.search_torrents(*p), param_list):
            if result.code == 0:
                my_site, response = result.data
                res = pt_spider.parse_search_result(my_site, response)
                if res.code == 0:
                    if len(res.data) > 0:
                        search_result['results'].extend(res.data)
                    else:
                        msg = f'{my_site.nickname} 无结果！'
                        logger.error(msg)
                        search_result['warning'].append(msg)
                else:
                    msg = f'{my_site.nickname} 搜索出错啦！{result.msg}'
                    logger.error(msg)
                    search_result['error'].append(msg)
            else:
                msg = f'{my_site.nickname} 搜索出错啦！{result.msg}'
                search_result['error'].append(msg)
            print(search_result)
        return CommonResponse.success(data=search_result)
    except Exception as e:
        msg = f'搜索功能出错了？{traceback.format_exc(3)}'
        logger.error(msg)
        return CommonResponse.error(msg=msg)


@router.get('/push_torrent', response=CommonResponse, description='聚合搜索')
def push_torrent(request, site: int, downloader_id: int, url: str, category: str):
    mysite = get_object_or_404(MySite, site=site)
    website = get_object_or_404(WebSite, id=site)
    client, downloader_category, _ = toolbox.get_downloader_instance(downloader_id)
    return toolbox.push_torrents_to_downloader(
        client=client,
        downloader_category=downloader_category,
        urls=url,
        category=category,
        cookie=mysite.cookie,
        upload_limit=website.limit_speed,
        download_limit=150,
        is_skip_checking=False,
        is_paused=False,
        use_auto_torrent_management=True,
    )


@router.get('/test/send_sms/{mobile}', response=CommonResponse, description='站点排序')
def send_sms_exec(request, mobile: str):
    try:
        res = autopt.auto_push_to_downloader.delay()
        logger.info(type(res))
        return CommonResponse.success(data=res.id)
    except Exception as e:
        logger.error(f'数据更新失败：{e}')
        logger.error(traceback.format_exc(limit=3))
        return CommonResponse.error(msg=f'数据更新失败：{e}')


@router.get('/push_to_server', response=CommonResponse, description='推送到服务器')
def push_to_server(request):
    start = time.time()
    res = toolbox.push_torrents_to_sever(10)
    logger.info(res)
    end = time.time()
    print(end - start)
    return CommonResponse.success(msg=f'{res}，耗时：{end - start}')
