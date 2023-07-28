import json
from typing import Tuple
from urllib import parse

import requests

from toolbox import tools
from toolbox.schema import CommonResponse


class CookieCloudHelper:
    _ignore_cookies: list = ["CookieAutoDeleteBrowsingDataCleanup", "CookieAutoDeleteCleaningDiscarded"]

    def __init__(self, server, key, password):
        self._server = server
        self._key = key
        self._password = password

    @staticmethod
    def get_url_netloc(url: str) -> Tuple[str, str]:
        """
        获取URL的协议和域名部分
        """
        if not url:
            return "", ""
        if not url.startswith("http"):
            return "http", url
        addr = parse.urlparse(url)
        return addr.scheme, addr.netloc

    @staticmethod
    def get_url_domain(url: str) -> str:
        """
        获取URL的域名部分，只保留最后两级
        """
        if not url:
            return ""
        if tools.is_valid_ip_address(url):
            return ''
        _, netloc = CookieCloudHelper.get_url_netloc(url)
        if netloc:
            return ".".join(netloc.split(".")[-3:])
        return ""

    def download(self) -> CommonResponse:
        """
        从CookieCloud下载数据
        :return: Cookie数据、错误信息
        """
        if not self._server or not self._key or not self._password:
            return CommonResponse.error(msg="CookieCloud参数不正确")
        req_url = "%s/get/%s" % (self._server, self._key)
        ret = requests.post(url=req_url, json={"password": self._password}, headers={
            "content_type": "application/json"
        })
        if ret and ret.status_code == 200:
            result = ret.json()
            if not result:
                return CommonResponse.error(msg="未下载到数据!")
            if result.get("cookie_data"):
                contents = result.get("cookie_data")
            else:
                contents = result
            # 整理数据,使用domain域名的最后两级作为分组依据
            domain_groups = {}
            for site, cookies in contents.items():
                for cookie in cookies:
                    domain_key = CookieCloudHelper.get_url_domain(cookie.get("domain"))
                    if domain_key.startswith('.'):
                        continue
                    if not domain_groups.get(domain_key):
                        domain_groups[domain_key] = [cookie]
                    else:
                        domain_groups[domain_key].append(cookie)
            # 返回错误
            ret_cookies = {}
            # 索引器
            for domain, content_list in domain_groups.items():
                if not content_list:
                    continue
                # 只有cf的cookie过滤掉
                cloudflare_cookie = True
                for content in content_list:
                    if content["name"] != "cf_clearance":
                        cloudflare_cookie = False
                        break
                if cloudflare_cookie:
                    continue
                # 站点Cookie
                cookie_str = ";".join(
                    [f"{content.get('name')}={content.get('value')}"
                     for content in content_list
                     if content.get("name") and content.get("name") not in self._ignore_cookies]
                )
                ret_cookies[domain] = cookie_str
            print(json.dumps(ret_cookies, indent=2))
            return CommonResponse.success(data=ret_cookies)
        elif ret:
            return CommonResponse.error(msg=f"同步CookieCloud失败，错误码：{ret.status_code}")
        else:
            return CommonResponse.error(msg=f"CookieCloud请求失败，请检查服务器地址、用户KEY及加密密码是否正确")
