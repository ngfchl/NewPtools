from typing import List

from django.shortcuts import get_object_or_404
from ninja import Router

from my_site.schema import *

# Create your views here.

router = Router(tags=['mysite'])


@router.get('/mysite', response=List[MySiteSchemaOut], description='我的站点-列表')
def get_mysite_list(request):
    return MySite.objects.order_by('id').select_related('site')


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
