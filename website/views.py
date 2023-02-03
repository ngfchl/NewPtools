from django.shortcuts import render
from ninja import Router

# Create your views here.
router = Router(tags=['website'])


@router.get('/index')
def websites(request):
    return 'website'


@router.get('/get/{int:website_id}')
def get_website(request, website_id):
    return f'get/{website_id}'


@router.post('/add')
def add_website(request):
    return 'add'


@router.put('/edit/{int:website_id}')
def edit_website(request, website_id):
    return f'edit/{website_id}'


@router.delete('/remove/{int:website_id}')
def remove_website(request, website_id):
    return f'remove/{website_id}'
