from typing import List

from ninja import Router

from website.schema import *

# Create your views here.
router = Router(tags=['website'])


@router.get('/website', response=List[WebSiteSchemaOut])
def websites(request):
    website_list = WebSite.objects.order_by('id')
    return website_list


@router.get('/website/{int:website_id}', response=WebSiteSchemaOut)
def get_website(request, website_id):
    website_list = WebSite.objects.filter(id=website_id)
    if len(website_list) == 1:
        return website_list.first()
    return None


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
def user_level_rule_list(request):
    rule_list = UserLevelRule.objects.order_by('id').select_related('site')
    return rule_list


@router.get('/user_level_rule/{int:rule_id}', response=UserLevelRuleSchemaOut)
def get_user_level_rule(request, rule_id):
    rule_list = UserLevelRule.objects.filter(id=rule_id)
    if len(rule_list) == 1:
        return rule_list.first()
    return None


@router.post('/user_level_rule')
def add_user_level_rule(request):
    return 'add'


@router.put('/user_level_rule/{int:rule_id}')
def edit_user_level_rule(request, rule_id):
    return f'edit/{rule_id}'


@router.delete('/user_level_rule/{int:rule_id}')
def remove_user_level_rule(request, rule_id):
    count = UserLevelRule.objects.filter(id=rule_id).delete()
    return f'remove/{count}'
