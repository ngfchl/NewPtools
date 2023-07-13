import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from jwt import exceptions

from toolbox.schema import CommonResponse


class AuthenticateMiddleware(MiddlewareMixin):

    def process_request(self, request):
        path: str = request.META.get('PATH_INFO')
        if path in [
            '/',
            '/api/config/login',
            '/api/docs',
            '/api/openapi.json',
        ] or path.startswith('/api/monkey') or path.startswith('/admin'):
            return None
        token = request.META.get("HTTP_AUTHORIZATION")
        if not token:
            return JsonResponse(data=CommonResponse.error(msg='未登录，等先登录后重试！').dict(), safe=False)
        salt = settings.SECRET_KEY
        try:
            res = jwt.decode(token.replace('Bearer ', ''), salt, algorithms=["HS256"])
            user = User.objects.get(id=res.get('id'), username=res.get('username'))
            request.user = user
        except exceptions.PyJWTError:
            return JsonResponse(data=CommonResponse.error(msg='认证失败，请重新登陆！').dict(), safe=False, status=403)
        except Exception as e:
            return JsonResponse(data=CommonResponse.error(msg='认证失败，请检查用户是否存在！').dict(), safe=False,
                                status=403)
        return None

    # def process_response(self, request, response):
    #     print("MD1里面的 process_response")
    #     return response
