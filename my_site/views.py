import logging
import traceback
from typing import List, Optional

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from ninja import Router

from my_site import tasks as autopt
from my_site.schema import *
from spider.views import PtSpider
from toolbox import views as toolbox
from toolbox.schema import CommonResponse
from my_site.schema import MySiteDoSchemaIn
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
        return CommonResponse.success(data=MySite.objects.get(id=mysite_id))
    except Exception as e:
        print(e)
        return CommonResponse.error(msg='没有这个站点的信息哦')


@router.post('/mysite', response=CommonResponse, description='我的站点-添加')
def add_mysite(request, my_site_params: MySiteSchemaEdit):
    try:
        logger.info(f'开始处理：{my_site_params.nickname}')
        logger.info(my_site_params)
        my_site_params.id = None
        my_site = MySite.objects.create(**my_site_params.dict())
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
async def edit_mysite(request, my_site_params: MySiteSchemaEdit):
    try:
        logger.info(f'开始更新：{my_site_params.nickname}')
        my_site_res = await MySite.objects.filter(id=my_site_params.id).aupdate(**my_site_params.dict())
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
def remove_mysite(request, mysite_id):
    try:
        logger.info(f'开始删除站点：{mysite_id}')
        my_site_res = MySite.objects.get(id=mysite_id).delete()
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
def get_status_list(request, my_site: MySiteDoSchemaIn):
    return pt_spider.send_status_request(MySite.objects.get(id=my_site.site_id))


@router.get('/status/newest', response=CommonResponse[List[StatusSchema]], description='最新状态-列表')
def get_newest_status_list(request):
    my_site_list = MySite.objects.all()
    id_list = [SiteStatus.objects.filter(site=my_site.id).order_by('created_at').first().id for my_site in
               my_site_list if SiteStatus.objects.filter(site=my_site.id).order_by('created_at').first()]
    status_list = SiteStatus.objects.filter(id__in=id_list)
    my_site_id_list = [my_site.id for my_site in my_site_list]
    site_id_list = [my_site.site for my_site in my_site_list]
    site_list = WebSite.objects.all()
    sign_list = SignIn.objects.filter(id__in=my_site_id_list)
    level_list = UserLevelRule.objects.filter(site_id__in=site_id_list)
    info_list = []
    for my_site in my_site_list:
        status = status_list.filter(site=my_site).first()
        sign = sign_list.filter(site=my_site, created_at__date=datetime.today().date()).first()
        level = level_list.filter(site_id=my_site.site, level=status.my_level).first() if status else None
        next_level = level_list.filter(site_id=my_site.site, level_id=level.id + 1).first() if level else None
        # if not status:
        #     status = SiteStatus.objects.create(site=my_site)
        info = {
            'my_site': my_site,
            'site': site_list.filter(id=my_site.site).first(),
            'status': status if status else SiteStatus(site=my_site),
            'sign': sign,
            'level': level,
            'next_level': next_level
        }
        # print(info)
        info_list.append(info)
    return CommonResponse.success(data=info_list)


@router.get('/status/{int:status_id}', response=SiteStatusSchemaOut, description='每日状态-单个')
def get_status(request, status_id):
    return get_object_or_404(SiteStatus, id=status_id)


@router.get('/signin', response=List[SignInSchemaOut], description='每日签到-列表')
def get_signin_list(request):
    return SignIn.objects.order_by('id').select_related('site')


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
def sign_in_api(request, site_list: List[int] = []):
    try:
        res = autopt.auto_sign_in.delay(site_list)
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


