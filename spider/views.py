import logging
import random
import re
import ssl
import threading
import time
import traceback
from datetime import datetime

import cloudscraper
import requests
import toml
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from lxml import etree
from requests import ReadTimeout, Response
from urllib3.exceptions import NewConnectionError, ConnectTimeoutError

from auxiliary.base import TorrentBaseInfo
from my_site.models import MySite, SignIn, SiteStatus, TorrentInfo
from toolbox import views as toolbox
from toolbox.schema import CommonResponse
from toolbox.views import FileSizeConvert
from website.models import WebSite

# Create your views here.

logger = logging.getLogger('ptools')
lock = threading.Lock()


class PtSpider:
    """爬虫"""

    def __init__(self, browser='chrome', platform='darwin', *args, **kwargs):
        self.browser = browser
        self.platform = platform

    def get_scraper(self, delay=0):
        return cloudscraper.create_scraper(browser={
            'browser': self.browser,
            'platform': self.platform,
            'mobile': False
        }, delay=delay)

    def send_request(self,
                     my_site: MySite,
                     url: str,
                     method: str = 'get',
                     data: dict = None,
                     params: dict = None,
                     json: dict = None,
                     timeout: int = 45,
                     delay: int = 15,
                     header: dict = {},
                     proxies: dict = None):
        scraper = self.get_scraper(delay=delay)
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        _RESTRICTED_SERVER_CIPHERS = 'ALL'
        ssl_context.set_ciphers(_RESTRICTED_SERVER_CIPHERS)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        scraper.ssl_context = ssl_context
        headers = {
            'User-Agent': my_site.user_agent,
        }
        headers.update(header)
        return scraper.request(
            url=url,
            method=method,
            headers=headers,
            cookies=toolbox.cookie2dict(my_site.cookie),
            data=data,
            timeout=timeout,
            proxies=proxies,
            params=params,
            json=json,
        )

    @staticmethod
    def parse(site, response, rules):
        if site.url in [
            'https://ourbits.club/',
            'https://piggo.me/',
        ]:
            return etree.HTML(response.text).xpath(rules)
        else:
            return etree.HTML(response.content).xpath(rules)

    def sign_in_52pt(self, my_site: MySite):
        site = get_object_or_404(WebSite, my_site.site)
        url = site.url + site.page_sign_in.lstrip('/')
        result = self.send_request(my_site=my_site, url=url, )
        # sign_str = self.parse(result, '//font[contains(text(),"签过到")]/text()')
        sign_str = etree.HTML(result.text).xpath('//font[contains(text(),"签过到")]/text()')
        logger.info(sign_str)
        if len(sign_str) >= 1:
            # msg = self.parse(result, '//font[contains(text(),"签过到")]/text()')
            return CommonResponse.success(msg='您已成功签到，请勿重复操作！{}'.format(sign_str))
        # if len(sign_str) >= 1:
        #     return CommonResponse.success(msg='52PT 签到太复杂不支持，访问网站保持活跃成功！')
        questionid = self.parse(site, result, '//input[contains(@name, "questionid")]/@value')
        choices = self.parse(site, result, '//input[contains(@name, "choice[]")]/@value')
        # for choice in choices:
        #     logger.info(choice)
        data = {
            'questionid': questionid,
            'choice[]': choices[random.randint(0, len(choices) - 1)],
            'usercomment': '十步杀一人，千里不流行！',
            'wantskip': '不会'
        }
        logger.info(data)
        sign_res = self.send_request(
            my_site=my_site, url=site.url + site.page_sign_in.lstrip('/'), method='post', data=data
        )
        logger.info(sign_res.text)
        # sign_str = etree.HTML(sign_res.text.encode('utf-8-sig')).xpath
        sign_str = self.parse(site, sign_res, '//font[contains(text(),"点魔力值(连续")]/text()')
        if len(sign_str) < 1:
            return CommonResponse.error(msg='签到失败!')
        else:
            # msg = self.parse(sign_res, '//font[contains(text(),"签过到")]/text()')
            return CommonResponse.success(msg=f'签到成功！{"".join(sign_str)}')

    def sign_in_hdupt(self, my_site: MySite):
        site = get_object_or_404(WebSite, my_site.site)
        url = site.url + site.page_control_panel.lstrip('/')
        result = self.send_request(
            my_site=my_site,
            url=url,
        )
        sign_str = self.parse(site, result, '//span[@id="qiandao"]')
        logger.info(sign_str)
        if len(sign_str) < 1:
            return CommonResponse.success(msg=site.name + '已签到，请勿重复操作！！')
        sign_res = self.send_request(
            my_site=my_site,
            url=site.url + site.page_sign_in.lstrip('/'),
            method='post'
        ).text
        logger.info(f'好多油签到反馈：{sign_res}')
        try:
            sign_res = toolbox.get_decimals(sign_res)
            if int(sign_res) > 0:
                return CommonResponse.success(
                    msg='你还需要继续努力哦！此次签到，你获得了魔力奖励：{}'.format(sign_res)
                )
        except Exception as e:
            logger.info(traceback.format_exc(3))
            return CommonResponse.error(
                msg=f'签到失败！{sign_res}: {e}'
            )

    def sign_in_hd4fans(self, my_site: MySite):
        site = get_object_or_404(WebSite, my_site.site)
        url = site.url + site.page_control_panel.lstrip('/')
        result = self.send_request(
            my_site=my_site,
            url=url,
        )
        sign_str = self.parse(site, result, '//span[@id="checkin"]/a')
        logger.info(sign_str)
        if len(sign_str) < 1:
            return CommonResponse.success(msg=site.name + '已签到，请勿重复操作！！')
        sign_res = self.send_request(
            my_site=my_site,
            url=site.url + site.page_sign_in.lstrip('/'),
            method='post',
            params={
                'action': 'checkin'
            }
        )
        msg = '你还需要继续努力哦！此次签到，你获得了魔力奖励：{}'.format(sign_res.text.encode('utf8'))
        logger.info(msg)
        return CommonResponse.success(
            msg=msg
        )

    def sign_in_hdc(self, my_site: MySite):
        site = get_object_or_404(WebSite, my_site.site)
        url = site.url + site.page_control_panel.lstrip('/')
        # result = self.send_request(
        #     my_site=my_site,
        #     url=url,
        # )
        result = requests.get(url=url, verify=False,
                              cookies=toolbox.cookie2dict(my_site.cookie),
                              headers={
                                  'user-agent': my_site.user_agent
                              })
        logger.info(f'签到检测页面：{result.text}')
        sign_str = self.parse(site, result, '//a[text()="已签到"]')
        logger.info('{}签到检测'.format(site.name, sign_str))
        logger.info(f'{result.cookies.get_dict()}')

        if len(sign_str) >= 1:
            return CommonResponse.success(msg=site.name + '已签到，请勿重复操作！！')
        csrf = ''.join(self.parse(site, result, '//meta[@name="x-csrf"]/@content'))
        logger.info('CSRF字符串：{}'.format(csrf))
        # sign_res = self.send_request(
        #     my_site=my_site,
        #     url=site.url + site.page_sign_in,
        #     method=site.sign_in_method,
        #     data={
        #         'csrf': csrf
        #     }
        # )
        cookies = toolbox.cookie2dict(my_site.cookie)
        cookies.update(result.cookies.get_dict())
        logger.info(cookies)
        sign_res = requests.request(url=site.url + site.page_sign_in, verify=False, method='post', cookies=cookies,
                                    headers={'user-agent': my_site.user_agent}, data={'csrf': csrf})
        logger.info(sign_res.text)
        res_json = sign_res.json()
        logger.info(sign_res.cookies)
        logger.info('签到返回结果：{}'.format(res_json))
        if res_json.get('state') == 'success':
            if len(sign_res.cookies) >= 1:
                logger.info(f'我的COOKIE：{my_site.cookie}')
                logger.info(f'新的COOKIE字典：{sign_res.cookies.items()}')
                cookie = ''
                for k, v in sign_res.cookies.items():
                    cookie += f'{k}={v};'
                logger.info(f'新的COOKIE：{sign_res.cookies.items()}')
                my_site.cookie = cookie
                my_site.save()
            msg = f"签到成功，您已连续签到{res_json.get('signindays')}天，本次增加魔力:{res_json.get('integral')}。"
            logger.info(msg)
            return CommonResponse.success(msg=msg)
        else:
            msg = res_json.get('msg')
            logger.info(msg)
            return CommonResponse.error(msg=msg)

    def sign_in_u2(self, my_site: MySite):
        site = get_object_or_404(WebSite, my_site.site)
        url = site.url + site.page_sign_in.lstrip('/')
        result = self.send_request(my_site=my_site, url=url, )
        sign_str = ''.join(self.parse(site, result, '//a[@href="showup.php"]/text()'))
        logger.info(site.name + sign_str)
        if '已签到' in sign_str or '已簽到' in sign_str:
            # if '已签到' in converter.convert(sign_str):
            return CommonResponse.success(msg=site.name + '已签到，请勿重复操作！！')
        req = self.parse(site, result, '//form//td/input[@name="req"]/@value')
        hash_str = self.parse(site, result, '//form//td/input[@name="hash"]/@value')
        form = self.parse(site, result, '//form//td/input[@name="form"]/@value')
        submit_name = self.parse(site, result, '//form//td/input[@type="submit"]/@name')
        submit_value = self.parse(site, result, '//form//td/input[@type="submit"]/@value')
        message = '天空飘来五个字儿,幼儿园里没有事儿'
        logger.info(submit_name)
        logger.info(submit_value)
        param = []
        for name, value in zip(submit_name, submit_value):
            param.append({name: value})
        data = {
            'req': req[0],
            'hash': hash_str[0],
            'form': form[0],
            'message': message,
        }
        data.update(param[random.randint(0, 3)])
        logger.info(data)
        response = self.send_request(
            my_site,
            url=site.url + site.page_sign_in.lstrip('/') + '?action=show',
            method='post',
            data=data,
        )
        logger.info(response.content.decode('utf8'))
        if "window.location.href = 'showup.php';" in response.content.decode('utf8'):
            result = self.send_request(my_site=my_site, url=url, )
            title = self.parse(site, result, '//h2[contains(text(),"签到区")]/following-sibling::table//h3/text()')
            content = self.parse(
                site, result,
                '//td/span[@class="nowrap"]/a[contains(@href,"userdetails.php?id={}")]'
                '/parent::span/following-sibling::b[2]/text()'.format(my_site.user_id)
            )
            msg = '{}，奖励UCoin{}'.format(''.join(title), ''.join(content))
            logger.info(msg)
            return CommonResponse.success(msg=msg)
        else:
            logger.info('签到失败！')
            return CommonResponse.error(msg='签到失败！')

    def sign_in_opencd(self, my_site: MySite):
        """皇后签到"""
        site = get_object_or_404(WebSite, my_site.site)
        check_url = site.url + site.page_user
        res_check = self.send_request(
            my_site=my_site,
            url=check_url)
        href_sign_in = self.parse(site, res_check, '//a[@href="/plugin_sign-in.php?cmd=show-log"]')
        if len(href_sign_in) >= 1:
            return CommonResponse.success(data={'state': 'false'})
        url = site.url + site.page_sign_in.lstrip('/')
        logger.info('# 开启验证码！')
        res = self.send_request(my_site=my_site, method='get', url=url)
        logger.info(res.text.encode('utf-8-sig'))
        img_src = ''.join(self.parse(site, res, '//form[@id="frmSignin"]//img/@src'))
        img_get_url = site.url + img_src
        times = 0
        # imagestring = ''
        ocr_result = None
        while times <= 5:
            ocr_result = toolbox.baidu_ocr_captcha(img_get_url)
            if ocr_result.code == 0:
                imagestring = ocr_result.data
                logger.info('验证码长度：{}'.format(len(imagestring)))
                if len(imagestring) == 6:
                    break
            times += 1
            time.sleep(1)
        if ocr_result.code != 0:
            return ocr_result
        data = {
            'imagehash': ''.join(self.parse(site, res, '//form[@id="frmSignin"]//input[@name="imagehash"]/@value')),
            'imagestring': imagestring
        }
        logger.info('请求参数：{}'.format(data))
        result = self.send_request(
            my_site=my_site,
            method='post',
            url=site.url + 'plugin_sign-in.php?cmd=signin', data=data)
        logger.info('皇后签到返回值：{}  \n'.format(result.text.encode('utf-8-sig')))
        return CommonResponse.success(data=result.json())

    def sign_in_hdsky(self, my_site: MySite):
        """HDSKY签到"""
        site = get_object_or_404(WebSite, my_site.site)
        url = site.url + site.page_sign_in.lstrip('/')
        # sky无需验证码时使用本方案
        # if not captcha:
        #     result = self.send_request(
        #         my_site=my_site,
        #         method='post',
        #         url=url
        #     )
        # sky无验证码方案结束
        # 获取img hash
        logger.info('# 开启验证码！')
        res = self.send_request(
            my_site=my_site,
            method='post',
            url=site.url + 'image_code_ajax.php',
            data={
                'action': 'new'
            }).json()
        # img url
        img_get_url = site.url + 'image.php?action=regimage&imagehash=' + res.get('code')
        logger.info('验证码图片链接：' + img_get_url)
        # 获取OCR识别结果
        # imagestring = toolbox.baidu_ocr_captcha(img_url=img_get_url)
        times = 0
        # imagestring = ''
        ocr_result = None
        while times <= 5:
            # ocr_result = toolbox.baidu_ocr_captcha(img_get_url)
            ocr_result = toolbox.baidu_ocr_captcha(img_get_url)
            if ocr_result.code == 0:
                imagestring = ocr_result.data
                logger.info('验证码长度：{}'.format(len(imagestring)))
                if len(imagestring) == 6:
                    break
            times += 1
            time.sleep(1)
        if ocr_result.code != 0:
            return ocr_result
        # 组装请求参数
        data = {
            'action': 'showup',
            'imagehash': res.get('code'),
            'imagestring': imagestring
        }
        # logger.info('请求参数', data)
        result = self.send_request(
            my_site=my_site,
            method='post',
            url=url, data=data)
        logger.info('天空返回值：{}\n'.format(result.text))
        return CommonResponse.success(data=result.json())

    def sign_in_ttg(self, my_site: MySite):
        """
        TTG签到
        :param my_site:
        :return:
        """
        site = get_object_or_404(WebSite, my_site.site)
        url = site.url + site.page_user.format(my_site.user_id)
        logger.info(site.name + '个人主页：' + url)
        try:
            res = self.send_request(my_site=my_site, url=url)
            # logger.info(res.text.encode('utf8'))
            # html = self.parse(site,res, '//script/text()')
            html = etree.HTML(res.text).xpath('//script/text()')
            # logger.info(html)
            text = ''.join(html).replace('\n', '').replace(' ', '')
            logger.info(text)
            signed_timestamp = toolbox.get_decimals(re.search("signed_timestamp:\"\d{10}", text).group())

            signed_token = re.search('[a-zA-Z0-9]{32}', text).group()
            params = {
                'signed_timestamp': signed_timestamp,
                'signed_token': signed_token
            }
            logger.info('signed_timestamp:' + signed_timestamp)
            logger.info('signed_token:' + signed_token)

            resp = self.send_request(
                my_site,
                site.url + site.page_sign_in,
                method='post',
                data=params)
            logger.info(resp.text)
            return CommonResponse.success(msg=resp.content.decode('utf8'))
        except Exception as e:
            # 打印异常详细信息
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg='{} 签到失败: {}'.format(site.name, e))

    @staticmethod
    def get_user_torrent(html, rule):
        res_list = html.xpath(rule)
        logger.info('content' + res_list)
        # logger.info('res_list:', len(res_list))
        return '0' if len(res_list) == 0 else res_list[0]

    def do_sign_in(self, pool, queryset: QuerySet[MySite]):
        message_list = []
        if datetime.now().hour < 9:
            # U2/52PT 每天九点前不签到
            queryset = [my_site for my_site in queryset if WebSite.objects.get(my_site.site).url not in [
                'https://u2.dmhy.org/',
                # 'https://52pt.site/'
            ] and my_site.signin_set.filter(created_at__date__gte=datetime.today()).count() <= 0
                        and my_site.cookie]
            message = '站点：`U2` 早上九点之前不执行签到任务哦！ \n\n'
            logger.info(message)
            message_list.append(message)
        else:
            queryset = [my_site for my_site in queryset if my_site.cookie and
                        my_site.signin_set.filter(created_at__date__gte=datetime.today(),
                                                  sign_in_today=True).count() <= 0]
        logger.info(len(queryset))
        if len(queryset) <= 0:
            message_list = ['已全部签到或无需签到！ \n\n']
            logger.info(message_list)
            return 0
        # results = pool.map(pt_spider.sign_in, site_list)
        with lock:
            results = pool.map(self.sign_in, queryset)
            for my_site, result in zip(queryset, results):
                # logger.info('自动签到：{}, {}'.format(my_site, result))
                # if result.code == 0:
                #     msg = f'{my_site.nickname} 签到成功！{result.msg} \n\n'
                #     logger.info(msg)
                #     message_list.append(msg)
                # else:
                #     message = f'{my_site.nickname}签到失败：{result.msg} \n\n'
                #     message_list.insert(0, message)
                #     logger.error(message)
                message_list.append({my_site.nickname: result.to_dict()})
            logger.info(message_list)
            return message_list

    # @transaction.atomic
    def sign_in(self, my_site: MySite):
        """签到"""
        site = get_object_or_404(WebSite, my_site.site)
        logger.info(site.name + '开始签到')
        signin_today = my_site.signin_set.filter(created_at__date__gte=datetime.today()).first()
        # 如果已有签到记录
        if signin_today:
            if signin_today.sign_in_today is True:
                return CommonResponse.success(msg=f'已签到，请勿重复签到！')
        else:
            signin_today = SignIn(site=my_site)
        url = site.url + site.page_sign_in.lstrip('/')
        logger.info('签到链接：' + url)
        try:
            # with lock:
            if '52pt' in site.url or 'chdbits' in site.url:
                result = self.sign_in_52pt(my_site)
                if result.code == 0:
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = result.msg
                    signin_today.save()
                return result
            if 'hd4fans' in site.url:
                result = self.sign_in_hd4fans(my_site)
                if result.code == 0:
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = result.msg
                    signin_today.save()
                return result
            if 'hdupt.com' in site.url:
                result = self.sign_in_hdupt(my_site)
                if result.code == 0:
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = result.msg
                    signin_today.save()
                return result
            if 'hdchina' in site.url:
                result = self.sign_in_hdc(my_site)
                if result.code == 0:
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = result.msg
                    signin_today.save()
                return result
            if 'totheglory' in site.url:
                result = self.sign_in_ttg(my_site)
                if result.code == 0:
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = result.msg
                    signin_today.save()
                return result
            if 'u2.dmhy.org' in site.url:
                result = self.sign_in_u2(my_site)
                if result.code == 0:
                    logger.info(result.data)
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = result.msg
                    signin_today.save()
                return result
            if 'hdsky.me' in site.url:
                result = self.sign_in_hdsky(my_site=my_site)
                if result.code == 0:
                    res_json = result.data
                    if res_json.get('success'):
                        # 签到成功
                        bonus = res_json.get('message')
                        days = (int(bonus) - 10) / 2 + 1
                        signin_today.sign_in_today = True
                        message = f'成功,已连续签到{days}天,魔力值加{bonus},明日继续签到可获取{bonus + 2}魔力值！'
                        signin_today.sign_in_info = message
                        signin_today.save()
                        return CommonResponse.success(msg=message)
                    elif res_json.get('message') == 'date_unmatch':
                        # 重复签到
                        message = '您今天已经在其他地方签到了哦！'
                        signin_today.sign_in_today = True
                        signin_today.sign_in_info = message
                        signin_today.save()
                        return CommonResponse.success(
                            msg=message
                        )
                    elif res_json.get('message') == 'invalid_imagehash':
                        # 验证码错误
                        return CommonResponse.error(msg='验证码错误')
                    else:
                        # 签到失败
                        return CommonResponse.error(msg='签到失败')
                else:
                    # 签到失败
                    return result
            if 'open.cd' in site.url:
                result = self.sign_in_opencd(my_site=my_site)
                logger.info('皇后签到结果：{}'.format(result.to_dict()))
                if result.code == 0:
                    res_json = result.data
                    if res_json.get('state') == 'success':
                        signin_today.sign_in_today = True
                        # data = res_json.get('msg')
                        message = "签到成功，您已连续签到{}天，本次增加魔力:{}。".format(
                            res_json.get('signindays'),
                            res_json.get('integral'),
                        )
                        signin_today.sign_in_info = message
                        signin_today.save()
                        return CommonResponse.success(msg=message)
                    elif res_json.get('state') == 'false' and len(res_json) <= 1:
                        # 重复签到
                        message = '您今天已经在其他地方签到了哦！'
                        signin_today.sign_in_today = True
                        signin_today.sign_in_info = message
                        signin_today.save()
                        return CommonResponse.success(msg=message)
                    # elif res_json.get('state') == 'invalid_imagehash':
                    #     # 验证码错误
                    #     return CommonResponse.error(
                    #         status=StatusCodeEnum.IMAGE_CODE_ERR,
                    #     )
                    else:
                        # 签到失败
                        return CommonResponse.error(msg=res_json.get('msg'))
                else:
                    # 签到失败
                    return result
            if 'hdarea.co' in site.url:
                res = self.send_request(my_site=my_site,
                                        method='post',
                                        url=url,
                                        data={'action': 'sign_in'}, )
                if res.status_code == 200:
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = res.text
                    signin_today.save()
                    return CommonResponse.success(msg=res.text)
                elif res.status_code == 503:
                    return CommonResponse.error(msg='网站访问失败！')
                else:
                    return CommonResponse.error(msg='签到失败！')
            if 'hares.top' in site.url:
                res = self.send_request(my_site=my_site, method='post', url=url, header={"accept": "application/json"})
                logger.info(res.text)
                code = res.json().get('code')
                # logger.info('白兔返回码：'+ type(code))
                if int(code) == 0:
                    """
                    "datas": {
                      "id": 2273,
                      "uid": 2577,
                      "added": "2022-08-03 12:52:36",
                      "points": "200",
                      "total_points": 5435,
                      "days": 42,
                      "total_days": 123,
                      "added_time": "12:52:36",
                      "is_updated": 1
                    }
                    """
                    message_template = '签到成功！奖励奶糖{},奶糖总奖励是{},您已连续签到{}天，签到总天数{}天！'
                    data = res.json().get('datas')
                    message = message_template.format(data.get('points'),
                                                      data.get('total_points'),
                                                      data.get('days'),
                                                      data.get('total_days'))
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = message
                    signin_today.save()
                    return CommonResponse.success(msg=message)
                elif int(code) == 1:
                    message = res.json().get('msg')
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = message
                    signin_today.save()
                    return CommonResponse.success(
                        msg=message
                    )
                else:
                    return CommonResponse.error(msg='签到失败！')
            if site.url in [
                # 'https://wintersakura.net/'
                'https://hudbt.hust.edu.cn/',
            ]:
                # 单独发送请求，解决冬樱签到问题
                res = requests.get(url=url, verify=False, cookies=toolbox.cookie2dict(my_site.cookie), headers={
                    'user-agent': my_site.user_agent
                })
                logger.info(res.text)
            else:
                res = self.send_request(my_site=my_site, method='post', url=url)
            logger.info(res)
            if 'pterclub.com' in site.url:
                logger.info(f'猫站签到返回值：{res.json()}')
                status = res.json().get('status')
                logger.info('{}：{}'.format(site.name, status))
                '''
                {
                  "status": "0",
                  "data": "抱歉",
                  "message": "您今天已经签到过了，请勿重复刷新。"
                }
                {
                  "status": "1",
                  "data": "&nbsp;(签到已得12)",
                  "message": "<p>这是您的第 <b>2</b> 次签到，已连续签到 <b>1</b> 天。</p><p>本次签到获得 <b>12</b> 克猫粮。</p>"
                }
                '''
                if status == '0' or status == '1':
                    message = res.json().get('message')
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = message
                    signin_today.save()
                    return CommonResponse.success(msg=message)
                else:
                    return CommonResponse.success(msg='签到失败！')

            if 'btschool' in site.url:
                # logger.info(res.status_code)
                logger.info('学校签到：{}'.format(res.text))
                text = self.parse(site, res, '//script/text()')
                logger.info('解析签到返回信息：{}'.format(text))
                if len(text) > 0:
                    location = toolbox.parse_school_location(text)
                    logger.info('学校签到链接：' + location)
                    if 'addbouns.php' in location:
                        res = self.send_request(my_site=my_site, url=site.url + location.lstrip('/'))
                # sign_in_text = self.parse(site, res, '//a[@href="index.php"]/font//text()')
                # sign_in_stat = self.parse(site, res, '//a[contains(@href,"addbouns")]')
                sign_in_text = self.parse(site, res, site.sign_info_content)
                sign_in_stat = self.parse(site, res, '//a[contains(@href,"addbouns")]')
                logger.info('{} 签到反馈：{}'.format(site.name, sign_in_text))
                if res.status_code == 200 and len(sign_in_stat) <= 0:
                    message = ''.join(sign_in_text) if len(sign_in_text) >= 1 else '您已在其他地方签到，请勿重复操作！'
                    signin_today.sign_in_today = True
                    signin_today.sign_in_info = message
                    signin_today.save()
                    return CommonResponse.success(msg=message)
                return CommonResponse.error(msg='签到失败！请求响应码：{}'.format(res.status_code))
            if res.status_code == 200:
                status = res.text
                # logger.info(status)
                # status = ''.join(self.parse(res, '//a[contains(@href,{})]/text()'.format(site.page_sign_in)))
                # 检查是否签到成功！
                # if '签到得魔力' in converter.convert(status):
                haidan_sign_str = '<input type="submit" id="modalBtn" ' \
                                  'style="cursor: default;" disabled class="dt_button" value="已经打卡" />'
                if haidan_sign_str in status \
                        or '(获得' in status \
                        or '签到已得' in status \
                        or '簽到已得' in status \
                        or '已签到' in status \
                        or '已簽到' in status \
                        or '已经签到' in status \
                        or '已經簽到' in status \
                        or '签到成功' in status \
                        or '簽到成功' in status \
                        or 'Attend got bonus' in status \
                        or 'Success' in status:
                    pass
                else:
                    return CommonResponse.error(msg='签到失败！')
                title_parse = self.parse(site, res, site.sign_info_title)
                content_parse = self.parse(site, res, site.sign_info_content)
                # if len(content_parse) <= 0:
                #     title_parse = self.parse(site, res, '//td[@id="outer"]//td[@class="embedded"]/b[1]/text()')
                #     content_parse = self.parse(site, res, '//td[@id="outer"]//td[@class="embedded"]/text()[1]')
                # if 'hdcity' in site.url:
                #     title_parse = self.parse(
                #         site,
                #         res,
                #         '//p[contains(text(),"本次签到获得魅力")]/preceding-sibling::h1[1]/span/text()'
                #     )
                #     content_parse = self.parse(site, res, '//p[contains(text(),"本次签到获得魅力")]/text()')
                logger.info(f'签到信息标题：{content_parse}')
                logger.info(f'签到信息：{content_parse}')
                title = ''.join(title_parse).strip()
                content = ''.join(content_parse).strip().replace('\n', '')
                message = title + '，' + content
                logger.info(f'{my_site} 签到返回信息：{message}')
                if len(message) <= 1:
                    message = datetime.today().strftime('%Y-%m-%d %H:%M:%S') + '打卡成功！'
                # message = ''.join(title).strip()
                signin_today.sign_in_today = True
                signin_today.sign_in_info = message
                signin_today.save()
                logger.info(site.name + message)
                return CommonResponse.success(msg=message)
            else:
                return CommonResponse.error(msg='请确认签到是否成功？？网页返回码：' + str(res.status_code))
        except Exception as e:
            msg = '{}签到失败！原因：{}'.format(site.name, e)
            logger.error(msg)
            logger.error(traceback.format_exc(limit=3))
            # raise
            # self.send_text(msg)
            return CommonResponse.error(msg=msg)

    def send_status_request(self, my_site: MySite):
        """请求抓取数据相关页面"""
        site = get_object_or_404(WebSite, my_site.site)
        user_detail_url = site.url + site.page_user.lstrip('/').format(my_site.user_id)
        logger.info(user_detail_url)
        # uploaded_detail_url = site.url + site.page_uploaded.lstrip('/').format(my_site.user_id)
        seeding_detail_url = site.url + site.page_seeding.lstrip('/').format(my_site.user_id)
        # completed_detail_url = site.url + site.page_completed.lstrip('/').format(my_site.user_id)
        # leeching_detail_url = site.url + site.page_leeching.lstrip('/').format(my_site.user_id)
        try:
            if site.url in ['https://filelist.io/']:
                # if my_site.expires > datetime.now():
                #     pass
                # else:
                logger.info(f'{site.name} cookie 已过期，重新获取！')
                session = requests.Session()
                headers = {
                    'user-agent': my_site.user_agent
                }
                res = session.get(url=site.url, headers=headers)
                validator = ''.join(self.parse(site, res, '//input[@name="validator"]/@value'))
                login_url = ''.join(self.parse(site, res, '//form/@action'))
                login_method = ''.join(self.parse(site, res, '//form/@method'))
                data = toml.load('db/ptools.toml')
                filelist = data.get('filelist')
                username = filelist.get('username')
                password = filelist.get('password')
                login_res = session.request(
                    url=site.url + login_url,
                    method=login_method,
                    headers=headers,
                    data={
                        'validator': validator,
                        'username': username,
                        'password': password,
                        'unlock': 0,
                        'returnto': '',
                    })
                cookies = ''
                logger.info(f'res: {login_res.text}')
                logger.info(f'cookies: {session.cookies.get_dict()}')
                # expires = [cookie for cookie in session.cookies if not cookie.expires]

                for key, value in session.cookies.get_dict().items():
                    cookies += f'{key}={value};'
                # my_site.expires = datetime.now() + timedelta(minutes=30)
                my_site.cookie = cookies
                my_site.save()
            # 发送请求，做种信息与正在下载信息，个人主页
            if site.url in [
                'https://hdchina.org/',
                'https://hudbt.hust.edu.cn/',
                # 'https://wintersakura.net/',
            ]:
                # 单独发送请求，解决冬樱签到问题
                user_detail_res = requests.get(url=user_detail_url, verify=False,
                                               cookies=toolbox.cookie2dict(my_site.cookie),
                                               headers={
                                                   'user-agent': my_site.user_agent
                                               })
            elif 'zhuque.in' in site.url:
                csrf_res = self.send_request(my_site=my_site, url=site.url)
                # '<meta name="x-csrf-token" content="4db531b6687b6e7f216b491c06937113">'
                x_csrf_token = self.parse(site, csrf_res, '//meta[@name="x-csrf-token"]/@content')
                logger.info(f'csrf token: {x_csrf_token}')
                header = {
                    'x-csrf-token': ''.join(x_csrf_token),
                    'accept': 'application/json',
                }
                user_detail_res = self.send_request(my_site=my_site, url=user_detail_url, header=header)
                logger.info(f'详情页：{user_detail_res.text}')
                seeding_res = self.send_request(my_site=my_site, url=site.url + site.page_mybonus, header=header)
                logger.info(f'做种信息: {seeding_res.text}')
                mail_res = self.send_request(my_site=my_site, url=site.url + 'api/user/getMainInfo', header=header)
                logger.info(f'新消息: {mail_res.text}')
                user_info = user_detail_res.json().get('data')
                bonus_hour = seeding_res.json().get('data').get('E')
                mail_data = mail_res.json().get('data')
                mail = mail_data.get('unreadAdmin') + mail_data.get('unreadInbox') + mail_data.get('unreadSystem')
                user_info.update({
                    'bonus_hour': bonus_hour,
                    'mail': mail
                })
                logger.info(f'详情页：{user_info}')
                # logger.info(f'魔力页面：{seeding_res.json()}')
                # details_html = user_detail_res.json()
                # seeding_html = seeding_res.json()
                return CommonResponse.success(data={
                    'details_html': user_info,
                    'seeding_html': '',
                    # 'leeching_html': leeching_html
                })
            else:
                user_detail_res = self.send_request(my_site=my_site, url=user_detail_url)
                time.sleep(0.6)
            # if leeching_detail_res.status_code != 200:
            #     return site.name + '种子下载信息获取错误，错误码：' + str(leeching_detail_res.status_code), False
            if user_detail_res.status_code != 200:
                return CommonResponse.error(msg=f'{site.name} 个人主页访问错误，错误码：{user_detail_res.status_code}')
            # logger.info(user_detail_res.status_code)
            # try:
            #     logger.info(f'个人主页：{user_detail_res.content.decode("utf-8-sig")}')
            # except Exception as e:
            #     logger.info('个人主页：UTF-8解析失败')
            #     logger.info(f'个人主页：{user_detail_res.content}')
            # # 解析HTML
            # logger.info(user_detail_res.is_redirect)
            if 'greatposterwall' in site.url or 'dicmusic' in site.url:
                details_html = user_detail_res.json()
                seeding_html = self.send_request(my_site=my_site, url=site.url + site.page_mybonus).json()
            elif site.url in [
                'https://lemonhd.org/',
                'https://www.htpt.cc/',
                'https://pt.btschool.club/',
                'https://pt.keepfrds.com/',
                'https://pterclub.com/',
                'https://monikadesign.uk/',
                'https://pt.hdpost.top/',
                'https://reelflix.xyz/',
            ]:
                logger.info(site.url)
                details_html = etree.HTML(user_detail_res.text)
                if 'btschool' in site.url:
                    text = details_html.xpath('//script/text()')
                    logger.info('学校：{}'.format(text))
                    if len(text) > 0:
                        try:
                            location = toolbox.parse_school_location(text)
                            logger.info('学校重定向链接：{}'.format(location))
                            if '__SAKURA' in location:
                                res = self.send_request(my_site=my_site, url=site.url + location.lstrip('/'), delay=25)
                                details_html = etree.HTML(res.text)
                                # logger.info(res.content)
                        except Exception as e:
                            logger.info(f'BT学校获取做种信息有误！{e}')
                            pass
                seeding_html = details_html
            elif 'hdchina.org' in site.url:
                details_html = etree.HTML(user_detail_res.text)
                csrf = details_html.xpath('//meta[@name="x-csrf"]/@content')
                logger.info(f'CSRF Token：{csrf}')
                # seeding_detail_res = self.send_request(my_site=my_site, url=seeding_detail_url, method='post',
                #                                        data={
                #                                            'userid': my_site.user_id,
                #                                            'type': 'seeding',
                #                                            'csrf': ''.join(csrf)
                #                                        })
                cookies = toolbox.cookie2dict(my_site.cookie)
                cookies.update(user_detail_res.cookies.get_dict())
                logger.info(cookies)
                seeding_detail_res = requests.post(url=seeding_detail_url, verify=False,
                                                   cookies=cookies,
                                                   headers={
                                                       'user-agent': my_site.user_agent
                                                   },
                                                   data={
                                                       'userid': my_site.user_id,
                                                       'type': 'seeding',
                                                       'csrf': ''.join(csrf)
                                                   })
                logger.info(f'cookie: {my_site.cookie}')
                logger.info(f'请求中的cookie: {seeding_detail_res.cookies}')
                logger.info(f'做种列表：{seeding_detail_res.text}')
                seeding_html = etree.HTML(seeding_detail_res.text)
            elif 'club.hares.top' in site.url:
                details_html = etree.HTML(user_detail_res.text)
                seeding_detail_res = self.send_request(my_site=my_site, url=seeding_detail_url, header={
                    'Accept': 'application/json'
                })
                logger.info(f'白兔做种信息：{seeding_detail_res.text}')
                seeding_html = seeding_detail_res.json()
                logger.info(f'白兔做种信息：{seeding_html}')
            else:
                if 'totheglory' in site.url:
                    # ttg的信息都是直接加载的，不需要再访问其他网页，直接解析就好
                    details_html = etree.HTML(user_detail_res.content)
                    # seeding_html = details_html.xpath('//div[@id="ka2"]/table')[0]
                else:
                    details_html = etree.HTML(user_detail_res.text)
                if site.url in [
                    # 'https://wintersakura.net/'
                    'https://hudbt.hust.edu.cn/',
                ]:
                    # 单独发送请求，解决冬樱签到问题
                    seeding_detail_res = requests.get(url=seeding_detail_url, verify=False,
                                                      cookies=toolbox.cookie2dict(my_site.cookie),
                                                      headers={
                                                          'user-agent': my_site.user_agent
                                                      })

                else:
                    seeding_detail_res = self.send_request(my_site=my_site, url=seeding_detail_url, delay=25)
                logger.info('做种信息：{}'.format(seeding_detail_res))
                # leeching_detail_res = self.send_request(my_site=my_site, url=leeching_detail_url, timeout=25)
                if seeding_detail_res.status_code != 200:
                    return CommonResponse.error(
                        msg=f'{site.name} 做种信息访问错误，错误码：{seeding_detail_res.status_code}')
                seeding_html = etree.HTML(seeding_detail_res.text)
                if 'kp.m-team.cc' in site.url:
                    url_list = self.parse(
                        site,
                        seeding_detail_res,
                        f'//p[1]/font[2]/following-sibling::'
                        f'a[contains(@href,"?type=seeding&userid={my_site.user_id}&page=")]/@href'
                    )
                    print(url_list)
                    seeding_text = seeding_detail_res.text.encode('utf8')
                    # trs.pop(0)
                    for url in url_list:
                        seeding_url = f'https://kp.m-team.cc/getusertorrentlist.php{url}'
                        seeding_res = self.send_request(my_site=my_site, url=seeding_url)
                        seeding_text += seeding_res.text.encode('utf8')
                    # logger.info(seeding_detail_res)
                    seeding_html = etree.HTML(seeding_text)
            # leeching_html = etree.HTML(leeching_detail_res.text)
            # logger.info(seeding_detail_res.text.encode('utf8'))
            return CommonResponse.success(data={
                'details_html': details_html,
                'seeding_html': seeding_html,
                # 'leeching_html': leeching_html
            })
        except NewConnectionError as nce:
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg=f'与网站建立连接失败，请检查网络？？{nce}')
        except requests.exceptions.SSLError as e:
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg=f'网站证书验证失败！！{e}')
        except ReadTimeout as e:
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg=f'网站访问超时，请检查网站是否维护？？{e}')
        except ConnectTimeoutError as e:
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg=f'网站连接超时，请稍后重试？？{e}')
        except Exception as e:
            message = f'{my_site.nickname} 访问个人主页信息：失败！原因：{e}'
            logger.error(message)
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg=message)

    def parse_status_html(self, my_site: MySite, result: dict):
        """解析个人状态"""
        site = get_object_or_404(WebSite, my_site.site)
        with lock:
            details_html = result.get('details_html')
            seeding_html = result.get('seeding_html')
            # leeching_html = result.get('leeching_html')
            if 'greatposterwall' in site.url or 'dicmusic' in site.url:
                try:
                    logger.info(details_html)
                    if details_html.get('status') == 'success' and seeding_html.get('status') == 'success':
                        seeding_response = seeding_html.get('response')
                        mail_str = seeding_response.get("notifications").get("messages")
                        notice_str = seeding_response.get("notifications").get("notifications")
                        mail = int(mail_str) + int(notice_str)
                        if my_site.mail > 0:
                            title = f'{site.name} 有{my_site.mail}条新短消息，请注意及时查收！'
                            msg = f'### <font color="red">{title}</font>  \n'
                            # todo 测试发送网站消息原内容
                            # self.send_text(title=title, message=msg)
                        details_response = details_html.get('response')
                        stats = details_response.get('stats')
                        downloaded = stats.get('downloaded')
                        uploaded = stats.get('uploaded')
                        ratio_str = stats.get('ratio').replace(',', '')
                        ratio = 'inf' if ratio_str == '∞' else ratio_str
                        my_site.time_join = stats.get('joinedDate')
                        my_site.latest_active = stats.get('lastAccess')
                        my_level = details_response.get('personal').get('class').strip(" ")
                        community = details_response.get('community')
                        seed = community.get('seeding')
                        leech = community.get('leeching')
                        # ajax.php?action=index
                        if 'greatposterwall' in site.url:
                            userdata = seeding_response.get('userstats')
                            my_bonus = userdata.get('bonusPoints')
                            # if userdata.get('bonusPoints') else 0
                            seeding_size = userdata.get('seedingSize')
                            # if userdata.get('seedingSize') else 0
                            bonus_hour = userdata.get('seedingBonusPointsPerHour')
                            # if userdata.get('seedingBonusPointsPerHour') else 0
                        if 'dicmusic' in site.url:
                            logger.info('海豚')
                            """未取得授权前不开放本段代码，谨防ban号
                            bonus_res = self.send_request(my_site, url=site.url + site.page_seeding, timeout=15)
                            sp_str = self.parse(bonus_res, '//h3[contains(text(),"总积分")]/text()')
                            my_bonus = get_decimals(''.join(sp_str))
                            hour_sp_str = self.parse(bonus_res, '//*[@id="bprates_overview"]/tbody/tr/td[3]/text()')
                            my_site.bonus_hour = ''.join(hour_sp_str)
                            seeding_size_str = self.parse(bonus_res,
                                                          '//*[@id="bprates_overview"]/tbody/tr/td[2]/text()')
                            seeding_size = FileSizeConvert.parse_2_byte(''.join(seeding_size_str))
                            """
                            my_bonus = 0
                            bonus_hour = 0
                            seeding_size = 0
                        my_site.save()
                        res_gpw = SiteStatus.objects.update_or_create(
                            site=my_site,
                            created_at__date__gte=datetime.today(),
                            defaults={
                                'ratio': float(ratio),
                                'my_level': float(my_level),
                                'downloaded': downloaded,
                                'uploaded': uploaded,
                                'my_bonus': my_bonus,
                                'my_score': 0,
                                # 做种体积
                                'seed_volume': seeding_size,
                                'seed': seed,
                                'leech': leech,
                                'bonus_hour': bonus_hour,
                                'mail': mail,
                            })
                        if float(ratio) < 1:
                            msg = f'{site.name} 分享率 {ratio} 过低，请注意'
                            # todo 消息发送
                            # self.send_text(title=msg, message=msg)
                        return CommonResponse.success(data=res_gpw)
                    else:
                        return CommonResponse.error(data=result)
                except Exception as e:
                    # 打印异常详细信息
                    message = '{} 解析个人主页信息：失败！原因：{}'.format(site.name, e)
                    logger.error(message)
                    logger.error(traceback.format_exc(limit=3))
                    # raise
                    # self.send_text('# <font color="red">' + message + '</font>  \n')
                    return CommonResponse.error(msg=message)
                pass
            elif 'zhuque.in' in site.url:
                try:
                    my_site.time_join = datetime.fromtimestamp(details_html.get(site.my_time_join_rule))
                    downloaded = details_html.get(site.my_downloaded_rule)
                    uploaded = details_html.get(site.my_uploaded_rule)
                    seeding_size = details_html.get(site.my_seed_vol_rule)
                    my_bonus = details_html.get(site.my_bonus_rule)
                    ratio = uploaded / downloaded if downloaded > 0 else 'inf'
                    invitation = details_html.get(site.my_invitation_rule)
                    my_level = details_html.get('class').get('name').strip(" ")
                    seed = details_html.get(site.my_seed_rule)
                    leech = details_html.get(site.my_leech_rule)
                    mail = details_html.get(site.my_mailbox_rule)
                    bonus_hour = details_html.get(site.my_per_hour_bonus_rule)
                    my_site.save()
                    res_zhuque = SiteStatus.objects.update_or_create(
                        site=my_site,
                        created_at__date__gte=datetime.today(),
                        defaults={
                            'ratio': ratio,
                            'downloaded': downloaded,
                            'uploaded': uploaded,
                            'my_bonus': my_bonus,
                            'my_score': 0,
                            'invitation': invitation,
                            'seed': seed,
                            'leech': leech,
                            'mail': mail,
                            'my_level': my_level,
                            'bonus_hour': bonus_hour,
                            # 做种体积
                            'seed_volume': seeding_size,
                        })
                    if my_site.mail > 0:
                        msg = f'{site.name} 有{my_site.mail}条新消息，请注意查收！'
                        # todo 发消息
                        # self.send_text(title=msg, message=msg)
                    if float(ratio) < 1:
                        msg = f'{site.name} 分享率 {ratio} 过低，请注意'
                        # self.send_text(title=msg, message=msg)
                    return CommonResponse.success(data=res_zhuque)
                except Exception as e:
                    # 打印异常详细信息
                    message = f'{site.name} 解析个人主页信息：失败！原因：{e}'
                    logger.error(message)
                    logger.error(traceback.format_exc(limit=3))
                    # raise
                    # self.send_text('# <font color="red">' + message + '</font>  \n')
                    return CommonResponse.error(msg=message)
            else:
                # 获取指定元素
                # title = details_html.xpath('//title/text()')
                # seed_vol_list = seeding_html.xpath(site.record_bulk_rule)
                try:
                    seed_vol_list = seeding_html.xpath(site.my_seed_vol_rule)
                    logger.info('做种数量seeding_vol：{}'.format(seed_vol_list))
                except:
                    pass
                if site.url in [
                    'https://lemonhd.org/',
                    'https://oldtoons.world/',
                    'https://xinglin.one/',
                    'https://piggo.me/',
                    'http://hdmayi.com/',
                    'https://pt.0ff.cc/',
                    'https://1ptba.com/',
                    'https://hdtime.org/',
                    'https://hhanclub.top/',
                    'https://pt.eastgame.org/',
                    'https://wintersakura.net/',
                    'https://gainbound.net/',
                    'http://pt.tu88.men/',
                    'https://srvfi.top/',
                    'https://www.hddolby.com/',
                    'https://gamegamept.cn/',
                    'https://hdatmos.club/',
                    'https://hdfans.org/',
                    'https://audiences.me/',
                    'https://www.nicept.net/',
                    'https://u2.dmhy.org/',
                    'https://hdpt.xyz/',
                    'https://www.icc2022.com/',
                    'http://leaves.red/',
                    'https://www.htpt.cc/',
                    'https://pt.btschool.club/',
                    'https://azusa.wiki/',
                    'https://pt.2xfree.org/',
                    'http://www.oshen.win/',
                    'https://sharkpt.net/',
                ]:
                    # 获取到的是整段，需要解析
                    logger.info('做种体积：{}'.format(seed_vol_list))
                    if len(seed_vol_list) < 1:
                        seed_vol_all = 0
                    else:
                        seeding_str = ''.join(
                            seed_vol_list
                        ).replace('\xa0', ':').replace('i', '')
                        logger.info('做种信息字符串：{}'.format(seeding_str))
                        if ':' in seeding_str:
                            seed_vol_size = seeding_str.split(':')[-1].strip()
                        if '：' in seeding_str:
                            seed_vol_size = seeding_str.split('：')[-1].strip()
                        if '&nbsp;' in seeding_str:
                            seed_vol_size = seeding_str.split('&nbsp;')[-1].strip()
                        if 'No record' in seeding_str:
                            seed_vol_size = 0
                        seed_vol_all = FileSizeConvert.parse_2_byte(seed_vol_size)
                elif site.url in [
                    'https://monikadesign.uk/',
                    'https://pt.hdpost.top/',
                    'https://reelflix.xyz/',
                    'https://pterclub.com/',
                    'https://hd-torrents.org/',
                    'https://filelist.io/',
                    'https://www.pttime.org/',
                    'https://totheglory.im/',
                    'https://pt.keepfrds.com/',
                ]:
                    # 无需解析字符串
                    seed_vol_size = ''.join(
                        seeding_html.xpath(site.my_seed_vol_rule)
                    ).replace('i', '').replace('&nbsp;', ' ')
                    seed_vol_all = FileSizeConvert.parse_2_byte(seed_vol_size)
                    logger.info(f'做种信息: {seed_vol_all}')
                elif 'club.hares.top' in site.url:
                    logger.info(f'白兔做种信息：{seeding_html}')
                    seed_vol_size = seeding_html.get('size')
                    logger.info(f'白兔做种信息：{seed_vol_size}')
                    seed_vol_all = FileSizeConvert.parse_2_byte(seed_vol_size)
                    logger.info(f'白兔做种信息：{seed_vol_all}')

                else:
                    if len(seed_vol_list) > 0 and site.url not in [
                        'https://nextpt.net/'
                    ]:
                        seed_vol_list.pop(0)
                    logger.info('做种数量seeding_vol：{}'.format(len(seed_vol_list)))
                    # 做种体积
                    seed_vol_all = 0
                    for seed_vol in seed_vol_list:
                        # logger.info(etree.tostring(seed_vol))
                        if 'iptorrents.com' in site.url:
                            vol = ''.join(seed_vol.xpath('.//text()'))
                            logger.info(vol)
                            vol = ''.join(re.findall(r'\((.*?)\)', vol))
                            logger.info(vol)
                        elif site.url in [
                            'https://exoticaz.to/',
                            'https://cinemaz.to/',
                            'https://avistaz.to/',
                        ]:
                            if ''.join(seed_vol) == '\n':
                                continue
                            vol = ''.join(seed_vol).strip()
                        else:
                            vol = ''.join(seed_vol.xpath('.//text()'))

                        # logger.info(vol)
                        if not len(vol) <= 0:
                            size = FileSizeConvert.parse_2_byte(
                                vol.replace('i', '')  # U2返回字符串为mib，gib
                            )
                            if size:
                                seed_vol_all += size
                            else:
                                msg = f'{site.name} 获取做种大小失败，请检查规则信息是否匹配？'
                                logger.warning(msg)
                                # todo
                                # self.send_text(title=msg, message=msg)
                                break
                        else:
                            # seed_vol_all = 0
                            pass
                logger.info('做种体积：{}'.format(FileSizeConvert.parse_2_file_size(seed_vol_all)))
                # logger.info(''.join(seed_vol_list).strip().split('：'))
                # logger.info(title)
                # logger.info(etree.tostring(details_html))
                # leech = self.get_user_torrent(leeching_html, site.leech_rule)
                # seed = self.get_user_torrent(seeding_html, site.seed_rule)
                logger.info(f'下载数目字符串：{details_html.xpath(site.my_leech_rule)}')
                logger.info(f'上传数目字符串：{details_html.xpath(site.my_seed_rule)}')
                leech = re.sub(r'\D', '', ''.join(details_html.xpath(site.my_leech_rule)).strip())
                logger.info(f'当前下载数：{leech}')
                seed = ''.join(details_html.xpath(site.my_seed_rule)).strip()
                logger.info(f'当前做种数：{seed}')
                if not leech and not seed:
                    return CommonResponse.error(
                        msg='请检查Cookie是否过期？'
                    )
                # seed = len(seed_vol_list)

                downloaded = ''.join(
                    details_html.xpath(site.my_downloaded_rule)
                ).replace(':', '').replace('\xa0\xa0', '').replace('i', '').replace(',', '').strip(' ')
                uploaded = ''.join(
                    details_html.xpath(site.my_uploaded_rule)
                ).replace(':', '').replace('i', '').replace(',', '').strip(' ')
                if 'hdchina' in site.url:
                    downloaded = downloaded.split('(')[0].replace(':', '').strip()
                    uploaded = uploaded.split('(')[0].replace(':', '').strip()
                downloaded = FileSizeConvert.parse_2_byte(downloaded)
                uploaded = FileSizeConvert.parse_2_byte(uploaded)

                invitation = ''.join(
                    details_html.xpath(site.my_invitation_rule)
                ).strip(']:').replace('[', '').strip()
                logger.info(f'邀请：{invitation}')
                # invitation = re.sub("\D", "", invitation)
                # time_join_1 = ''.join(
                #     details_html.xpath(site.time_join_rule)
                # ).split('(')[0].strip('\xa0').strip()
                # logger.info('注册时间：', time_join_1)
                # time_join = time_join_1.replace('(', '').replace(')', '').strip('\xa0').strip()
                logger.info(f'注册时间：{details_html.xpath(site.my_time_join_rule)}')
                if site.url in [
                    'https://monikadesign.uk/',
                    'https://pt.hdpost.top/',
                    'https://reelflix.xyz/',
                ]:
                    time_str = ''.join(details_html.xpath(site.my_time_join_rule))
                    time_str = re.sub(u"[\u4e00-\u9fa5]", "", time_str).strip()
                    time_join = datetime.strptime(time_str, '%b %d %Y')
                    logger.info(f'注册时间：{time_join}')
                    my_site.time_join = time_join
                elif 'hd-torrents.org' in site.url:
                    time_join = datetime.strptime(''.join(details_html.xpath(site.my_time_join_rule)),
                                                  '%d/%m/%Y %H:%M:%S')
                    my_site.time_join = time_join
                elif site.url in [
                    'https://exoticaz.to/',
                    'https://cinemaz.to/',
                    'https://avistaz.to/',
                ]:
                    time_str = ''.join(details_html.xpath(site.my_time_join_rule)).split('(')[0].strip()
                    time_join = datetime.strptime(time_str, '%d %b %Y %I:%M %p')
                    my_site.time_join = time_join
                else:
                    time_join = re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', ''.join(
                        details_html.xpath(site.my_time_join_rule)
                    ).strip())
                    my_site.time_join = ''.join(time_join)
                # 去除字符串中的中文
                my_level_1 = ''.join(
                    details_html.xpath(site.my_level_rule)
                ).replace('_Name', '').replace('fontBold', '').strip(" ").strip()
                if 'hdcity' in site.url:
                    my_level = my_level_1.replace('[', '').replace(']', '').strip(" ").strip()
                # elif 'u2' in site.url:
                #     my_level = ''.join(re.findall(r'/(.*).{4}', my_level_1)).title()
                else:
                    my_level = re.sub(u"([^\u0041-\u005a\u0061-\u007a])", "", my_level_1).strip(" ")
                logger.info('用户等级：{}-{}'.format(my_level_1, my_level))
                # my_level = re.sub('[\u4e00-\u9fa5]', '', my_level_1)
                # logger.info('正则去除中文：', my_level)
                # latest_active = ''.join(
                #     details_html.xpath(site.latest_active_rule)
                # ).strip('\xa0').strip()
                # if '(' in latest_active:
                #     latest_active = latest_active.split('(')[0].strip()

                # 获取字符串中的魔力值
                my_bonus = ''.join(
                    details_html.xpath(site.my_bonus_rule)
                ).replace(',', '').strip()
                logger.info('魔力：{}'.format(details_html.xpath(site.my_bonus_rule)))

                if my_bonus:
                    my_bonus = toolbox.get_decimals(my_bonus)

                my_score_1 = ''.join(
                    details_html.xpath(site.my_score_rule)
                ).strip('N/A').replace(',', '').strip()
                if my_score_1 != '':
                    my_score = toolbox.get_decimals(my_score_1)
                else:
                    my_score = 0
                # if '（' in my_score:
                #     my_score = my_score.split('（')[0]

                hr = ''.join(details_html.xpath(site.my_hr_rule)).replace('H&R:', '').replace('有效\n:', '').strip()

                my_hr = hr if hr else '0'
                logger.info(f'h&r: "{hr}" ,解析后：{my_hr}')
                # logger.info(my_score)
                # 更新我的站点数据
                # invitation = converter.convert(invitation)
                # x = invitation.split('/')
                # invitation = re.sub('[\u4e00-\u9fa5]', '', invitation)
                logger.info(f'当前获取邀请数："{invitation}"')
                if '没有邀请资格' in invitation or '沒有邀請資格' in invitation:
                    invitation = 0
                elif '/' in invitation:
                    invitation_list = [int(n) for n in invitation.split('/')]
                    # my_site.invitation = int(invitation) if invitation else 0
                    invitation = sum(invitation_list)
                elif '(' in invitation:
                    invitation_list = [int(toolbox.get_decimals(n)) for n in invitation.split('(')]
                    # my_site.invitation = int(invitation) if invitation else 0
                    invitation = sum(invitation_list)
                elif not invitation:
                    invitation = 0
                else:
                    invitation = int(re.sub('\D', '', invitation))
                my_site.latest_active = datetime.now()
                my_level = my_level.strip(" ") if my_level != '' else ' '
                seed = int(toolbox.get_decimals(seed)) if seed else 0
                logger.info(f'当前下载数：{leech}')
                leech = int(toolbox.get_decimals(leech)) if leech else 0

                logger.info('站点：{}'.format(site))
                logger.info('等级：{}'.format(my_level))
                logger.info('魔力：{}'.format(my_bonus))
                logger.info('积分：{}'.format(my_score if my_score else 0))
                # logger.info('分享率：{}'.format(ratio))
                logger.info('下载量：{}'.format(downloaded))
                logger.info('上传量：{}'.format(uploaded))
                logger.info('邀请：{}'.format(invitation))
                # logger.info('注册时间：{}'.format(time_join))
                # logger.info('最后活动：{}'.format(latest_active))
                logger.info('H&R：{}'.format(my_hr))
                logger.info('上传数：{}'.format(seed))
                logger.info('下载数：{}'.format(leech))
                try:
                    ratio = ''.join(
                        details_html.xpath(site.my_ratio_rule)
                    ).lower().replace(',', '').replace('无限', 'inf').replace('∞', 'inf'). \
                        replace('inf.', 'inf').replace(
                        'null', 'inf').replace('---', 'inf').replace('-', 'inf').replace('\xa0', '').strip(
                        ']:').strip('：').strip()
                    logger.info(f'分享率：{details_html.xpath(site.my_ratio_rule)}')
                    if not ratio:
                        ratio = ''.join(
                            details_html.xpath('//font[@class="color_ratio"][1]/following-sibling::font[1]/text()[1]'))
                    if ratio.count('上传量') > 0 and site.url == 'https://totheglory.im/':
                        # 适配TTG inf分享率
                        ratio = ''.join(
                            details_html.xpath(
                                '//font[contains(text(),"分享率 ")][1]/following-sibling::text()[1]')) \
                            .replace('\xa0', '').replace('.', '').strip()
                    # 分享率告警通知
                    logger.info('ratio：{}'.format(ratio))
                    try:
                        # 获取的分享率无法转为数字时，自行计算分享率
                        ratio = float(ratio)
                    except:
                        if int(downloaded) == 0:
                            ratio = 'inf'
                        else:
                            ratio = round(int(uploaded) / int(downloaded), 3)
                    if ratio and ratio != 'inf' and float(ratio) <= 1:
                        title = f'{site.name}  站点分享率告警：{ratio}'
                        message = f'{title}  \n'
                        # todo
                        # self.send_text(title=title, message=message)
                    # 检查邮件
                    mail_check = len(details_html.xpath(site.my_mailbox_rule))
                    notice_check = len(details_html.xpath(site.my_notice_rule))
                    logger.info(f'公告：{notice_check} 短消息：{mail_check}')
                    if mail_check > 0 or notice_check > 0:
                        if site.url in [
                            'https://monikadesign.uk/',
                            'https://pt.hdpost.top/',
                            'https://reelflix.xyz/',
                        ]:
                            mail_count = mail_check
                            # notice_str = ''.join(details_html.xpath(site.notice_rule))
                            notice_count = 0

                        else:
                            mail_str = ''.join(details_html.xpath(site.my_mailbox_rule))
                            notice_str = ''.join(details_html.xpath(site.my_notice_rule))
                            mail_count = re.sub(u"([^\u0030-\u0039])", "", mail_str)
                            notice_count = re.sub(u"([^\u0030-\u0039])", "", notice_str)
                            mail_count = int(mail_count) if mail_count else 0
                            notice_count = int(notice_count) if notice_count else 0
                        notice_list = []
                        mail_list = []
                        message_list = ''
                        if notice_count > 0:
                            print(f'{site.name} 站点公告')
                            if site.url in [
                                'https://hdchina.org/',
                                'https://hudbt.hust.edu.cn/',
                                # 'https://wintersakura.net/',
                            ]:
                                # 单独发送请求，解决冬樱签到问题
                                notice_res = requests.get(url=site.url + site.page_index, verify=False,
                                                          cookies=toolbox.cookie2dict(my_site.cookie),
                                                          headers={
                                                              'user-agent': my_site.user_agent
                                                          })
                            else:
                                notice_res = self.send_request(my_site, url=site.url + site.page_index)
                            # notice_res = self.send_request(my_site, url=site.url)
                            logger.info(f'公告信息：{notice_res}')
                            notice_list = self.parse(site, notice_res, site.my_notice_title)
                            content_list = self.parse(
                                site,
                                notice_res,
                                site.my_notice_content,
                            )
                            logger.info(f'公告信息：{notice_list}')
                            notice_list = [notice.xpath("string(.)", encoding="utf-8").strip("\n").strip("\r").strip()
                                           for notice in notice_list]
                            logger.info(f'公告信息：{notice_list}')
                            print(content_list)
                            if len(content_list) > 0:
                                content_list = [
                                    content.xpath("string(.)").replace("\r\n\r\n", "  \n> ").strip()
                                    for content in content_list]
                                notice_list = [
                                    f'## {title} \n> {content}\n\n' for
                                    title, content in zip(notice_list, content_list)
                                ]
                            logger.info(f'公告信息列表：{notice_list}')
                            # notice = '  \n\n### '.join(notice_list[:notice_count])
                            notice = ''.join(notice_list[:1])
                            message_list += f'# 公告  \n## {notice}'
                            time.sleep(1)
                        if mail_count > 0:
                            print(f'{site.name} 站点消息')
                            if site.url in [
                                'https://hdchina.org/',
                                'https://hudbt.hust.edu.cn/',
                                # 'https://wintersakura.net/',
                            ]:
                                # 单独发送请求，解决冬樱签到问题
                                message_res = requests.get(url=site.url + site.page_message, verify=False,
                                                           cookies=toolbox.cookie2dict(my_site.cookie),
                                                           headers={
                                                               'user-agent': my_site.user_agent
                                                           })
                            else:
                                message_res = self.send_request(my_site, url=site.url + site.page_message)
                            logger.info(f'PM消息页面：{message_res}')
                            mail_list = self.parse(site, message_res, site.my_message_title)
                            mail_list = [f'#### {mail.strip()} ...\n' for mail in mail_list]
                            logger.info(mail_list)
                            mail = "".join(mail_list)
                            logger.info(mail)
                            logger.info(f'PM信息列表：{mail}')
                            # 测试发送网站消息原内容
                            message = f'\n# 短消息  \n> 只显示第一页哦\n{mail}'
                            message_list += message
                        if site.url in [
                            'https://monikadesign.uk/',
                            'https://pt.hdpost.top/',
                            'https://reelflix.xyz/',
                        ]:
                            mail = len(mail_list)
                        else:
                            mail = mail_count + notice_count
                        my_site.mail = mail
                        title = f'{site.name} 有{mail}条新消息，请注意及时查收！'
                        # todo
                        # self.send_text(title=title, message=message_list)
                    else:
                        my_site.mail = 0
                    if site.url in [
                        'https://nextpt.net/',
                    ]:
                        # logger.info(site.hour_sp_rule)
                        res_bonus_hour_list = details_html.xpath(site.my_per_hour_bonus_rule)
                        # logger.info(details_html)
                        # logger.info(res_bonus_hour_list)
                        res_bonus_hour = ''.join(res_bonus_hour_list)
                        bonus_hour = toolbox.get_decimals(res_bonus_hour)
                        # 飞天邀请获取
                        logger.info(f'邀请页面：{site.url}Invites')
                        res_next_pt_invite = self.send_request(my_site, f'{site.url}Invites')
                        logger.info(res_next_pt_invite.text)
                        str_next_pt_invite = ''.join(self.parse(
                            site,
                            res_next_pt_invite,
                            site.my_invitation_rule))
                        print(f'邀请字符串：{str_next_pt_invite}')
                        list_next_pt_invite = re.findall('\d+', str_next_pt_invite)
                        print(list_next_pt_invite)
                        invitation = int(list_next_pt_invite[0]) - int(list_next_pt_invite[1])
                    else:
                        res_bonus_hour = self.get_hour_sp(my_site=my_site)
                        if res_bonus_hour.code != 0:
                            logger.error(f'{site.name}  {res_bonus_hour.msg}')
                        else:
                            bonus_hour = res_bonus_hour.data
                    # 保存上传下载等信息
                    my_site.save()
                    # 外键反向查询
                    # status = my_site.sitestatus_set.filter(updated_at__date__gte=datetime.datetime.today())
                    # logger.info(status)
                    result = SiteStatus.objects.update_or_create(
                        site=my_site, created_at__date__gte=datetime.today(),
                        defaults={
                            'ratio': float(ratio) if ratio else 0,
                            'downloaded': int(downloaded),
                            'uploaded': int(uploaded),
                            'my_bonus': float(my_bonus),
                            'my_score': float(
                                my_score) if my_score != '' else 0,
                            # 做种体积
                            'seed_volume': seed_vol_all,
                            'seed': seed,
                            'leech': leech,
                            'bonus_hour': bonus_hour,
                            'invitation': invitation,
                            'publish': 0,  # todo 待获取
                            'seed_days': 0,  # todo 待获取
                            'mail': mail,
                            'my_hr': my_hr,
                            'my_level': my_level,
                        })
                    # logger.info(result) # result 本身就是元祖
                    return CommonResponse.success(data=result)
                except Exception as e:
                    # 打印异常详细信息
                    message = f'{site.name} 解析个人主页信息：失败！原因：{e}'
                    logger.error(message)
                    logger.error(traceback.format_exc(limit=3))
                    # raise
                    # self.send_text('# <font color="red">' + message + '</font>  \n')
                    return CommonResponse.error(msg=message)

    def get_hour_sp(self, my_site: MySite):
        """获取时魔"""
        site = get_object_or_404(WebSite, my_site.site)
        url = site.url + site.page_mybonus
        if site.url in [
            'https://monikadesign.uk/',
            'https://pt.hdpost.top/',
            'https://reelflix.xyz/',
            'https://exoticaz.to/',
            'https://cinemaz.to/',
            'https://avistaz.to/',
        ]:
            url = url.format(my_site.user_id)
        logger.info(f'魔力页面链接：{url}')
        try:
            if site.url in [
                'https://hdchina.org/',
                'https://hudbt.hust.edu.cn/',
                # 'https://wintersakura.net/',
            ]:
                # 单独发送请求，解决冬樱签到问题
                response = requests.get(url=url, verify=False,
                                        cookies=toolbox.cookie2dict(my_site.cookie),
                                        headers={
                                            'user-agent': my_site.user_agent
                                        })
            else:
                response = self.send_request(my_site=my_site, url=url, )
            # print(response.text.encode('utf8'))
            """
            if 'btschool' in site.url:
                # logger.info(response.text.encode('utf8'))
                url = self.parse(response, '//form[@id="challenge-form"]/@action[1]')
                data = {
                    'md': ''.join(self.parse(response, '//form[@id="challenge-form"]/input[@name="md"]/@value')),
                    'r': ''.join(self.parse(response, '//form[@id="challenge-form"]/input[@name="r"]/@value'))
                }
                logger.info(data)
                logger.info('学校时魔页面url：', url)
                response = self.send_request(
                    my_site=my_site,
                    url=site.url + ''.join(url).lstrip('/'),
                    method='post',
                    # headers=headers,
                    data=data,
                    delay=60
                )
                """
            # response = converter.convert(response.content)
            # logger.info('时魔响应：{}'.format(response.content))
            # logger.info('转为简体的时魔页面：', str(res))
            res_list = self.parse(site, response, site.my_per_hour_bonus_rule)
            if 'u2.dmhy.org' in site.url:
                res_list = ''.join(res_list).split('，')
                res_list.reverse()
            logger.info('时魔字符串：{}'.format(res_list))
            hour_sp = toolbox.get_decimals(res_list[0].replace(',', ''))
            if len(res_list) <= 0:
                CommonResponse.error(msg='时魔获取失败！')
            return CommonResponse.success(data=hour_sp)
        except Exception as e:
            # 打印异常详细信息
            message = f'{site.name} 时魔获取失败！{e}'
            logger.error(message)
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.success(msg=message, data=0)

    def send_torrent_info_request(self, my_site: MySite):
        site = get_object_or_404(WebSite, my_site.site)
        url = site.url + site.page_index.lstrip('/')
        logger.info(f'种子页面链接：{url}')
        try:
            response = self.send_request(my_site, url)
            logger.info(site.name)
            if response.status_code == 200:
                return CommonResponse.success(data=response)
            elif response.status_code == 503:
                return CommonResponse.error(msg="我可能碰上CF盾了")
            else:
                return CommonResponse.error(msg="网站访问失败")
        except Exception as e:
            # raise
            title = f'{site.name} 网站访问失败'
            msg = '{} 网站访问失败！原因：{}'.format(site.name, e)
            # 打印异常详细信息
            logger.error(msg)
            logger.error(traceback.format_exc(limit=3))
            # self.send_text(title=title, message=msg)
            return CommonResponse.error(msg=msg)

    # @transaction.atomic
    def get_torrent_info_list(self, my_site: MySite, response: Response):
        count = 0
        new_count = 0
        site = get_object_or_404(WebSite, my_site.site)
        # if not my_site.passkey:
        #     return CommonResponse.error(msg='{}站点未设置Passkey，无法拼接种子链接！'.format(site.name))
        # logger.info(response.text.encode('utf8'))
        try:
            with lock:
                if site.url == 'https://www.hd.ai/':
                    # logger.info(response.text)
                    torrent_info_list = response.json().get('data').get('items')
                    logger.info('海带首页种子数目：{}'.format(len(torrent_info_list)))
                    for torrent_json_info in torrent_info_list:
                        # logger.info(torrent_json_info.get('download'))
                        magnet_url = site.url + torrent_json_info.get('download')
                        sale_num = torrent_json_info.get('promotion_time_type')
                        # logger.info(type(sale_status))
                        if sale_num == 1:
                            continue
                        # logger.info(type(sale_num))
                        title = torrent_json_info.get('title')
                        subtitle = torrent_json_info.get('small_descr')
                        download_url = site.url + torrent_json_info.get('download').lstrip('/')
                        result = TorrentInfo.objects.update_or_create(download_url=download_url, defaults={
                            'category': torrent_json_info.get('category'),
                            'site': site,
                            'title': title,
                            'subtitle': subtitle if subtitle != '' else title,
                            'magnet_url': magnet_url,
                            'poster_url': torrent_json_info.get('poster'),
                            'detail_url': torrent_json_info.get('details'),
                            'sale_status': TorrentBaseInfo.sale_list.get(sale_num),
                            'sale_expire': torrent_json_info.get('promotion_until'),
                            'hr': True,
                            'on_release': torrent_json_info.get('added'),
                            'size': int(torrent_json_info.get('size')),
                            'seeders': torrent_json_info.get('seeders'),
                            'leechers': torrent_json_info.get('leechers'),
                            'completers': torrent_json_info.get('times_completed'),
                            'save_path': '/downloads/brush'
                        })
                        # logger.info(result[0].site.url)
                        if not result[1]:
                            count += 1
                        else:
                            new_count += 1
                            # logger.info(torrent_info)
                else:
                    # response = self.send_request()
                    trs = self.parse(site, response, site.torrents_rule)
                    # logger.info(f'种子页面：{response.text}')
                    # logger.info(trs)
                    logger.info(len(trs))
                    print('=' * 50)
                    for tr in trs:
                        logger.info(tr)
                        # logger.info(etree.tostring(tr))
                        sale_status = ''.join(tr.xpath(site.torrent_sale_rule))
                        logger.info('sale_status: {}'.format(sale_status))
                        # 非免费种子跳过
                        if not sale_status:
                            logger.info('非免费种子跳过')
                            continue
                        title_list = tr.xpath(site.torrent_subtitle_rule)
                        logger.info(title_list)
                        subtitle = ''.join(title_list).strip().strip('剩余时间：').strip('剩餘時間：').strip('()')
                        title = ''.join(tr.xpath(site.torrent_title_rule))
                        if not title and not subtitle:
                            logger.info('无名无姓？跳过')
                            continue
                        # sale_status = ''.join(re.split(r'[^\x00-\xff]', sale_status))
                        sale_status = sale_status.replace('tStatus ', '').upper().replace(
                            'FREE', 'Free'
                        ).replace('免费', 'Free').replace(' ', '')
                        # # 下载链接，下载链接已存在则跳过
                        href = ''.join(tr.xpath(site.magnet_url_rule))
                        logger.info('href: {}'.format(href))
                        magnet_url = '{}{}'.format(
                            site.url,
                            href.replace('&type=zip', '').replace(site.url, '').lstrip('/')
                        )
                        logger.info('magnet_url: {}'.format(magnet_url))
                        if href.count('passkey') <= 0 and href.count('&sign=') <= 0:
                            download_url = '{}&passkey={}'.format(magnet_url, my_site.passkey)
                        else:
                            download_url = magnet_url
                        logger.info('download_url: {}'.format(download_url))

                        # 如果种子有HR，则为否 HR绿色表示无需，红色表示未通过HR考核
                        hr = False if tr.xpath(site.hr_rule) else True
                        # H&R 种子有HR且站点设置不下载HR种子,跳过，
                        if not hr and not my_site.hr:
                            logger.info('hr种子，未开启HR跳过')
                            continue
                        # # 促销到期时间
                        sale_expire = ''.join(tr.xpath(site.sale_expire_rule))
                        if site.url in [
                            'https://www.beitai.pt/',
                            'http://www.oshen.win/',
                            'https://www.hitpt.com/',
                            'https://hdsky.me/',
                            'https://pt.keepfrds.com/',
                            # 'https://totheglory.im/',
                        ]:
                            """
                            由于备胎等站优惠结束日期格式特殊，所以做特殊处理,使用正则表达式获取字符串中的时间
                            """
                            sale_expire = ''.join(
                                re.findall(r'\d{4}\D\d{2}\D\d{2}\D\d{2}\D\d{2}\D', ''.join(sale_expire)))

                        if site.url in [
                            'https://totheglory.im/',
                        ]:
                            # javascript: alert('Freeleech将持续到2022年09月20日13点46分,加油呀~')
                            # 获取时间数据
                            time_array = re.findall(r'\d+', ''.join(sale_expire))
                            # 不组9位
                            time_array.extend([0, 0, 0, 0])
                            # 转化为标准时间字符串
                            sale_expire = time.strftime(
                                "%Y-%m-%d %H:%M:%S",
                                time.struct_time(tuple([int(x) for x in time_array]))
                            )
                        #     pass
                        # logger.info(sale_expire)
                        # 如果促销结束时间为空，则为无限期
                        sale_expire = '无限期' if not sale_expire else sale_expire
                        # logger.info(torrent_info.sale_expire)
                        # # 发布时间
                        on_release = ''.join(tr.xpath(site.release_rule))
                        # # 做种人数
                        seeders = ''.join(tr.xpath(site.seeders_rule))
                        # # # 下载人数
                        leechers = ''.join(tr.xpath(site.leechers_rule))
                        # # # 完成人数
                        completers = ''.join(tr.xpath(site.completers_rule))
                        # 存在则更新，不存在就创建
                        # logger.info(type(seeders), type(leechers), type(completers), )
                        # logger.info(seeders, leechers, completers)
                        # logger.info(''.join(tr.xpath(site.title_rule)))
                        category = ''.join(tr.xpath(site.category_rule))
                        file_parse_size = ''.join(tr.xpath(site.size_rule))
                        # file_parse_size = ''.join(tr.xpath(''))
                        logger.info(file_parse_size)
                        file_size = FileSizeConvert.parse_2_byte(file_parse_size)
                        # subtitle = subtitle if subtitle else title
                        poster_url = ''.join(tr.xpath(site.poster_rule))  # 海报链接
                        detail_url = site.url + ''.join(
                            tr.xpath(site.detail_url_rule)
                        ).replace(site.url, '').lstrip('/')
                        logger.info('title：{}'.format(site))
                        logger.info('size{}'.format(file_size))
                        logger.info('category：{}'.format(category))
                        logger.info('download_url：{}'.format(download_url))
                        logger.info('magnet_url：{}'.format(magnet_url))
                        logger.info('subtitle：{}'.format(subtitle))
                        logger.info('poster_url：{}'.format(poster_url))
                        logger.info('detail_url：{}'.format(detail_url))
                        logger.info('sale_status：{}'.format(sale_status))
                        logger.info('sale_expire：{}'.format(sale_expire))
                        logger.info('seeders：{}'.format(seeders))
                        logger.info('leechers：{}'.format(leechers))
                        logger.info('H&R：{}'.format(hr))
                        logger.info('completers：{}'.format(completers))
                        result = TorrentInfo.objects.update_or_create(site=site, detail_url=detail_url, defaults={
                            'category': category,
                            'download_url': download_url,
                            'magnet_url': magnet_url,
                            'title': title,
                            'subtitle': subtitle,
                            'poster_url': poster_url,  # 海报链接
                            'detail_url': detail_url,
                            'sale_status': sale_status,
                            'sale_expire': sale_expire,
                            'hr': hr,
                            'on_release': on_release,
                            'size': file_size,
                            'seeders': seeders if seeders else '0',
                            'leechers': leechers if leechers else '0',
                            'completers': completers if completers else '0',
                            'save_path': '/downloads/brush'
                        })
                        logger.info('拉取种子：{} {}'.format(site.name, result[0]))
                        # time.sleep(0.5)
                        if not result[1]:
                            count += 1
                        else:
                            new_count += 1
                            # logger.info(torrent_info)
                if count + new_count <= 0:
                    return CommonResponse.error(msg='抓取失败或无促销种子！')
                return CommonResponse.success(data=(new_count, count))
        except Exception as e:
            # raise
            title = f'{site.name} 解析种子信息：失败！'
            msg = '解析种子页面失败！{}'.format(e)
            # self.send_text(title=title, message=msg)
            logger.error(msg)
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg=msg)
