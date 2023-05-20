import logging
import random
import re
import ssl
import threading
import time
import traceback
from datetime import datetime
from urllib.parse import urlparse, parse_qs

import cloudscraper
import requests
import toml
from django.shortcuts import get_object_or_404
from lxml import etree
from requests import Response, RequestException

from my_site.models import MySite, SignIn, SiteStatus, TorrentInfo
from toolbox import views as toolbox
from toolbox.schema import CommonResponse
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
                     timeout: int = 75,
                     delay: int = 15,
                     header: dict = {}):
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
        proxy = my_site.custom_server
        proxies = {
            'http': proxy if proxy else None,
            'https': proxy if proxy else None,
        } if proxy else None
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

    # @transaction.atomic
    def get_uid_and_passkey(self, cookie: dict):
        url = cookie.get('url')
        host = cookie.get('host')
        site = WebSite.objects.filter(url__contains=host).first()
        # logger.info('查询站点信息：', site, site.url, url)
        if not site:
            return CommonResponse.error(msg='尚未支持此站点：{}'.format(url))
        try:
            logger.debug(f'正在导入站点：{site.name}')
            # 如果有更新cookie，如果没有继续创建
            # userdatas = cookie.get('userdatas')
            time_stamp = cookie.get('info').get('joinTime')
            logger.debug(f'注册时间：{time_stamp}')
            if not time_stamp:
                time_join = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(time_stamp) / 1000))
            else:
                time_join = datetime.now()
            uid = cookie.get('info').get('id')
            if not uid:
                try:
                    logger.info('备份文件未获取到User_id，尝试获取中')
                    scraper = cloudscraper.create_scraper(browser={
                        'browser': 'chrome',
                        'platform': 'darwin',
                    })
                    response = scraper.get(
                        url=site.url + site.page_index,
                        cookies=cookie.get('cookies'),
                    )
                    logger.debug(response.text)
                    uid = ''.join(self.parse(site, response, site.my_uid_rule)).split('=')[-1]
                    logger.debug(f'uid:{uid}')
                except Exception as e:
                    passkey_msg = f'{site.name} Uid获取失败，请手动添加！'
                    msg = f'{site.name} 信息导入失败！ {passkey_msg}：{e}'
                    logger.error(passkey_msg)
                    return CommonResponse.error(
                        msg=msg
                    )
            result = MySite.objects.update_or_create(site=site.id, defaults={
                'nickname': site.name,
                'cookie': cookie.get('cookies'),
                'user_id': uid,
                'time_join': time_join,
            })
            # my_site = result[0]
            # passkey_msg = ''
            # logger.info('开始导入PTPP历史数据')
            # for key, value in userdatas.items():
            #     logger.debug(key)
            #     try:
            #         downloaded = value.get('downloaded')
            #         uploaded = value.get('uploaded')
            #         seeding_size = value.get('seedingSize')
            #         my_bonus = value.get('bonus')
            #         ratio = value.get('ratio')
            #         seed = value.get('seeding')
            #         my_level_str = value.get('levelName')
            #         if 'hdcity' in site.url:
            #             my_level = my_level_str.replace('[', '').replace(']', '').strip(" ").strip()
            #         else:
            #             my_level = re.sub(u"([^\u0041-\u005a\u0061-\u007a])", "", my_level_str).strip(" ")
            #         if not my_level:
            #             my_level = 'User'
            #         if ratio is None or ratio == 'null':
            #             continue
            #         if type(ratio) == str:
            #             ratio = ratio.strip('\n').strip()
            #         if float(ratio) < 0:
            #             ratio = 'inf'
            #         if not value.get(
            #                 'id') or key == 'latest' or not downloaded or not uploaded or not seeding_size or not my_bonus:
            #             continue
            #         create_time = dateutil.parser.parse(key).date()
            #         count_status = SiteStatus.objects.filter(site=my_site,
            #                                                  created_at__date=create_time).count()
            #         if count_status >= 1:
            #             continue
            #         res_status = SiteStatus.objects.update_or_create(
            #             site=my_site,
            #             created_at__date=create_time,
            #             defaults={
            #                 'uploaded': uploaded,
            #                 'downloaded': downloaded,
            #                 'ratio': float(ratio),
            #                 'my_bonus': my_bonus,
            #                 'my_level': my_level,
            #                 'seed_volume': seeding_size,
            #                 'seed': seed if seed else 0,
            #             })
            #         res_status[0].created_at = create_time
            #         res_status[0].save()
            #         logger.debug(f'数据导入结果: 日期: {create_time}，True为新建，false为更新')
            #         logger.debug(res_status)
            #     except Exception as e:
            #         msg = '{}{} 数据导入出错，错误原因：{}'.format(site.name, key, traceback.format_exc(limit=3))
            #         logger.error(msg)
            #         continue
            message = f'{site.name}: {" 信息导入成功！" if result[1] else " 信息更新成功！ "}'
            logger.info(message)
            return CommonResponse.success(msg=message)
        except Exception as e:
            message = f'{site.name}: 站点导入失败！{traceback.format_exc(3)}'
            logger.error(message)
            toolbox.send_text(title='PTPP站点导入', message=message)
            return CommonResponse.error(msg=f'{site.name}: 站点导入失败！')

    def sign_in_52pt(self, my_site: MySite):
        site = get_object_or_404(WebSite, id=my_site.site)
        url = f'{site.url}{site.page_sign_in}'.lstrip('/')
        result = self.send_request(my_site=my_site, url=url, )
        # sign_str = self.parse(result, '//font[contains(text(),"签过到")]/text()')
        sign_str = etree.HTML(result.text).xpath('//font[contains(text(),"签过到")]/text()')
        logger.debug(sign_str)
        if len(sign_str) >= 1:
            # msg = self.parse(result, '//font[contains(text(),"签过到")]/text()')
            return CommonResponse.success(msg='您已成功签到，请勿重复操作！{}'.format(sign_str))
        # if len(sign_str) >= 1:
        #     return CommonResponse.success(msg='52PT 签到太复杂不支持，访问网站保持活跃成功！')
        questionid = self.parse(site, result, '//input[contains(@name, "questionid")]/@value')
        choices = self.parse(site, result, '//input[contains(@name, "choice[]")]/@value')
        # for choice in choices:
        #     logger.debug(choice)
        data = {
            'questionid': questionid,
            'choice[]': choices[random.randint(0, len(choices) - 1)],
            'usercomment': '十步杀一人，千里不流行！',
            'wantskip': '不会'
        }
        logger.debug(data)
        sign_res = self.send_request(
            my_site=my_site, url=f'{site.url}{site.page_sign_in}'.lstrip('/'), method='post', data=data
        )
        logger.debug(sign_res.text)
        # sign_str = etree.HTML(sign_res.text.encode('utf-8-sig')).xpath
        sign_str = self.parse(site, sign_res, '//font[contains(text(),"点魔力值(连续")]/text()')
        if len(sign_str) < 1:
            return CommonResponse.error(msg='签到失败!')
        else:
            # msg = self.parse(sign_res, '//font[contains(text(),"签过到")]/text()')
            return CommonResponse.success(msg=f'签到成功！{"".join(sign_str)}')

    def sign_in_hdupt(self, my_site: MySite):
        site = get_object_or_404(WebSite, id=my_site.site)
        url = site.url + site.page_control_panel.lstrip('/')
        result = self.send_request(
            my_site=my_site,
            url=url,
        )
        sign_str = self.parse(site, result, '//span[@id="qiandao"]')
        logger.debug(sign_str)
        if len(sign_str) < 1:
            return CommonResponse.success(msg=f'{site.name} 已签到，请勿重复操作！！')
        sign_res = self.send_request(
            my_site=my_site,
            url=f'{site.url}{site.page_sign_in}'.lstrip('/'),
            method='post'
        ).text
        logger.debug(f'好多油签到反馈：{sign_res}')
        try:
            sign_res = toolbox.get_decimals(sign_res)
            if int(sign_res) > 0:
                return CommonResponse.success(
                    msg='你还需要继续努力哦！此次签到，你获得了魔力奖励：{}'.format(sign_res)
                )
        except Exception as e:
            logger.error(traceback.format_exc(3))
            return CommonResponse.error(
                msg=f'签到失败！{sign_res}: {e}'
            )

    def sign_in_hd4fans(self, my_site: MySite):
        site = get_object_or_404(WebSite, id=my_site.site)
        url = site.url + site.page_control_panel.lstrip('/')
        result = self.send_request(
            my_site=my_site,
            url=url,
        )
        sign_str = self.parse(site, result, '//span[@id="checkin"]/a')
        logger.debug(sign_str)
        if len(sign_str) < 1:
            return CommonResponse.success(msg=f'{site.name} 已签到，请勿重复操作！！')
        sign_res = self.send_request(
            my_site=my_site,
            url=f'{site.url}{site.page_sign_in}'.lstrip('/'),
            method='post',
            params={
                'action': 'checkin'
            }
        )
        msg = '你还需要继续努力哦！此次签到，你获得了魔力奖励：{}'.format(sign_res.text.encode('utf8'))
        logger.debug(msg)
        return CommonResponse.success(
            msg=msg
        )

    def sign_in_hdc(self, my_site: MySite):
        site = get_object_or_404(WebSite, id=my_site.site)
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
        logger.debug(f'签到检测页面：{result.text}')
        sign_str = self.parse(site, result, '//a[text()="已签到"]')
        logger.debug('{}签到检测'.format(site.name, sign_str))
        logger.debug(f'{result.cookies.get_dict()}')

        if len(sign_str) >= 1:
            return CommonResponse.success(msg=f'{site.name} 已签到，请勿重复操作！！')
        csrf = ''.join(self.parse(site, result, '//meta[@name="x-csrf"]/@content'))
        logger.debug(f'CSRF字符串：{csrf}')
        # sign_res = self.send_request(
        #     my_site=my_site,
        #     url=f'{site.url}{site.page_sign_in}',
        #     method=site.sign_in_method,
        #     data={
        #         'csrf': csrf
        #     }
        # )
        cookies = toolbox.cookie2dict(my_site.cookie)
        cookies.update(result.cookies.get_dict())
        logger.debug(cookies)
        sign_res = requests.request(url=f'{site.url}{site.page_sign_in}', verify=False, method='post', cookies=cookies,
                                    headers={'user-agent': my_site.user_agent}, data={'csrf': csrf})
        logger.debug(sign_res.text)
        res_json = sign_res.json()
        logger.debug(sign_res.cookies)
        logger.info('签到返回结果：{}'.format(res_json))
        if res_json.get('state') == 'success':
            if len(sign_res.cookies) >= 1:
                logger.debug(f'我的COOKIE：{my_site.cookie}')
                logger.debug(f'新的COOKIE字典：{sign_res.cookies.items()}')
                cookie = ''
                for k, v in sign_res.cookies.items():
                    cookie += f'{k}={v};'
                logger.debug(f'新的COOKIE：{sign_res.cookies.items()}')
                my_site.cookie = cookie
                my_site.save()
            msg = f"签到成功，您已连续签到{res_json.get('signindays')}天，本次增加魔力:{res_json.get('integral')}。"
            logger.info(msg)
            return CommonResponse.success(msg=msg)
        else:
            msg = res_json.get('msg')
            logger.error(msg)
            return CommonResponse.error(msg=msg)

    def sign_in_u2(self, my_site: MySite):
        site = get_object_or_404(WebSite, id=my_site.site)
        url = f'{site.url}{site.page_sign_in}'.lstrip('/')
        result = self.send_request(my_site=my_site, url=url, )
        sign_str = ''.join(self.parse(site, result, '//a[@href="showup.php"]/text()'))
        logger.info(site.name + sign_str)
        if '已签到' in sign_str or '已簽到' in sign_str:
            # if '已签到' in converter.convert(sign_str):
            return CommonResponse.success(msg=f'{site.name}已签到，请勿重复操作！！')
        req = self.parse(site, result, '//form//td/input[@name="req"]/@value')
        hash_str = self.parse(site, result, '//form//td/input[@name="hash"]/@value')
        form = self.parse(site, result, '//form//td/input[@name="form"]/@value')
        submit_name = self.parse(site, result, '//form//td/input[@type="submit"]/@name')
        submit_value = self.parse(site, result, '//form//td/input[@type="submit"]/@value')
        message = '天空飘来五个字儿,幼儿园里没有事儿'
        logger.debug(submit_name)
        logger.debug(submit_value)
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
        logger.debug(data)
        response = self.send_request(
            my_site,
            url=f'{site.url}{site.page_sign_in.lstrip("/")}?action=show',
            method='post',
            data=data,
        )
        logger.debug(response.content.decode('utf8'))
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
            logger.error('签到失败！')
            return CommonResponse.error(msg='签到失败！')

    def sign_in_opencd(self, my_site: MySite):
        """皇后签到"""
        site = get_object_or_404(WebSite, id=my_site.site)
        check_url = site.url + site.page_user
        res_check = self.send_request(
            my_site=my_site,
            url=check_url)
        href_sign_in = self.parse(site, res_check, '//a[@href="/plugin_sign-in.php?cmd=show-log"]')
        if len(href_sign_in) >= 1:
            return CommonResponse.success(data={'state': 'false'})
        url = f'{site.url}{site.page_sign_in}'.lstrip('/')
        logger.debug('# 开启验证码！')
        res = self.send_request(my_site=my_site, method='get', url=url)
        logger.debug(res.text.encode('utf-8-sig'))
        img_src = ''.join(self.parse(site, res, '//form[@id="frmSignin"]//img/@src'))
        img_get_url = site.url + img_src
        times = 0
        # imagestring = ''
        ocr_result = None
        while times <= 5:
            ocr_result = toolbox.baidu_ocr_captcha(img_get_url)
            if ocr_result.code == 0:
                imagestring = ocr_result.data
                logger.debug('验证码长度：{}'.format(len(imagestring)))
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
        logger.debug('请求参数：{}'.format(data))
        result = self.send_request(
            my_site=my_site,
            method='post',
            url=f'{site.url}plugin_sign-in.php?cmd=signin', data=data)
        logger.debug('皇后签到返回值：{}  \n'.format(result.text.encode('utf-8-sig')))
        return CommonResponse.success(data=result.json())

    def sign_in_hdsky(self, my_site: MySite):
        """HDSKY签到"""
        site = get_object_or_404(WebSite, id=my_site.site)
        url = f'{site.url}{site.page_sign_in}'.lstrip('/')
        # sky无需验证码时使用本方案
        # if not captcha:
        #     result = self.send_request(
        #         my_site=my_site,
        #         method='post',
        #         url=url
        #     )
        # sky无验证码方案结束
        # 获取img hash
        logger.debug('# 开启验证码！')
        res = self.send_request(
            my_site=my_site,
            method='post',
            url=f'{site.url}image_code_ajax.php',
            data={
                'action': 'new'
            }).json()
        # img url
        img_get_url = f'{site.url}image.php?action=regimage&imagehash={res.get("code")}'
        logger.debug(f'验证码图片链接：{img_get_url}')
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
                logger.debug(f'验证码长度：{len(imagestring)}')
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
        # logger.debug('请求参数', data)
        result = self.send_request(
            my_site=my_site,
            method='post',
            url=url, data=data)
        logger.debug('天空返回值：{}\n'.format(result.text))
        return CommonResponse.success(data=result.json())

    def sign_in_ttg(self, my_site: MySite):
        """
        TTG签到
        :param my_site:
        :return:
        """
        site = get_object_or_404(WebSite, id=my_site.site)
        url = site.url + site.page_user.format(my_site.user_id)
        logger.info(f'{site.name} 个人主页：{url}')
        try:
            res = self.send_request(my_site=my_site, url=url)
            # logger.debug(res.text.encode('utf8'))
            # html = self.parse(site,res, '//script/text()')
            html = etree.HTML(res.text).xpath('//script/text()')
            # logger.debug(html)
            text = ''.join(html).replace('\n', '').replace(' ', '')
            logger.debug(text)
            signed_timestamp = toolbox.get_decimals(re.search("signed_timestamp:\"\d{10}", text).group())

            signed_token = re.search('[a-zA-Z0-9]{32}', text).group()
            params = {
                'signed_timestamp': signed_timestamp,
                'signed_token': signed_token
            }
            logger.debug(f'signed_timestamp:{signed_timestamp}')
            logger.debug(f'signed_token:{signed_token}')

            resp = self.send_request(
                my_site,
                f'{site.url}{site.page_sign_in}',
                method='post',
                data=params)
            logger.debug(f'{my_site.nickname}: {resp.content.decode("utf8")}')
            return CommonResponse.success(msg=resp.content.decode('utf8'))
        except Exception as e:
            # 打印异常详细信息
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg='{} 签到失败: {}'.format(site.name, e))

    def sign_in_zhuque(self, my_site):
        site = get_object_or_404(WebSite, id=my_site.site)
        try:
            csrf_res = self.send_request(my_site=my_site, url=site.url)
            # '<meta name="x-csrf-token" content="4db531b6687b6e7f216b491c06937113">'
            x_csrf_token = self.parse(site, csrf_res, '//meta[@name="x-csrf-token"]/@content')
            logger.debug(f'csrf token: {x_csrf_token}')
            header = {
                'user-agent': my_site.user_agent,
                'content-type': 'application/json',
                'referer': 'https://zhuque.in/gaming/genshin/character/list',
                'x-csrf-token': ''.join(x_csrf_token),
            }
            data = {"resetModal": "true", "all": 1, }
            url = f'{site.url}{site.page_sign_in}'
            logger.info(url)
            res = self.send_request(my_site=my_site, method='post', url=url, json=data, header=header)
            # 单独发送请求，解决冬樱签到问题
            # res = requests.post(url=url, verify=False, cookies=cookie2dict(my_site.cookie), json=data, headers=header)
            """
            {
                "status": 200,
                "data": {
                    "code": "FIRE_GENSHIN_CHARACTER_MAGIC_SUCCESS",
                    "bonus": 0
                }
            }
            """
            logger.debug(res.content)
            return CommonResponse.success(data=res.json())
        except Exception as e:
            # 打印异常详细信息
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(
                msg='{} 签到失败: {}'.format(site.name, e)
            )

    @staticmethod
    def get_user_torrent(html, rule):
        res_list = html.xpath(rule)
        logger.debug(f'content: {res_list}')
        # logger.debug('res_list:', len(res_list))
        return '0' if len(res_list) == 0 else res_list[0]

    # @transaction.atomic
    def sign_in(self, my_site: MySite):
        """签到"""
        site = get_object_or_404(WebSite, id=my_site.site)
        logger.info(f'{site.name} 开始签到')
        signin_today = my_site.signin_set.filter(created_at__date__gte=datetime.today()).first()
        # 如果已有签到记录
        if signin_today:
            if signin_today.sign_in_today is True:
                return CommonResponse.success(msg=f'{my_site.nickname} 已签到，请勿重复签到！')
        else:
            signin_today = SignIn(site=my_site, created_at=datetime.now())
        url = f'{site.url}{site.page_sign_in}'.lstrip('/')
        logger.info(f'签到链接：{url}')
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
            if 'zhuque.in' in site.url:
                result = self.sign_in_zhuque(my_site)
                if result.code == 0 and result.data.get('status') == 200:
                    data = result.data.get("data")
                    bonus = data.get("bonus")
                    message = f'技能释放成功，获得{bonus}灵石'
                    # if bonus > 0:
                    #     signin_today.sign_in_today = True
                    #     signin_today.sign_in_info = message
                    #     signin_today.save()
                    result.msg = message
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
                    logger.debug(result.data)
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
                        return CommonResponse.success(msg=message)
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
                logger.info(f'皇后签到结果：{result.to_dict()}')
                if result.code == 0:
                    res_json = result.data
                    if res_json.get('state') == 'success':
                        signin_today.sign_in_today = True
                        # data = res_json.get('msg')
                        message = f"签到成功，您已连续签到{res_json.get('signindays')}天，本次增加魔力:{res_json.get('integral')}。"
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
                logger.debug(res.text)
                code = res.json().get('code')
                # logger.debug('白兔返回码：'+ type(code))
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
                    return CommonResponse.success(msg=message)
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
                logger.debug(res.text)
            else:
                res = self.send_request(my_site=my_site, method='post', url=url)
            logger.info(f'{my_site.nickname}: {res}')
            if 'pterclub.com' in site.url:
                logger.debug(f'猫站签到返回值：{res.json()}')
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
                logger.debug(f'学校签到：{res.text}')
                text = self.parse(site, res, '//script/text()')
                logger.debug('解析签到返回信息：{text}')
                if len(text) > 0:
                    location = toolbox.parse_school_location(text)
                    logger.debug(f'学校签到链接：{location}')
                    if 'addbouns.php' in location:
                        res = self.send_request(my_site=my_site, url=f'{site.url}{location.lstrip("/")}')
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
                return CommonResponse.error(msg=f'签到失败！请求响应码：{res.status_code}')
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
                logger.debug(f'{my_site.nickname}: 签到信息标题：{content_parse}')
                logger.debug(f'{my_site.nickname}: 签到信息：{content_parse}')
                title = ''.join(title_parse).strip()
                content = ''.join(content_parse).strip().replace('\n', '')
                message = title + '，' + content
                logger.info(f'{my_site} 签到返回信息：{message}')
                if len(message) <= 1:
                    message = f'{datetime.today().strftime("%Y-%m-%d %H:%M:%S")}打卡成功！'
                # message = ''.join(title).strip()
                signin_today.sign_in_today = True
                signin_today.sign_in_info = message
                signin_today.save()
                logger.info(f'{my_site.nickname}: {message}')
                return CommonResponse.success(msg=message)
            else:
                return CommonResponse.error(msg=f'请确认签到是否成功？？网页返回码：{res.status_code}')
        except Exception as e:
            msg = '{}签到失败！原因：{}'.format(site.name, e)
            logger.error(msg)
            logger.error(traceback.format_exc(limit=3))
            # raise
            # toolbox.send_text(msg)
            return CommonResponse.error(msg=msg)

    def get_filelist_cookie(self, my_site: MySite):
        """更新filelist站点COOKIE"""
        site = get_object_or_404(WebSite, id=my_site.site)
        logger.info(f'{site.name} 开始获取cookie！')
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
            url=f'{site.url}{login_url}',
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
        logger.debug(f'res: {login_res.text}')
        logger.debug(f'cookies: {session.cookies.get_dict()}')
        # expires = [cookie for cookie in session.cookies if not cookie.expires]

        for key, value in session.cookies.get_dict().items():
            cookies += f'{key}={value};'
        # my_site.expires = datetime.now() + timedelta(minutes=30)
        my_site.cookie = cookies
        my_site.save()

    def get_zhuque_header(self, my_site: MySite):
        """获取朱雀csrf-token，并生成请求头"""
        site = get_object_or_404(WebSite, id=my_site.site)
        user_detail_url = f'{site.url}{site.page_user.lstrip("/").format(my_site.user_id)}'
        logger.info(f'{site.name} 开始抓取站点个人主页信息，网址：{user_detail_url}')
        csrf_res = self.send_request(my_site=my_site, url=site.url)
        # '<meta name="x-csrf-token" content="4db531b6687b6e7f216b491c06937113">'
        x_csrf_token = self.parse(site, csrf_res, '//meta[@name="x-csrf-token"]/@content')
        logger.debug(f'csrf token: {x_csrf_token}')
        return {
            'x-csrf-token': ''.join(x_csrf_token),
            'accept': 'application/json',
        }

    def get_mail_info(self, my_site: MySite, details_html, header):
        """获取站点短消息"""
        site = get_object_or_404(WebSite, id=my_site.site)
        mail = 0
        mail_check = len(details_html.xpath(site.my_mailbox_rule))
        if 'zhuque.in' in site.url:
            mail_res = self.send_request(my_site=my_site, url=f'{site.url}api/user/getMainInfo', header=header)
            logger.debug(f'新消息: {mail_res.text}')
            mail_data = mail_res.json().get('data')
            mail = mail_data.get('unreadAdmin') + mail_data.get('unreadInbox') + mail_data.get('unreadSystem')
            if mail > 0:
                title = f'{site.name} 有{mail}条新消息，请注意及时查收！'
                toolbox.send_text(title=title, message=title)
        logger.info(f' 短消息：{mail_check}')
        res = SiteStatus.objects.update_or_create(
            site=my_site,
            created_at__date__gte=datetime.today(),
        )
        status = res[0]
        if mail_check > 0:
            if site.url in [
                'https://monikadesign.uk/',
                'https://pt.hdpost.top/',
                'https://reelflix.xyz/',
            ]:
                mail_count = mail_check
            else:
                mail_str = ''.join(details_html.xpath(site.my_mailbox_rule))
                mail_count = re.sub(u"([^\u0030-\u0039])", "", mail_str)
                mail_count = int(mail_count) if mail_count else 0
            mail_list = []
            message_list = ''
            if mail_count > 0:
                logger.info(f'{site.name} 站点消息')
                if site.url in [
                    'https://hdchina.org/',
                    'https://hudbt.hust.edu.cn/',
                    # 'https://wintersakura.net/',
                ]:
                    # 单独发送请求，解决冬樱签到问题
                    message_res = requests.get(url=f'{site.url}{site.page_message}', verify=False,
                                               cookies=toolbox.cookie2dict(my_site.cookie),
                                               headers={
                                                   'user-agent': my_site.user_agent
                                               })
                else:
                    message_res = self.send_request(my_site, url=f'{site.url}{site.page_message}')
                logger.info(f'PM消息页面：{message_res}')
                mail_list = self.parse(site, message_res, site.my_message_title)
                mail_list = [f'#### {mail.strip()} ...\n' for mail in mail_list]
                logger.debug(mail_list)
                mail = "".join(mail_list)
                logger.info(f'PM信息列表：{mail}')
                # 测试发送网站消息原内容
                message = f'\n# 短消息  \n> 只显示第一页哦\n{mail}'
                message_list += message
            status.mail = len(mail_list)
            status.save()
            title = f'{site.name} 有{len(mail_list)}条新消息！'
            toolbox.send_text(title=title, message=message_list)
        else:
            status.mail = 0
            status.save()

    def get_notice_info(self, my_site: MySite, details_html):
        """获取站点公告信息"""
        site = get_object_or_404(WebSite, id=my_site.site)
        if site.url in [
            'https://monikadesign.uk/',
            'https://pt.hdpost.top/',
            'https://reelflix.xyz/',
        ]:
            pass
        else:
            notice = 0
            notice_check = len(details_html.xpath(site.my_notice_rule))
            logger.debug(f'公告：{notice_check} ')
            if notice_check > 0:
                notice_str = ''.join(details_html.xpath(site.my_notice_rule))
                notice_count = re.sub(u"([^\u0030-\u0039])", "", notice_str)
                notice_count = int(notice_count) if notice_count else 0
                notice_list = []
                message_list = ''
                if notice_count > 0:
                    logger.info(f'{site.name} 站点公告')
                    if site.url in [
                        'https://hdchina.org/',
                        'https://hudbt.hust.edu.cn/',
                        # 'https://wintersakura.net/',
                    ]:
                        # 单独发送请求，解决冬樱签到问题
                        notice_res = requests.get(url=f'{site.url}{site.page_index}', verify=False,
                                                  cookies=toolbox.cookie2dict(my_site.cookie),
                                                  headers={
                                                      'user-agent': my_site.user_agent
                                                  })
                    else:
                        notice_res = self.send_request(my_site, url=f'{site.url}{site.page_index}')
                    # notice_res = self.send_request(my_site, url=site.url)
                    logger.debug(f'公告信息：{notice_res}')
                    notice_list = self.parse(site, notice_res, site.my_notice_title)
                    content_list = self.parse(
                        site,
                        notice_res,
                        site.my_notice_content,
                    )
                    logger.debug(f'公告信息：{notice_list}')
                    notice_list = [notice.xpath("string(.)", encoding="utf-8").strip("\n").strip("\r").strip()
                                   for notice in notice_list]
                    logger.debug(f'公告信息：{notice_list}')
                    logger.debug(content_list)
                    if len(content_list) > 0:
                        content_list = [
                            content.xpath("string(.)").replace("\r\n\r\n", "  \n> ").strip()
                            for content in content_list]
                        notice_list = [
                            f'## {title} \n> {content}\n\n' for
                            title, content in zip(notice_list, content_list)
                        ]
                    logger.debug(f'公告信息列表：{notice_list}')
                    # notice = '  \n\n### '.join(notice_list[:notice_count])
                    notice = ''.join(notice_list[:1])
                    message_list += f'# 公告  \n## {notice}'
                    title = f'{site.name} 有{notice_count}条新公告！'
                    toolbox.send_text(title=title, message=message_list)

    def get_userinfo_html(self, my_site: MySite, headers: dict):
        """请求抓取数据相关页面"""
        site = get_object_or_404(WebSite, id=my_site.site)
        user_detail_url = site.url + site.page_user.lstrip('/').format(my_site.user_id)
        logger.info(f'{site.name} 开始抓取站点个人主页信息，网址：{user_detail_url}')
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

        else:
            user_detail_res = self.send_request(my_site=my_site, url=user_detail_url, header=headers)
        if user_detail_res.status_code != 200:
            return CommonResponse.error(msg=f'{site.name} 个人主页访问错误，错误码：{user_detail_res.status_code}')
        if site.url in [
            'https://greatposterwall.com/', 'https://dicmusic.club/',
        ]:
            user_detail = user_detail_res.json()
            if user_detail.get('status') != 'success':
                return CommonResponse.error(
                    msg=f'{site.name} 个人主页访问错误，错误：{user_detail.get("status")}')
            details_html = user_detail.get('response')
        elif site.url in [
            'https://zhuque.in/'
        ]:
            user_detail = user_detail_res.json()
            if user_detail.get('status') != 200:
                return CommonResponse.error(
                    msg=f'{site.name} 个人主页访问错误，错误：{user_detail.get("status")}')
            details_html = user_detail.get('data')
        elif site.url in [
            'https://totheglory.im/',
        ]:
            details_html = etree.HTML(user_detail_res.content)
        else:
            details_html = etree.HTML(user_detail_res.text)
        if 'btschool' in site.url:
            text = details_html.xpath('//script/text()')
            logger.debug('学校：{}'.format(text))
            if len(text) > 0:
                try:
                    location = toolbox.parse_school_location(text)
                    logger.debug('学校重定向链接：{}'.format(location))
                    if '__SAKURA' in location:
                        res = self.send_request(my_site=my_site, url=site.url + location.lstrip('/'), delay=25)
                        details_html = etree.HTML(res.text)
                except Exception as e:
                    logger.debug(f'BT学校个人主页访问失败！{e}')
        if 'hdchina.org' in site.url:
            cookies = ''
            logger.debug(f'res: {user_detail_res.text}')
            logger.debug(f'cookies: {user_detail_res.cookies.get_dict()}')
            # expires = [cookie for cookie in session.cookies if not cookie.expires]
            logger.debug(f'请求中的cookie: {user_detail_res.cookies}')

            # for key, value in user_detail_res.cookies.get_dict().items():
            #     cookies += f'{key}={value};'
            # my_site.expires = datetime.now() + timedelta(minutes=30)
            # my_site.cookie = cookies
            # my_site.save()
        self.parse_userinfo_html(my_site=my_site, details_html=details_html)
        return CommonResponse.success(data=details_html)

    def get_seeding_html(self, my_site: MySite, headers: dict, details_html=None):
        """请求做种数据相关页面"""
        site = get_object_or_404(WebSite, id=my_site.site)
        seeding_detail_url = site.url + site.page_seeding.lstrip('/').format(my_site.user_id)
        logger.info(f'{site.name} 开始抓取站点做种信息，网址：{seeding_detail_url}')
        if site.url in [
            'https://greatposterwall.com/', 'https://dicmusic.club/'
        ]:
            seeding_detail_res = self.send_request(my_site=my_site, url=site.url + site.page_mybonus).json()
            if seeding_detail_res.get('status') != 'success':
                return CommonResponse.error(
                    msg=f'{site.name} 做种信息访问错误，错误：{seeding_detail_res.get("status")}')
            seeding_html = seeding_detail_res.get('response')
        elif site.url in [
            'https://lemonhd.org/',
            'https://www.htpt.cc/',
            'https://pt.btschool.club/',
            'https://pt.keepfrds.com/',
            'https://pterclub.com/',
            'https://monikadesign.uk/',
            'https://pt.hdpost.top/',
            'https://reelflix.xyz/',
            'https://totheglory.im/',
        ]:
            logger.info(site.url)
            seeding_html = details_html
        elif 'hdchina.org' in site.url:
            # print(details_html.content)
            # details_html = etree.HTML(details_html.text)
            csrf = details_html.xpath('//meta[@name="x-csrf"]/@content')
            logger.debug(f'CSRF Token：{csrf}')

            seeding_detail_res = requests.post(
                url=seeding_detail_url, verify=False,
                cookies=toolbox.cookie2dict(my_site.cookie),
                headers={
                    'user-agent': my_site.user_agent
                },
                data={
                    'userid': my_site.user_id,
                    'type': 'seeding',
                    'csrf': ''.join(csrf)
                })
            logger.debug(f'cookie: {my_site.cookie}')
            logger.debug(f'做种列表：{seeding_detail_res.text}')
            seeding_html = etree.HTML(seeding_detail_res.text)
        elif 'club.hares.top' in site.url:
            seeding_detail_res = self.send_request(my_site=my_site, url=seeding_detail_url, header={
                'Accept': 'application/json'
            })
            logger.debug(f'白兔做种信息：{seeding_detail_res.text}')
            seeding_html = seeding_detail_res.json()
            logger.debug(f'白兔做种信息：{seeding_html}')
        else:
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
                seeding_detail_res = self.send_request(my_site=my_site, url=seeding_detail_url, header=headers,
                                                       delay=25)
            logger.debug('做种信息：{}'.format(seeding_detail_res))
            if seeding_detail_res.status_code != 200:
                return CommonResponse.error(
                    msg=f'{site.name} 做种信息访问错误，错误码：{seeding_detail_res.status_code}')
            if 'kp.m-team.cc' in site.url:
                seeding_text = self.get_m_team_seeding(my_site, seeding_detail_res)
                seeding_html = etree.HTML(seeding_text)
            else:
                seeding_html = etree.HTML(seeding_detail_res.text)
        self.parse_seeding_html(my_site=my_site, seeding_html=seeding_html)
        return CommonResponse.success(data=seeding_html)

    def get_m_team_seeding(self, my_site, seeding_detail_res):
        site = get_object_or_404(WebSite, id=my_site.site)
        url_list = self.parse(
            site,
            seeding_detail_res,
            f'//p[1]/font[2]/following-sibling::'
            f'a[contains(@href,"?type=seeding&userid={my_site.user_id}&page=")]/@href'
        )
        seeding_text = seeding_detail_res.text.encode('utf8')
        for url in url_list:
            seeding_url = f'https://kp.m-team.cc/getusertorrentlist.php{url}'
            seeding_res = self.send_request(my_site=my_site, url=seeding_url)
            seeding_text += seeding_res.text.encode('utf8')
        return seeding_text

    def send_status_request(self, my_site: MySite):
        """请求抓取数据相关页面"""
        site = get_object_or_404(WebSite, id=my_site.site)
        # uploaded_detail_url = site.url + site.page_uploaded.lstrip('/').format(my_site.user_id)
        seeding_detail_url = site.url + site.page_seeding.lstrip('/').format(my_site.user_id)
        # completed_detail_url = site.url + site.page_completed.lstrip('/').format(my_site.user_id)
        # leeching_detail_url = site.url + site.page_leeching.lstrip('/').format(my_site.user_id)
        status_today = my_site.sitestatus_set.filter(created_at__date__gte=datetime.today()).first()
        if not status_today:
            status_today = SiteStatus(site=my_site)
            status_latest = my_site.sitestatus_set.latest('created_at')
            if status_latest:
                status_today.uploaded = status_latest.uploaded
                status_today.downloaded = status_latest.downloaded
                status_today.ratio = status_latest.ratio
                status_today.my_bonus = status_latest.my_bonus
                status_today.my_score = status_latest.my_score
                status_today.seed_volume = status_latest.seed_volume
                status_today.my_level = status_latest.my_level
            status_today.save()
        err_msg = []
        try:
            headers = {}
            if site.url in [
                'https://hdchina.org/',
                'https://hudbt.hust.edu.cn/',
                # 'https://wintersakura.net/',
            ]:
                headers = {
                    'user-agent': my_site.user_agent
                }
            if 'zhuque.in' in site.url:
                zhuque_header = self.get_zhuque_header(my_site)
                headers.update(zhuque_header)
            if site.url in ['https://filelist.io/']:
                # 获取filelist站点COOKIE
                self.get_filelist_cookie(my_site)
            # 发送请求，请求个人主页
            details_html = self.get_userinfo_html(my_site, headers=headers)
            if details_html.code != 0:
                detail_msg = f'个人主页解析失败!'
                err_msg.append(detail_msg)
                logger.warning(f'{my_site.nickname} {detail_msg}')
            # 请求时魔页面,信息写入数据库
            hour_bonus = self.get_hour_sp(my_site, headers=headers)
            if hour_bonus.code != 0:
                bonus_msg = f'时魔获取失败!'
                err_msg.append(bonus_msg)
                logger.warning(f'{my_site.nickname} {bonus_msg}')
            # 请求邮件页面，直接推送通知到手机
            if site.url not in [
                'https://dicmusic.club/',
                'https://greatposterwall.com/',
                'https://zhuque.in/',
            ]:
                # 发送请求，请求做种信息页面
                seeding_html = self.get_seeding_html(my_site, headers=headers, details_html=details_html.data)
                if seeding_html.code != 0:
                    seeding_msg = f'做种页面访问失败!'
                    err_msg.append(seeding_msg)
                    logger.warning(f'{my_site.nickname} {seeding_msg}')
                if details_html.code == 0:
                    self.get_mail_info(my_site, details_html.data, header=headers)
                    # 请求公告信息，直接推送通知到手机
                    self.get_notice_info(my_site, details_html.data)
            # return self.parse_status_html(my_site, data)
            # status = SiteStatus.objects.filter(site=my_site, created_at__date=datetime.today()).first()
            if len(err_msg) <= 3:
                return CommonResponse.success(
                    msg=f'{my_site.nickname} 数据更新完毕! {("🆘 " + " ".join(err_msg)) if len(err_msg) > 0 else ""}')
            return CommonResponse.error(
                msg=f'{my_site.nickname} 数据更新失败! 🆘 {" ".join(err_msg)}')
        except RequestException as nce:
            msg = f'🆘 与网站 {my_site.nickname} 建立连接失败，请检查网络？？'
            logger.error(msg)
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg=msg)
        except Exception as e:
            message = f'🆘 {my_site.nickname} 统计个人数据失败！原因：{err_msg} {e}'
            logger.error(message)
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg=message)

    def get_time_join(self, my_site, details_html):
        site = get_object_or_404(WebSite, id=my_site.site)
        with lock:
            try:
                if 'greatposterwall' in site.url or 'dicmusic' in site.url:
                    logger.debug(details_html)
                    details_response = details_html.get('response')
                    stats = details_response.get('stats')
                    my_site.time_join = stats.get('joinedDate')
                    my_site.latest_active = stats.get('lastAccess')
                    my_site.save()
                elif 'zhuque.in' in site.url:
                    userdata = details_html.get('data')
                    my_site.time_join = datetime.fromtimestamp(userdata.get(site.my_time_join_rule))
                    my_site.save()
                else:
                    logger.debug(f'注册时间：{details_html.xpath(site.my_time_join_rule)}')
                    if site.url in [
                        'https://monikadesign.uk/',
                        'https://pt.hdpost.top/',
                        'https://reelflix.xyz/',
                    ]:
                        time_str = ''.join(details_html.xpath(site.my_time_join_rule))
                        time_str = re.sub(u"[\u4e00-\u9fa5]", "", time_str).strip()
                        time_join = datetime.strptime(time_str, '%b %d %Y')
                        logger.debug(f'注册时间：{time_join}')
                        my_site.time_join = time_join
                    elif 'hd-torrents.org' in site.url:
                        my_site.time_join = datetime.strptime(
                            ''.join(details_html.xpath(site.my_time_join_rule)),
                            '%d/%m/%Y %H:%M:%S'
                        )
                    elif site.url in [
                        'https://exoticaz.to/',
                        'https://cinemaz.to/',
                        'https://avistaz.to/',
                    ]:
                        time_str = ''.join(details_html.xpath(site.my_time_join_rule)).split('(')[0].strip()
                        my_site.time_join = datetime.strptime(time_str, '%d %b %Y %I:%M %p')
                    else:
                        time_join = re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', ''.join(
                            details_html.xpath(site.my_time_join_rule)
                        ).strip())
                        my_site.time_join = ''.join(time_join)
                    my_site.latest_active = datetime.now()
                    my_site.save()
            except Exception as e:
                msg = f'🆘 {site.name} 注册时间获取出错啦！'
                logger.error(traceback.format_exc(3))

    def parse_userinfo_html(self, my_site, details_html):
        """解析个人主页"""
        site = get_object_or_404(WebSite, id=my_site.site)
        with lock:
            try:
                if 'greatposterwall' in site.url or 'dicmusic' in site.url:
                    logger.debug(details_html)
                    stats = details_html.get('stats')
                    downloaded = stats.get('downloaded')
                    uploaded = stats.get('uploaded')
                    ratio_str = stats.get('ratio').replace(',', '')
                    ratio = 'inf' if ratio_str == '∞' else ratio_str
                    my_level = details_html.get('personal').get('class').strip(" ")
                    community = details_html.get('community')
                    seed = community.get('seeding')
                    leech = community.get('leeching')
                    # ajax.php?action=index
                    my_site.save()
                    res_gpw = SiteStatus.objects.update_or_create(
                        site=my_site,
                        created_at__date__gte=datetime.today(),
                        defaults={
                            'ratio': float(ratio),
                            'my_level': my_level,
                            'downloaded': downloaded,
                            'uploaded': uploaded,
                            'my_score': 0,
                            'seed': seed,
                            'leech': leech,
                        })
                    if float(ratio) < 1:
                        msg = f'{site.name} 分享率 {ratio} 过低，请注意'
                        # 消息发送
                        toolbox.send_text(title=msg, message=msg)
                    return CommonResponse.success(data=res_gpw)
                elif 'zhuque.in' in site.url:
                    logger.debug(details_html)
                    downloaded = details_html.get('download')
                    uploaded = details_html.get('upload')
                    seeding_size = details_html.get('seedSize')
                    my_bonus = details_html.get('bonus')
                    my_score = details_html.get('seedBonus')
                    seed_days = int(details_html.get('seedTime') / 3600 / 24)
                    ratio = uploaded / downloaded if downloaded > 0 else 'inf'
                    invitation = details_html.get(site.my_invitation_rule)
                    my_level = details_html.get('class').get('name').strip(" ")
                    seed = details_html.get('seeding')
                    leech = details_html.get('leeching')
                    if float(ratio) < 1:
                        msg = f'{site.name} 分享率 {ratio} 过低，请注意'
                        toolbox.send_text(title=msg, message=msg)
                    res_zhuque = SiteStatus.objects.update_or_create(
                        site=my_site,
                        created_at__date__gte=datetime.today(),
                        defaults={
                            'ratio': ratio,
                            'downloaded': downloaded,
                            'uploaded': uploaded,
                            'my_bonus': my_bonus,
                            'my_score': my_score,
                            'invitation': invitation,
                            'seed': seed,
                            'leech': leech,
                            'my_level': my_level,
                            'seed_volume': seeding_size,
                            'seed_days': seed_days
                        })
                    return CommonResponse.success(data=res_zhuque)
                else:
                    logger.debug(f'下载数目字符串：{details_html.xpath(site.my_leech_rule)}')
                    logger.debug(f'上传数目字符串：{details_html.xpath(site.my_seed_rule)}')
                    leech = re.sub(r'\D', '', ''.join(details_html.xpath(site.my_leech_rule)).strip())
                    logger.debug(f'当前下载数：{leech}')
                    seed = ''.join(details_html.xpath(site.my_seed_rule)).strip()
                    logger.debug(f'当前做种数：{seed}')
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
                    downloaded = toolbox.FileSizeConvert.parse_2_byte(downloaded)
                    uploaded = toolbox.FileSizeConvert.parse_2_byte(uploaded)
                    # 获取邀请信息
                    invitation = ''.join(
                        details_html.xpath(site.my_invitation_rule)
                    ).strip(']:').replace('[', '').strip()
                    logger.debug(f'邀请：{invitation}')
                    if '没有邀请资格' in invitation or '沒有邀請資格' in invitation:
                        invitation = 0
                    elif '/' in invitation:
                        invitation_list = [int(n) for n in invitation.split('/')]
                        invitation = sum(invitation_list)
                    elif '(' in invitation:
                        invitation_list = [int(toolbox.get_decimals(n)) for n in invitation.split('(')]
                        invitation = sum(invitation_list)
                    elif not invitation:
                        invitation = 0
                    else:
                        invitation = int(re.sub('\D', '', invitation))
                    logger.debug(f'当前获取邀请数："{invitation}"')
                    # 获取用户等级信息
                    my_level_1 = ''.join(
                        details_html.xpath(site.my_level_rule)
                    ).replace('_Name', '').replace('fontBold', '').strip(" ").strip()
                    if 'hdcity' in site.url:
                        my_level = my_level_1.replace('[', '').replace(']', '').strip(" ").strip()
                    else:
                        my_level = re.sub(u"([^\u0041-\u005a\u0061-\u007a])", "", my_level_1).strip(" ")
                    my_level = my_level.strip(" ") if my_level != '' else ' '
                    logger.debug('用户等级：{}-{}'.format(my_level_1, my_level))
                    # 获取字符串中的魔力值
                    my_bonus = ''.join(
                        details_html.xpath(site.my_bonus_rule)
                    ).replace(',', '').strip()
                    logger.debug('魔力：{}'.format(details_html.xpath(site.my_bonus_rule)))
                    if my_bonus:
                        my_bonus = toolbox.get_decimals(my_bonus)
                    # 获取做种积分
                    my_score_1 = ''.join(
                        details_html.xpath(site.my_score_rule)
                    ).strip('N/A').replace(',', '').strip()
                    if my_score_1 != '':
                        my_score = toolbox.get_decimals(my_score_1)
                    else:
                        my_score = 0
                    # 获取HR信息
                    hr = ''.join(
                        details_html.xpath(site.my_hr_rule)
                    ).replace('H&R:', '').strip()
                    if site.url in [
                        'https://monikadesign.uk/',
                        'https://pt.hdpost.top/',
                        'https://reelflix.xyz/',
                    ]:
                        hr = hr.replace('\n', '').replace('有效', '').replace(':', '').strip('/').strip()
                    my_hr = hr if hr else '0'
                    logger.debug(f'h&r: "{hr}" ,解析后：{my_hr}')
                    # 做种与下载信息
                    seed = int(toolbox.get_decimals(seed)) if seed else 0
                    leech = int(toolbox.get_decimals(leech)) if leech else 0
                    logger.debug(f'当前上传种子数：{seed}')
                    logger.debug(f'当前下载种子数：{leech}')
                    # 分享率信息
                    if float(downloaded) == 0:
                        ratio = float('inf')
                    else:
                        ratio = round(int(uploaded) / int(downloaded), 3)
                    if ratio <= 1:
                        title = f'{site.name}  站点分享率告警：{ratio}'
                        message = f'{title}  \n'
                        toolbox.send_text(title=title, message=message)
                    logger.debug('站点：{}'.format(site))
                    logger.debug('魔力：{}'.format(my_bonus))
                    logger.debug('积分：{}'.format(my_score if my_score else 0))
                    logger.debug('下载量：{}'.format(toolbox.FileSizeConvert.parse_2_file_size(downloaded)))
                    logger.debug('上传量：{}'.format(toolbox.FileSizeConvert.parse_2_file_size(uploaded)))
                    logger.debug('邀请：{}'.format(invitation))
                    logger.debug('H&R：{}'.format(my_hr))
                    logger.debug('上传数：{}'.format(seed))
                    logger.debug('下载数：{}'.format(leech))
                    defaults = {
                        'ratio': float(ratio) if ratio else 0,
                        'downloaded': int(downloaded),
                        'uploaded': int(uploaded),
                        'my_bonus': float(my_bonus),
                        'my_score': float(
                            my_score) if my_score != '' else 0,
                        'seed': seed,
                        'leech': leech,
                        'invitation': invitation,
                        'publish': 0,  # todo 待获取
                        'seed_days': 0,  # todo 待获取
                        'my_hr': my_hr,
                        'my_level': my_level,
                    }
                    if site.url in [
                        'https://nextpt.net/',
                    ]:
                        # logger.debug(site.hour_sp_rule)
                        res_bonus_hour_list = details_html.xpath(site.my_per_hour_bonus_rule)
                        # logger.debug(details_html)
                        # logger.debug(res_bonus_hour_list)
                        res_bonus_hour = ''.join(res_bonus_hour_list)
                        bonus_hour = toolbox.get_decimals(res_bonus_hour)
                        # 飞天邀请获取
                        logger.info(f'邀请页面：{site.url}Invites')
                        res_next_pt_invite = self.send_request(my_site, f'{site.url}Invites')
                        logger.debug(res_next_pt_invite.text)
                        str_next_pt_invite = ''.join(self.parse(
                            site,
                            res_next_pt_invite,
                            site.my_invitation_rule))
                        logger.debug(f'邀请字符串：{str_next_pt_invite}')
                        list_next_pt_invite = re.findall('\d+', str_next_pt_invite)
                        logger.debug(list_next_pt_invite)
                        invitation = int(list_next_pt_invite[0]) - int(list_next_pt_invite[1])
                        defaults.update({
                            'bonus_hour': bonus_hour,
                            'invitation': invitation,
                        })
                    result = SiteStatus.objects.update_or_create(
                        site=my_site, created_at__date__gte=datetime.today(),
                        defaults=defaults)
                    return CommonResponse.success(data=result)
            except Exception as e:
                # 打印异常详细信息
                message = f'{site.name} 解析做种信息：失败！原因：{e}'
                logger.error(message)
                logger.error(traceback.format_exc(limit=3))
                # raise
                # toolbox.send_text('# <font color="red">' + message + '</font>  \n')
                return CommonResponse.error(msg=message)

    def parse_seeding_html(self, my_site, seeding_html):
        """解析做种页面"""
        site = get_object_or_404(WebSite, id=my_site.site)
        with lock:
            try:
                if 'greatposterwall' in site.url or 'dicmusic' in site.url:
                    logger.debug(seeding_html)
                    mail_str = seeding_html.get("notifications").get("messages")
                    notice_str = seeding_html.get("notifications").get("notifications")
                    mail = int(mail_str) + int(notice_str)
                    if mail > 0:
                        title = f'{site.name} 有{mail}条新短消息，请注意及时查收！'
                        msg = f'### <font color="red">{title}</font>  \n'
                        # 测试发送网站消息原内容
                        # toolbox.send_text(title=title, message=msg)
                    if 'greatposterwall' in site.url:
                        userdata = seeding_html.get('userstats')
                        my_bonus = userdata.get('bonusPoints')
                        # if userdata.get('bonusPoints') else 0
                        seeding_size = userdata.get('seedingSize')
                        # if userdata.get('seedingSize') else 0
                        bonus_hour = userdata.get('seedingBonusPointsPerHour')
                        # if userdata.get('seedingBonusPointsPerHour') else 0
                    if 'dicmusic' in site.url:
                        logger.debug('海豚')
                        """未取得授权前不开放本段代码，谨防ban号
                        bonus_res = self.send_request(my_site, url=site.url + site.page_seeding, timeout=15)
                        sp_str = self.parse(bonus_res, '//h3[contains(text(),"总积分")]/text()')
                        my_bonus = get_decimals(''.join(sp_str))
                        hour_sp_str = self.parse(bonus_res, '//*[@id="bprates_overview"]/tbody/tr/td[3]/text()')
                        my_site.bonus_hour = ''.join(hour_sp_str)
                        seeding_size_str = self.parse(bonus_res,
                                                      '//*[@id="bprates_overview"]/tbody/tr/td[2]/text()')
                        seeding_size = toolbox.FileSizeConvert.parse_2_byte(''.join(seeding_size_str))
                        """
                        my_bonus = 0
                        bonus_hour = 0
                        seeding_size = 0
                    res_gpw = SiteStatus.objects.update_or_create(
                        site=my_site,
                        created_at__date__gte=datetime.today(),
                        defaults={
                            'my_bonus': my_bonus,
                            'my_score': 0,
                            # 做种体积
                            'seed_volume': seeding_size,
                            'bonus_hour': bonus_hour,
                            'mail': mail,
                        })
                    return CommonResponse.success(data=res_gpw)
                else:
                    try:
                        seed_vol_list = seeding_html.xpath(site.my_seed_vol_rule)
                        logger.debug('做种数量seeding_vol：{}'.format(seed_vol_list))
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
                        'https://pt.soulvoice.club/',
                        'https://dajiao.cyou/',
                    ]:
                        # 获取到的是整段，需要解析
                        logger.debug('做种体积：{}'.format(seed_vol_list))
                        if len(seed_vol_list) < 1:
                            seed_vol_all = 0
                        else:
                            seeding_str = ''.join(
                                seed_vol_list
                            ).replace('\xa0', ':').replace('i', '')
                            logger.debug('做种信息字符串：{}'.format(seeding_str))
                            if ':' in seeding_str:
                                seed_vol_size = seeding_str.split(':')[-1].strip()
                            if '：' in seeding_str:
                                seed_vol_size = seeding_str.split('：')[-1].strip()
                            if '&nbsp;' in seeding_str:
                                seed_vol_size = seeding_str.split('&nbsp;')[-1].strip()
                            if 'No record' in seeding_str:
                                seed_vol_size = 0
                            seed_vol_all = toolbox.FileSizeConvert.parse_2_byte(seed_vol_size)
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
                        seed_vol_all = toolbox.FileSizeConvert.parse_2_byte(seed_vol_size)
                        logger.debug(f'做种信息: {seed_vol_all}')
                    elif 'club.hares.top' in site.url:
                        logger.debug(f'白兔做种信息：{seeding_html}')
                        seed_vol_size = seeding_html.get('size')
                        logger.debug(f'白兔做种信息：{seed_vol_size}')
                        seed_vol_all = toolbox.FileSizeConvert.parse_2_byte(seed_vol_size)
                        logger.debug(f'白兔做种信息：{seed_vol_all}')
                    else:
                        if len(seed_vol_list) > 0 and site.url not in ['https://nextpt.net/']:
                            seed_vol_list.pop(0)
                        logger.debug('做种数量seeding_vol：{}'.format(len(seed_vol_list)))
                        # 做种体积
                        seed_vol_all = 0
                        for seed_vol in seed_vol_list:
                            if 'iptorrents.com' in site.url:
                                vol = ''.join(seed_vol.xpath('.//text()'))
                                logger.debug(vol)
                                vol = ''.join(re.findall(r'\((.*?)\)', vol))
                                logger.debug(vol)
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
                            # logger.debug(vol)
                            if not len(vol) <= 0:
                                # U2返回字符串为mib，gib
                                size = toolbox.FileSizeConvert.parse_2_byte(vol.replace('i', ''))
                                if size:
                                    seed_vol_all += size
                                else:
                                    msg = f'{site.name} 获取做种大小失败，请检查规则信息是否匹配？'
                                    logger.warning(msg)
                                    # toolbox.send_text(title=msg, message=msg)
                                    break
                            else:
                                # seed_vol_all = 0
                                pass
                    logger.debug('做种体积：{}'.format(toolbox.FileSizeConvert.parse_2_file_size(seed_vol_all)))
                    res = SiteStatus.objects.update_or_create(
                        site=my_site,
                        created_at__date__gte=datetime.today(),
                        defaults={
                            'seed_volume': seed_vol_all,
                        })
                    return CommonResponse.success(data=res)
            except Exception as e:
                return CommonResponse.error(msg=f'{site.name} 站点做种信息解析错误~')

    def get_torrent_detail(self, my_site, url):
        """
        获取种子详情页数据
        :param my_site:
        :param url:
        :return:
        """
        try:
            site = get_object_or_404(WebSite, id=my_site.site)
            torrent_detail = self.send_request(my_site=my_site, url=url)
            download_url = ''.join(self.parse(site, torrent_detail, site.detail_download_url_rule))
            size = ''.join(self.parse(site, torrent_detail, site.detail_size_rule))
            files_count = ''.join(self.parse(site, torrent_detail, site.detail_count_files_rule))
            return CommonResponse.success(data={
                'subtitle': ''.join(self.parse(site, torrent_detail, site.detail_subtitle_rule)),
                'magnet_url': download_url if download_url.startswith(
                    'http') else f'{site.url}{download_url.lstrip("/")}',
                'size': toolbox.FileSizeConvert.parse_2_byte(size.replace('\xa0', '')),
                'category': ''.join(self.parse(site, torrent_detail, site.detail_category_rule)).strip(),
                'area': ''.join(self.parse(site, torrent_detail, site.detail_area_rule)),
                'files_count': toolbox.get_decimals(files_count),
                # 'hash_string': ''.join(self.parse(site, torrent_detail, site.detail_hash_rule)),
                'sale_status': ''.join(self.parse(site, torrent_detail, site.detail_free_rule)),
                'sale_expire': ''.join(self.parse(site, torrent_detail, site.detail_free_expire_rule)),
                'douban_url': ''.join(self.parse(site, torrent_detail, site.detail_douban_rule)),
                'year_publish': ''.join(self.parse(site, torrent_detail, site.detail_year_publish_rule)),
            })
        except Exception as e:
            logger.error(traceback.format_exc(3))
            return CommonResponse.error(msg=f'网址：{url} 访问失败')

    def get_update_torrent(self, torrent):
        my_site = torrent.site
        website = get_object_or_404(WebSite, id=my_site.site)
        res_detail = self.get_torrent_detail(my_site, f'{website.url}{website.page_detail.format(torrent.tid)}')
        if res_detail.code == 0:
            res = TorrentInfo.objects.update_or_create(
                id=torrent.id,
                defaults=res_detail.data,
            )
            return CommonResponse.success(data=res[0])
        else:
            return res_detail

    def get_hour_sp(self, my_site: MySite, headers={}):
        """获取时魔"""
        site = get_object_or_404(WebSite, id=my_site.site)
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
            if 'iptorrents' in site.url:
                bonus_hour = 0
            else:
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
                    response = self.send_request(my_site=my_site, url=url, header=headers)
                """
                if 'btschool' in site.url:
                    # logger.info(response.text.encode('utf8'))
                    url = self.parse(response, '//form[@id="challenge-form"]/@action[1]')
                    data = {
                        'md': ''.join(self.parse(response, '//form[@id="challenge-form"]/input[@name="md"]/@value')),
                        'r': ''.join(self.parse(response, '//form[@id="challenge-form"]/input[@name="r"]/@value'))
                    }
                    logger.info(data)
                    logger.debug('学校时魔页面url：', url)
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
                # logger.debug('时魔响应：{}'.format(response.content))
                # logger.debug('转为简体的时魔页面：', str(res))
                if 'zhuque.in' in site.url:
                    # 获取朱雀时魔
                    bonus_hour = response.json().get('data').get('E')
                elif site.url in [
                    'https://greatposterwall.com/',
                    'https://dicmusic.club/'
                ]:
                    # 获取朱雀时魔
                    bonus_hour = response.json().get('response').get('userstats').get('seedingBonusPointsPerHour')
                else:
                    if response.status_code == 200:
                        res_list = self.parse(site, response, site.my_per_hour_bonus_rule)
                        if len(res_list) <= 0:
                            CommonResponse.error(msg='时魔获取失败！')
                        if 'u2.dmhy.org' in site.url:
                            res_list = ''.join(res_list).split('，')
                            res_list.reverse()
                        logger.debug('时魔字符串：{}'.format(res_list))
                        if len(res_list) <= 0:
                            message = f'{site.name} 时魔获取失败！'
                            logger.error(message)
                            return CommonResponse.error(msg=message, data=0)
                        bonus_hour = toolbox.get_decimals(res_list[0].replace(',', ''))
                    else:
                        message = f'{site.name} 时魔获取失败！'
                        logger.error(message)
                        return CommonResponse.error(msg=message)
            SiteStatus.objects.update_or_create(
                site=my_site,
                created_at__date__gte=datetime.today(),
                defaults={
                    'bonus_hour': bonus_hour if bonus_hour else 0,
                })
            return CommonResponse.success(data=bonus_hour)
        except Exception as e:
            # 打印异常详细信息
            message = f'{site.name} 时魔获取失败！{e}'
            logger.error(message)
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg=message, data=0)

    def send_torrent_info_request(self, my_site: MySite):
        site = get_object_or_404(WebSite, id=my_site.site)
        url = my_site.torrents
        if not url or len(url) <= 10:
            url = site.url + site.page_torrents.lstrip('/')
        logger.info(f'种子页面链接：{url}')
        try:
            response = self.send_request(my_site, url)
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
            # toolbox.send_text(title=title, message=msg)
            return CommonResponse.error(msg=msg)

    # @transaction.atomic
    def get_torrent_info_list(self, my_site: MySite, response: Response):
        count = 0
        new_count = 0
        torrents = []
        site = get_object_or_404(WebSite, id=my_site.site)
        try:
            with lock:
                trs = self.parse(site, response, site.torrents_rule)
                # logger.debug(f'种子页面：{response.text}')
                # logger.info(trs)
                logger.info(f'{my_site.nickname} 共发现{len(trs)}条种子记录')
                logger.info('=' * 50)
                for tr in trs:
                    logger.debug(tr)
                    # logger.debug(etree.tostring(tr))
                    sale_status = ''.join(tr.xpath(site.torrent_sale_rule))
                    logger.debug('sale_status: {}'.format(sale_status))
                    # 打开免费种刷流时，非免费种子跳过
                    if my_site.brush_free and not sale_status:
                        logger.debug('非免费种子跳过')
                    title_list = tr.xpath(site.torrent_subtitle_rule)
                    logger.debug(title_list)
                    subtitle = ''.join(title_list).strip('剩余时间：').strip('剩餘時間：').replace(
                        '&nbsp;', '').strip('()').strip()
                    title = ''.join(tr.xpath(site.torrent_title_rule)).replace('&nbsp;', '').strip()
                    if not title and not subtitle:
                        logger.error('无名无姓？跳过')
                        continue
                    # sale_status = ''.join(re.split(r'[^\x00-\xff]', sale_status))
                    sale_status = sale_status.replace('tStatus ', '').upper().replace(
                        'FREE', 'Free'
                    ).replace('免费', 'Free').replace(' ', '')
                    # # 下载链接，下载链接已存在则跳过
                    href = ''.join(tr.xpath(site.torrent_magnet_url_rule))
                    logger.debug('href: {}'.format(href))
                    magnet_url = '{}{}'.format(
                        site.url,
                        href.replace('&type=zip', '').replace(site.url, '').lstrip('/')
                    )
                    parsed_url = urlparse(magnet_url)
                    tid = parse_qs(parsed_url.query).get("id")[0]
                    logger.info('magnet_url: {}'.format(magnet_url))
                    # 如果种子有HR，则为否 HR绿色表示无需，红色表示未通过HR考核
                    hr = False if tr.xpath(site.torrent_hr_rule) else True
                    # H&R 种子有HR且站点设置不下载HR种子,跳过，
                    if not hr and not my_site.hr_discern:
                        logger.debug('hr种子，未开启HR跳过')
                    # # 促销到期时间
                    sale_expire = ''.join(tr.xpath(site.torrent_sale_expire_rule))
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
                    logger.debug(sale_expire)
                    if sale_expire.endswith(':'):
                        sale_expire = sale_expire + '00'
                    # 如果促销结束时间为空，则为无限期
                    sale_expire = None if not sale_expire else sale_expire
                    # logger.debug(torrent_info.sale_expire)
                    # # 发布时间
                    on_release = ''.join(tr.xpath(site.torrent_release_rule))
                    # # 做种人数
                    seeders = ''.join(tr.xpath(site.torrent_seeders_rule))
                    # # # 下载人数
                    leechers = ''.join(tr.xpath(site.torrent_leechers_rule))
                    # # # 完成人数
                    completers = ''.join(tr.xpath(site.torrent_completers_rule))
                    # 存在则更新，不存在就创建
                    # logger.debug(type(seeders), type(leechers), type(completers), )
                    # logger.debug(seeders, leechers, completers)
                    # logger.debug(''.join(tr.xpath(site.title_rule)))
                    category = ''.join(tr.xpath(site.torrent_category_rule))
                    file_parse_size = ''.join(tr.xpath(site.torrent_size_rule))
                    # file_parse_size = ''.join(tr.xpath(''))
                    logger.debug(file_parse_size)
                    file_size = toolbox.FileSizeConvert.parse_2_byte(file_parse_size)
                    # subtitle = subtitle if subtitle else title
                    # poster_url = ''.join(tr.xpath(site.torrent_poster_rule))  # 海报链接
                    logger.debug(f'title：{site}\n size: {file_size}\n category：{category}\n '
                                 f'magnet_url：{magnet_url}\n subtitle：{subtitle}\n sale_status：{sale_status}\n '
                                 f'sale_expire：{sale_expire}\n seeders：{seeders}\n leechers：{leechers}\n'
                                 f'H&R：{hr}\n completers：{completers}')
                    result = TorrentInfo.objects.update_or_create(
                        site=my_site,
                        tid=tid,
                        defaults={
                            'category': category,
                            'magnet_url': magnet_url,
                            'title': title,
                            'subtitle': subtitle,
                            # 'detail_url': detail_url,
                            'sale_status': sale_status,
                            'sale_expire': sale_expire,
                            'hr': hr,
                            'published': on_release,
                            'size': file_size,
                            'seeders': int(seeders) if seeders else 0,
                            'leechers': int(leechers) if leechers else 0,
                            'completers': int(completers) if completers else 0,
                        })
                    logger.info('拉取种子：{} {}'.format(site.name, result[0].title))
                    # time.sleep(0.5)
                    if not result[1]:
                        count += 1
                    else:
                        new_count += 1
                        # logger.debug(torrent_info)
                    # HR 与种子推送状态筛选
                    torrent = result[0]
                    if torrent.sale_status.find('Free') >= 0 and torrent.hr and torrent.state == 0:
                        torrents.append(result[0])
                if count + new_count <= 0:
                    return CommonResponse.error(msg='抓取失败或无促销种子！')
                return CommonResponse.success(
                    msg=f'种子抓取成功！新增种子{new_count}条!',
                    data=torrents
                )
        except Exception as e:
            # raise
            title = f'{site.name} 解析种子信息：失败！'
            msg = f'{site.name} 解析种子页面失败！{e}'
            # toolbox.send_text(title=title, message=msg)
            logger.error(msg)
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg=msg)
