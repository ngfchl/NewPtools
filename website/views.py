import logging
from typing import List

from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.responses import codes_4xx

from monkey.schema import CommonMessage
from my_site.models import MySite
from website.schema import *

# Create your views here.

logger = logging.getLogger('ptools')

router = Router(tags=['website'])


@router.get('/website', response=List[WebSiteSchemaOut])
def get_website_list(request):
    website_list = WebSite.objects.order_by('id')
    return website_list


@router.get('/website/{int:website_id}', response=WebSiteSchemaOut)
def get_website(request, website_id):
    return get_object_or_404(WebSite, id=website_id)


@router.post('/website')
def add_website(request):
    return 'add'


@router.put('/website/{int:website_id}')
def edit_website(request, website_id):
    return f'edit/{website_id}'


@router.delete('/website/{int:website_id}')
def remove_website(request, website_id):
    count = WebSite.objects.filter(id=website_id).delete()
    return f'remove/{count}'


@router.get('/user_level_rule', response=List[UserLevelRuleSchemaOut])
def get_rule_list(request):
    rule_list = UserLevelRule.objects.order_by('id').select_related('site')
    return rule_list


@router.get('/user_level_rule/{int:rule_id}', response=UserLevelRuleSchemaOut)
def get_rule(request, rule_id):
    return get_object_or_404(UserLevelRule, id=rule_id)


@router.post('/user_level_rule')
def add_rule(request):
    return 'add'


@router.put('/user_level_rule/{int:rule_id}')
def edit_rule(request, rule_id):
    return f'edit/{rule_id}'


@router.delete('/user_level_rule/{int:rule_id}')
def remove_rule(request, rule_id):
    count = UserLevelRule.objects.filter(id=rule_id).delete()
    return f'remove/{count}'


@router.get('/trackers', response={200: List[TrackerSchema], codes_4xx: CommonMessage},
            description='下载器列表')
def get_trackers(request):
    """从已支持的站点获取tracker关键字列表"""
    tracker_list = WebSite.objects.all()
    return tracker_list


@router.get('/website/list/{site_id}', response=List[WebSiteSchemaOut])
def get_site_list(request, site_id: int):
    logger.info(site_id)
    if int(site_id) == 0:
        return [site for site in WebSite.objects.all().order_by('id') if
                MySite.objects.filter(site=site.get('id')).count() < 1]
    else:
        return WebSite.objects.filter(id=site_id).order_by('id')
