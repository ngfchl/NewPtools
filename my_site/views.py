import logging
from typing import List

from django.shortcuts import get_object_or_404
from ninja import Router

from my_site.schema import *
from toolbox import views as toolbox
from toolbox.views import FileSizeConvert

# Create your views here.
logger = logging.getLogger('ptools')

router = Router(tags=['mysite'])


@router.get('/mysite', response=List[MySiteSchemaOut], description='我的站点-列表')
def get_mysite_list(request):
    return MySite.objects.order_by('id')


@router.get('/mysite/{int:mysite_id}', response=MySiteSchemaOut, description='我的站点-单个')
def get_mysite(request, mysite_id):
    return get_object_or_404(MySite, id=mysite_id)


@router.post('/mysite', description='我的站点-添加')
def add_mysite(request, my_site_params: MySiteSchemaIn):
    my_site = MySite.objects.create(**my_site_params.dict())
    return my_site


@router.put('/mysite/{int:mysite_id}', description='我的站点-更新')
def edit_mysite(request, mysite_id):
    return f'edit/{mysite_id}'


@router.delete('/mysite/{int:mysite_id}', description='我的站点-删除')
def remove_mysite(request, mysite_id):
    count = SiteStatus.objects.filter(id=mysite_id).delete()
    return f'remove/{count}'


@router.get('/status', response=List[SiteStatusSchemaOut], description='每日状态-列表')
def get_status_list(request):
    return SiteStatus.objects.order_by('id').select_related('site')


@router.get('/status/{int:status_id}', response=SiteStatusSchemaOut, description='每日状态-单个')
def get_status(request, status_id):
    return get_object_or_404(SiteStatus, id=status_id)


@router.get('/signin', response=List[SignInSchemaOut], description='每日签到-列表')
def get_signin_list(request):
    return SignIn.objects.order_by('id').select_related('site')


@router.get('/signin/{int:signin_id}', response=SignInSchemaOut, description='每日状态-单个')
def get_signin(request, signin_id):
    return get_object_or_404(SignIn, id=signin_id)


def today_data(self):
    """获取当日相较于前一日上传下载数据增长量"""
    today_site_status_list = SiteStatus.objects.filter(created_at__date=datetime.today())
    # yesterday_site_status_list = SiteStatus.objects.filter(
    #     created_at__day=datetime.today() - timedelta(days=1))
    increase_list = []
    total_upload = 0
    total_download = 0
    for site_state in today_site_status_list:
        my_site = site_state.site
        yesterday_site_status_list = SiteStatus.objects.filter(site=my_site)
        if len(yesterday_site_status_list) >= 2:
            yesterday_site_status = SiteStatus.objects.filter(site=my_site).order_by('-created_at')[1]
            uploaded_increase = site_state.uploaded - yesterday_site_status.uploaded
            downloaded_increase = site_state.downloaded - yesterday_site_status.downloaded
        else:
            uploaded_increase = site_state.uploaded
            downloaded_increase = site_state.downloaded
        if uploaded_increase + downloaded_increase <= 0:
            continue
        total_upload += uploaded_increase
        total_download += downloaded_increase
        increase_list.append(f'\n\n- 站点：{my_site.site.name}'
                             f'\n\t\t上传：{FileSizeConvert.parse_2_file_size(uploaded_increase)}'
                             f'\n\t\t下载：{FileSizeConvert.parse_2_file_size(downloaded_increase)}')
    # incremental = {
    #     '总上传': FileSizeConvert.parse_2_file_size(total_upload),
    #     '总下载': FileSizeConvert.parse_2_file_size(total_download),
    #     '说明': '数据均相较于本站今日之前最近的一条数据，可能并非昨日',
    #     '数据列表': increase_list,
    # }
    incremental = f'#### 总上传：{FileSizeConvert.parse_2_file_size(total_upload)}\n' \
                  f'#### 总下载：{FileSizeConvert.parse_2_file_size(total_download)}\n' \
                  f'> 说明: 数据均相较于本站今日之前最近的一条数据，可能并非昨日\n' \
                  f'#### 数据列表：{"".join(increase_list)}'
    logger.info(incremental)
    # todo
    # self.send_text(title='通知：今日数据', message=incremental)


@router.post('/import', response=SignInSchemaOut, description='PTPP备份导入')
def import_from_ptpp(request, data: ImportSchema):
    res = toolbox.parse_ptpp_cookies(data)
    if res.code == 0:
        cookies = res.data
        # logger.info(cookies)
    else:
        return res.to_dict()
    message_list = []
    for data in cookies:
        try:
            # logger.info(data)
            res = toolbox.get_uid_and_passkey(data)
            msg = res.msg
            logger.info(msg)
            if res.code == 0:
                message_list.append({
                    'msg': msg,
                    'tag': 'success'
                })
            else:
                message_list.append({
                    'msg': msg,
                    'tag': 'error'
                })
        except Exception as e:
            message = '{} 站点导入失败！{}  \n'.format(data.get('domain'), str(e))
            message_list.append({
                'msg': message,
                'tag': 'warning'
            })
            # raise
        logger.info(message_list)
    return message_list
