"""auxiliary URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from http.client import HTTPException

from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
from ninja import NinjaAPI
from ninja.errors import ValidationError

from monkey.views import router as monkey_router
from my_site.views import router as mysite_router
from website.views import router as website_router

api_v1 = NinjaAPI(version='1.0.0')
api_v1.add_router('/website', website_router)
api_v1.add_router('/mysite', mysite_router)
api_v1.add_router('/monkey', monkey_router)


@api_v1.exception_handler(ValidationError)
def validation_errors(request, exc):
    return HttpResponse("Invalid input", status=422)


@api_v1.exception_handler(HTTPException)
async def http_exception_v1(request, exc: HTTPException):
    """
    # 改变成字符串响应
    :param request: 不可省略
    :param exc: HTTPException
    :return:
    """
    return HttpResponse(str(exc.detail), status_code=400)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api_v1.urls),
]