@router.get('/status/chart/{site_id}', response=CommonResponse, description='站点数据展示')
def site_data_api(request, site_id: int):
    """站点数据(柱状图)"""
    # my_site_id = request.GET.get('id')
    logger.info(f'ID值：{type(site_id)}')
    if int(site_id) == 0:
        my_site_list = MySite.objects.all()
        diff_list = []
        # 提取日期
        date_list = set([
            status.created_at.date().strftime('%Y-%m-%d') for status in SiteStatus.objects.all()
        ])
        date_list = list(date_list)
        date_list.sort()
        # logger.info(f'日期列表：{date_list}')
        logger.info(f'日期数量：{len(date_list)}')

        for my_site in my_site_list:
            # 每个站点获取自己站点的所有信息
            site_status_list = my_site.sitestatus_set.order_by('created_at').all()
            # logger.info(f'站点数据条数：{len(site_status_list)}')
            info_list = [
                {
                    'uploaded': site_info.uploaded,
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
            diff_info_list = {
                info['date']: info['uploaded'] - info_list[index - 1]['uploaded'] if
                info['uploaded'] - info_list[index - 1]['uploaded'] > 0 else 0 for
                (index, info) in enumerate(info_list) if 0 < index < len(info_list)

            }
            # logger.info(f'处理完后站点数据条数：{len(info_list)}')
            for date in date_list:
                if not diff_info_list.get(date):
                    diff_info_list[date] = 0
            # logger.info(diff_info_list)
            # logger.info(len(diff_info_list))
            diff_info_list = sorted(diff_info_list.items(), key=lambda x: x[0])
            diff_list.append({
                'name': my_site.nickname,
                'type': 'bar',
                'large': 'true',
                'stack': 'increment',
                'data': [value[1] if value[1] > 0 else 0 for value in diff_info_list]
            })
        return CommonResponse.success(
            data={'date_list': date_list, 'diff': diff_list}
        )

    logger.info(f'前端传来的站点ID：{site_id}')
    my_site = MySite.objects.filter(id=site_id).first()
    if not my_site:
        return CommonResponse.error(
            msg='访问出错咯！没有这个站点...'
        )
    site_info_list = my_site.sitestatus_set.order_by('created_at').all()
    if len(site_info_list) <= 0:
        return CommonResponse.error(
            msg='你还没有获取过这个站点的数据...'
        )
    # logger.info(site_info_list)
    site_status_list = []
    site = get_object_or_404(WebSite, id=my_site.site)
    my_site_info = {
        'id': my_site.id,
        'name': site.name,
        'icon': site.logo,
        'url': site.url,
        'class': site_info_list.first().my_level,
        'last_active': datetime.strftime(site_info_list.first().updated_at, '%Y/%m/%d %H:%M:%S'),
    }
    for site_info in site_info_list:
        my_site_status = {
            'uploaded': site_info.uploaded,
            'downloaded': site_info.downloaded,
            'ratio': 0 if site_info.ratio == float('inf') else site_info.ratio,
            'seedingSize': site_info.seed_vol,
            'sp': site_info.my_sp,
            'sp_hour': site_info.sp_hour,
            'bonus': site_info.my_bonus,
            'seeding': site_info.seed,
            'leeching': site_info.leech,
            'invitation': site_info.invitation,
            'info_date': site_info.created_at.date()
        }
        site_status_list.append(my_site_status)
    logger.info(site)
    # logger.info(site_status_list)
    return CommonResponse.success(
        data={'site': my_site_info, 'site_status_list': site_status_list}
    )


@router.post('/status/do', response=CommonResponse, description='刷新站点数据')
def update_site_api(request, site_list: List[int] = []):
    try:
        res = autopt.auto_get_status.delay(site_list)
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


@router.get('/sign/show/{site_id}/{sort_id}', response=CommonResponse, description='站点排序')
def site_sort_api(request, site_id: int, sort_id: int):
    try:
        my_site = MySite.objects.filter(id=site_id).first()
        my_site.sort_id += int(sort_id)

        if int(my_site.sort_id) <= 0:
            my_site.sort_id = 0
            my_site.save()
            return CommonResponse.success(msg='排序已经最靠前啦，不要再点了！')
        my_site.save()
        return CommonResponse.success(msg='排序成功！')
    except Exception as e:
        logger.error(f'数据更新失败：{e}')
        logger.error(traceback.format_exc(limit=3))
        return CommonResponse.error(msg=f'数据更新失败：{e}')


@router.get('/torrents', response=CommonResponse[List[TorrentInfoSchemaOut]], description='获取种子')
def torrents(request):
    return CommonResponse.success(data=list(TorrentInfo.objects.all()))


@router.post('/torrents/get/', response=CommonResponse, description='获取种子')
def update_torrents(request, site_list: List[int] = []):
    try:
        res = autopt.auto_update_torrents.delay(site_list)
        return CommonResponse.success(msg=f'抓取种子指令已发送，请注意查收推送消息！任务id：{res}')
    except Exception as e:
        logger.error(f'抓取种子失败：{e}')
        logger.error(traceback.format_exc(limit=3))
        return CommonResponse.error(msg=f'抓取种子失败：{e}')


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
