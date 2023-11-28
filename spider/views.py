import functools
import logging
import os
import random
import re
import ssl
import threading
import time
import traceback
from datetime import datetime
from multiprocessing.dummy import Pool as ThreadPool
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import cloudscraper
import requests
import toml
from channels.db import database_sync_to_async
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from lxml import etree
from requests import Response, RequestException
from transmission_rpc import TransmissionError

from auxiliary.base import DownloaderCategory
from my_site.models import MySite, SignIn, SiteStatus, TorrentInfo
from toolbox import views as toolbox
from toolbox.schema import CommonResponse
from website.models import WebSite

# Create your views here.

logger = logging.getLogger('ptools')
lock = threading.Lock()
notice = toolbox.parse_toml("notice")
notice_category_enable = notice.get("notice_category_enable", {})
if os.getenv('MYSQL_CONNECTION'):
    cpu_count = os.cpu_count() if os.cpu_count() <= 16 else os.getenv("THREAD_COUNT", 16)
else:
    cpu_count = os.cpu_count() if os.cpu_count() <= 8 else os.getenv("THREAD_COUNT", 8)
pool = ThreadPool(cpu_count)


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
        ]:
            return etree.HTML(response.text).xpath(rules)
        elif site.url in [
            'https://piggo.me/',
        ]:
            return etree.HTML(response.text.encode('utf8')).xpath(rules)
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
        url = f'{my_site.mirror if my_site.mirror_switch else site.url}{site.page_sign_in}'.lstrip('/')
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
            my_site=my_site,
            url=f'{my_site.mirror if my_site.mirror_switch else site.url}{site.page_sign_in}'.lstrip('/'),
            method='post', data=data
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
        mirror = my_site.mirror if my_site.mirror_switch else site.url

        url = mirror + site.page_control_panel.lstrip('/')
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
            url=f'{mirror}{site.page_sign_in}'.lstrip('/'),
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
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        url = mirror + site.page_control_panel.lstrip('/')
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
            url=f'{mirror}{site.page_sign_in}'.lstrip('/'),
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
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        url = mirror + site.page_control_panel.lstrip('/')
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
        #     url=f'{mirror}{site.page_sign_in}',
        #     method=site.sign_in_method,
        #     data={
        #         'csrf': csrf
        #     }
        # )
        cookies = toolbox.cookie2dict(my_site.cookie)
        cookies.update(result.cookies.get_dict())
        logger.debug(cookies)
        sign_res = requests.request(url=f'{mirror}{site.page_sign_in}', verify=False, method='post', cookies=cookies,
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
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        url = f'{mirror}{site.page_sign_in}'.lstrip('/')
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
            url=f'{mirror}{site.page_sign_in.lstrip("/")}?action=show',
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
        mirror = my_site.mirror if my_site.mirror_switch else site.url

        check_url = mirror + site.page_user
        res_check = self.send_request(
            my_site=my_site,
            url=check_url)
        href_sign_in = self.parse(site, res_check, '//a[@href="/plugin_sign-in.php?cmd=show-log"]')
        if len(href_sign_in) >= 1:
            return CommonResponse.success(data={'state': 'false'})
        url = f'{mirror}{site.page_sign_in}'.lstrip('/')
        logger.debug('# 开启验证码！')
        res = self.send_request(my_site=my_site, method='get', url=url)
        logger.debug(res.text.encode('utf-8-sig'))
        img_src = ''.join(self.parse(site, res, '//form[@id="frmSignin"]//img/@src'))
        img_get_url = mirror + img_src
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
            url=f'{mirror}plugin_sign-in.php?cmd=signin', data=data)
        logger.debug('皇后签到返回值：{}  \n'.format(result.text.encode('utf-8-sig')))
        return CommonResponse.success(data=result.json())

    def sign_in_hdsky(self, my_site: MySite):
        """HDSKY签到"""
        site = get_object_or_404(WebSite, id=my_site.site)
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        url = f'{mirror}{site.page_sign_in}'.lstrip('/')
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
            url=f'{mirror}image_code_ajax.php',
            data={
                'action': 'new'
            }).json()
        # img url
        img_get_url = f'{mirror}image.php?action=regimage&imagehash={res.get("code")}'
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
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        url = mirror + site.page_user.format(my_site.user_id)
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
                f'{mirror}{site.page_sign_in}',
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
            mirror = my_site.mirror if my_site.mirror_switch else site.url
            csrf_res = self.send_request(my_site=my_site, url=mirror)
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
            url = f'{mirror}{site.page_sign_in}'
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

    def sign_in_leaves(self, my_site: MySite):
        """
        红叶签到，暂不支持
        :param my_site:
        :return:
        """
        try:
            site = get_object_or_404(WebSite, id=my_site.site)
            mirror = my_site.mirror if my_site.mirror_switch else site.url
            url = mirror + site.page_sign_in.lstrip('/')
            result = self.send_request(
                my_site=my_site,
                url=url,
            )
            # 检测是否已签到
            logger.info(result.content)
            # sign_str = self.parse(site, result, '//span[@id="qiandao"]')
            # logger.debug(sign_str)
            # if len(sign_str) < 1:
            #     return CommonResponse.success(msg=f'{site.name} 已签到，请勿重复操作！！')
            mood_list = [
                "情绪愉悦，充满喜悦和快乐",
                "心情愉快，感到幸福和满足",
                "心情欢畅，感到愉悦和舒适",
                "感受到内心的满足和幸福",
                "情绪高涨，充满激动和期待",
                "情绪激昂，兴奋或激烈的感受",
                "感到放松和安逸，没有压力",
                "感到舒服和宜人",
                "内心安宁，没有波动和激情",
                "心情安定，放心和安心",
                "感到满足和满意，对结果感到满意",
                "为自己的成就感到自豪和满足",
                "感到畅快和痛快，毫不犹豫",
                "感到高兴和喜悦",
                "对别人的帮助或恩情感到感激和感谢",
                "关系和谐，感到和睦和融洽",
                "感到温馨和宽慰，心情舒畅",
                "充满爱和情意",
                "精神饱满，容光焕发",
                "情绪低落，感到忧伤和沉闷",
                "心情受伤，感到悲伤和痛苦",
                "心情低落，感到失望和沮丧",
                "感到疑惑和不安，心情紧张",
                "感到疲惫和精疲力尽",
                "感到烦躁和不耐烦",
                "感到愤怒和气愤",
                "感到恐惧和不安",
                "感到孤独和寂寞"
            ]
            answer_list = [
                "蜜蜂是通过花朵采集花蜜，并将花蜜带回蜂巢。",
                "地球的外部结构包括地壳、地幔和地核。",
                "太阳是太阳系的中心星体，是由氢和氦等元素组成的巨大热核反应堆。",
                "光的传播速度是每秒约30万公里，它在真空中传播得更快。",
                "DNA是一种分子，包含生物体遗传信息的编码。",
                "水的化学式是H2O，由氢原子和氧原子组成。",
                "地球上最高的山峰是珠穆朗玛峰，位于喜马拉雅山脉。",
                "人类的骨骼系统由206块骨头组成，提供身体结构和支持。",
                "植物通过光合作用将阳光转化为能量，同时释放氧气。",
                "牛顿三大运动定律描述了物体的运动规律和力的作用关系。",
                "宇宙大爆炸理论是关于宇宙起源的一种科学理论。",
                "地球绕太阳运行一周的时间大约是365.25天，所以闰年有366天。",
                "蝴蝶是昆虫中的一种，具有独特的鳞状翅膀和蜡样外壳。",
                "地球上最大的洋是太平洋，占地球表面积的约30%。",
                "人类的心脏位于胸腔中，是泵血和循环系统的中心。",
                "地球上最长的河流是尼罗河，位于非洲大陆。",
                "昆虫是地球上数量最多的动物类别，约有100万已知种类。",
                "人类的大脑是控制思维、感觉和行为的中枢器官。",
                "月球是地球的卫星，是人类探索和观测的对象之一。",
                "地球是第三颗离太阳最近的行星，也是人类居住的家园。",
                "鱼是一类生活在水中的脊椎动物，有鳞和鳍。",
                "地球的大气层由氮、氧、氩和其他气体组成，保护地球并维持气候。",
                "人类的眼睛是感知光线和视觉的器官。",
                "Photosynthesis is the process by which plants convert sunlight into energy and produce oxygen.",
                "The theory of relativity, proposed by Albert Einstein, describes the relationship between space, time, and gravity.",
                "The human respiratory system consists of organs such as the lungs, trachea, and diaphragm, which are responsible for breathing and gas exchange.",
                "The Great Wall of China is an ancient fortification that stretches over 13,000 miles and was built to protect against invasions.",
                "Plate tectonics is the scientific theory that explains the movement of Earth's lithospheric plates and the formation of continents, mountains, and volcanoes.",
                "The concept of supply and demand is a fundamental principle in economics that describes the relationship between the availability of a product or service and its demand by consumers.",
                "The water cycle is the continuous movement of water on Earth, involving processes such as evaporation, condensation, precipitation, and runoff.",
                "The human immune system is a complex network of cells, tissues, and organs that protects the body against pathogens and foreign substances.",
                "The theory of evolution, proposed by Charles Darwin, explains how species change and adapt over time through the process of natural selection.",
                "The concept of inertia, introduced by Isaac Newton, states that an object at rest tends to stay at rest, and an object in motion tends to stay in motion unless acted upon by an external force.",
                "The Mona Lisa, painted by Leonardo da Vinci, is one of the most famous and iconic artworks in the world.",
                "The process of cellular respiration is how cells convert glucose and oxygen into energy, carbon dioxide, and water.",
                "The human digestive system includes organs such as the stomach, intestines, and liver, which break down food and absorb nutrients.",
                "The theory of electromagnetism, formulated by James Clerk Maxwell, describes the relationship between electricity and magnetism.",
                "The concept of gravity, described by Sir Isaac Newton, explains the force of attraction between objects with mass.",
                "The human nervous system consists of the brain, spinal cord, and nerves, and is responsible for transmitting signals throughout the body.",
                "The Renaissance was a period of cultural and intellectual rebirth in Europe, characterized by advancements in art, literature, science, and philosophy.",
                "The greenhouse effect is the process by which certain gases in Earth's atmosphere trap heat and contribute to global warming.",
                "The human skeletal system provides support, protection, and movement, with bones connected by joints and held together by ligaments.",
                "The concept of entropy, introduced in thermodynamics, refers to the measure of disorder or randomness in a system.",
                "The theory of quantum mechanics describes the behavior of matter and energy at the atomic and subatomic levels.",
                "The human reproductive system includes organs such as the ovaries, uterus, and testes, and is responsible for reproduction and the production of offspring.",
                "The concept of elasticity in economics refers to the responsiveness of demand or supply to changes in price or other factors.",
                "The concept of cultural diversity recognizes and values the presence of different cultures, languages, and traditions within a society.",
            ]
            # 解析form表单
            form = self.parse(site, result, '//td/h2[contains(text(), "签到")]/following::form[1]')[0]

            # 构造表单数据
            form_data = {}
            for input_element in form.xpath(".//input"):
                field_name = input_element.get("name")
                field_value = input_element.get("value")
                form_data[field_name] = field_value

            # 添加其他需要的字段和值
            form_data["character"] = random.choice(answer_list)
            form_data["mood"] = random.choice(mood_list)
            logger.info(f'红叶签到参数：{form_data}')

            sign_res = self.send_request(
                my_site=my_site,
                url=url,
                method='post',
                data=form_data,
            )
            logger.info(f'红叶签到反馈：{sign_res.content}')
            return CommonResponse.success(
                msg='你还需要继续努力哦！此次签到，你获得了魔力奖励：{}'
            )
        except Exception as e:
            logger.error(traceback.format_exc(3))
            return CommonResponse.error(
                msg=f'签到失败！: {e}'
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
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        logger.info(f'{site.name} 开始签到')
        signin_today = my_site.signin_set.filter(created_at__date__gte=datetime.today()).first()
        # 如果已有签到记录
        if signin_today:
            if signin_today.sign_in_today is True:
                return CommonResponse.success(msg=f'{my_site.nickname} 已签到，请勿重复签到！')
        else:
            signin_today = SignIn(site=my_site, created_at=datetime.now())
        url = f'{mirror}{site.page_sign_in}'.lstrip('/')
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
            # if 'leaves.red' in site.url:
            # 红叶签到，暂不支持
            #     result = self.sign_in_leaves(my_site)
            # if result.code == 0:
            #     signin_today.sign_in_today = True
            #     signin_today.sign_in_info = result.msg
            #     signin_today.save()
            # return result
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
            if 'hdarea' in site.url:
                res = self.send_request(my_site=my_site,
                                        method='post',
                                        url=url,
                                        data={'action': 'sign_in'}, )
                logger.info(res.text)
                if res.text.find('已连续签到') >= 0 or res.text.find('请不要重复签到哦！') >= 0:
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
                'https://wintersakura.net/',
                'https://hudbt.hust.edu.cn/',
            ]:
                # 单独发送请求，解决冬樱签到问题
                logger.info(url)
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
                    message = res.json().get('message').replace('\n', '')
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
                    if 'index.php?action=addbonus' in location:
                        res = self.send_request(my_site=my_site, url=f'{mirror}{location.lstrip("/")}')
                        logger.info(res.content)
                # sign_in_text = self.parse(site, res, '//a[@href="index.php"]/font//text()')
                # sign_in_stat = self.parse(site, res, '//a[contains(@href,"addbouns")]')
                sign_in_text = self.parse(site, res, site.sign_info_content)
                sign_in_stat = self.parse(site, res, '//a[contains(@href,"index.php?action=addbonus")]')
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
                message = f'{my_site} 签到返回信息：{title} {content}'
                logger.info(message)
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
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        logger.info(f'{site.name} 开始获取cookie！')
        session = requests.Session()
        headers = {
            'user-agent': my_site.user_agent
        }
        res = session.get(url=mirror, headers=headers)
        validator = ''.join(self.parse(site, res, '//input[@name="validator"]/@value'))
        login_url = ''.join(self.parse(site, res, '//form/@action'))
        login_method = ''.join(self.parse(site, res, '//form/@method'))
        data = toml.load('db/ptools.toml')
        filelist = data.get('filelist')
        username = filelist.get('username')
        password = filelist.get('password')
        login_res = session.request(
            url=f'{mirror}{login_url}',
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
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        user_detail_url = f'{mirror}{site.page_user.lstrip("/").format(my_site.user_id)}'
        logger.info(f'{site.name} 开始抓取站点个人主页信息，网址：{user_detail_url}')
        csrf_res = self.send_request(my_site=my_site, url=mirror)
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
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        mail_check = len(details_html.xpath(site.my_mailbox_rule))
        if 'zhuque.in' in site.url:
            mail_res = self.send_request(my_site=my_site, url=f'{mirror}api/user/getMainInfo', header=header)
            logger.debug(f'新消息: {mail_res.text}')
            mail_data = mail_res.json().get('data')
            mail = mail_data.get('unreadAdmin') + mail_data.get('unreadInbox') + mail_data.get('unreadSystem')
            if mail > 0:
                title = f'{site.name}有{mail}条新消息！'
                toolbox.send_text(title=title, message=title)
        logger.info(f' 短消息：{mail_check}')
        res = SiteStatus.objects.update_or_create(
            site=my_site,
            created_at__date__gte=datetime.today(),
        )
        status = res[0]
        if mail_check > 0:
            title = f'{site.name}有新消息！'

            if 'torrentleech' in site.url:
                mail_count = int(''.join(details_html.xpath(site.my_mailbox_rule)))
                if mail_count <= 0:
                    status.mail = 0
                    status.save()
                    return

            if not notice_category_enable.get("message"):
                toolbox.send_text(title=title, message=title)
                status.mail = 1
                status.save()
                return

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
                    'https://wintersakura.net/',
                ]:
                    # 单独发送请求，解决冬樱签到问题
                    message_res = requests.get(url=f'{mirror}{site.page_message}', verify=False,
                                               cookies=toolbox.cookie2dict(my_site.cookie),
                                               headers={
                                                   'user-agent': my_site.user_agent
                                               })
                else:
                    message_res = self.send_request(my_site, url=f'{mirror}{site.page_message}')
                logger.info(f'PM消息页面：{message_res}')
                mail_list = self.parse(site, message_res, site.my_message_title)
                mail_list = [f'#### {mail.strip()} ...\n' for mail in mail_list]
                logger.debug(mail_list)
                mail = "".join(mail_list)
                logger.info(f'PM信息列表：{mail}')
                # 测试发送网站消息原内容
                message = f'\n# {site.name} 短消息  \n> 只显示第一页哦\n{mail}'
                message_list += message
            status.mail = len(mail_list)
            status.save()
            title = f'{site.name}有{len(mail_list)}条新消息！'
            toolbox.send_text(title=title, message=message_list)
        else:
            status.mail = 0
            status.save()

    def get_notice_info(self, my_site: MySite, details_html):
        """获取站点公告信息"""
        site = get_object_or_404(WebSite, id=my_site.site)
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        if site.url in [
            'https://monikadesign.uk/',
            'https://pt.hdpost.top/',
            'https://reelflix.xyz/',
        ]:
            pass
        else:
            notice_check = len(details_html.xpath(site.my_notice_rule))
            logger.debug(f'{site.name} 公告：{notice_check} ')

            if notice_check > 0:
                title = f'{site.name}有新公告！'

                if not notice_category_enable.get("announcement"):
                    toolbox.send_text(title=title, message=title)
                    return
                if site.url in [
                    'https://totheglory.im/',
                ]:
                    toolbox.send_text(title=title, message=title)
                else:
                    notice_str = ''.join(details_html.xpath(site.my_notice_rule))
                    notice_count = re.sub(u"([^\u0030-\u0039])", "", notice_str)
                    notice_count = int(notice_count) if notice_count else 0
                    message_list = ''
                    if notice_count > 0:
                        logger.info(f'{site.name} 站点公告')
                        if site.url in [
                            'https://hdchina.org/',
                            'https://hudbt.hust.edu.cn/',
                            'https://wintersakura.net/',
                        ]:
                            # 单独发送请求，解决冬樱签到问题
                            notice_res = requests.get(url=f'{mirror}{site.page_index}', verify=False,
                                                      cookies=toolbox.cookie2dict(my_site.cookie),
                                                      headers={
                                                          'user-agent': my_site.user_agent
                                                      })
                        else:
                            notice_res = self.send_request(my_site, url=f'{mirror}{site.page_index}')
                        # notice_res = self.send_request(my_site, url=mirror)
                        logger.debug(f'公告信息 {notice_res}')
                        notice_list = self.parse(site, notice_res, site.my_notice_title)
                        content_list = self.parse(
                            site,
                            notice_res,
                            site.my_notice_content,
                        )
                        logger.debug(f'公告信息：{notice_list}')
                        notice_list = [n.xpath(
                            "string(.)", encoding="utf-8"
                        ).strip("\n").strip("\r").strip() for n in notice_list]
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
                        message_list += f'# {site.name} 公告  \n## {notice}'
                        title = f'{site.name}有{notice_count}条新公告！'
                        toolbox.send_text(title=title, message=message_list)

    def get_userinfo_html(self, my_site: MySite, headers: dict):
        """请求抓取数据相关页面"""
        site = get_object_or_404(WebSite, id=my_site.site)
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        user_detail_url = mirror + site.page_user.lstrip('/').format(my_site.user_id)
        logger.info(f'{site.name} 开始抓取站点个人主页信息，网址：{user_detail_url}')
        logger.info(f'当前站点 URL：{site.url}')
        if site.url in [
            'https://hdchina.org/',
            'https://hudbt.hust.edu.cn/',
            'https://wintersakura.net/',
        ]:
            # 单独发送请求，解决冬樱签到问题
            user_detail_res = requests.get(url=user_detail_url, verify=False,
                                           cookies=toolbox.cookie2dict(my_site.cookie),
                                           headers={
                                               'user-agent': my_site.user_agent
                                           })

        else:
            user_detail_res = self.send_request(my_site=my_site, url=user_detail_url, header=headers)
        logger.info(f"个人信息页面：{user_detail_res.status_code}")
        logger.info(f"个人信息页面：{user_detail_res.text}")
        if site.url in [
            'https://piggo.me/',
        ]:
            logger.debug('猪猪')
            html = user_detail_res.text
            if 'window.location.href' in html:
                pattern = r'href ="(.*?)"; </script>'
                match = re.search(pattern, html, re.DOTALL)
                html_code = match.group(1)
                logger.debug(html_code)
                user_detail_url = f'{site.url}{html_code.lstrip("/")}'
                user_detail_res = self.send_request(my_site=my_site, url=user_detail_url, header=headers)
                logger.info(f"个人信息页面：{user_detail_res.status_code}")
                logger.info(f"个人信息页面：{user_detail_res.text}")
        if user_detail_res.status_code != 200:
            msg = f'{site.name} 个人主页访问错误，错误码：{user_detail_res.status_code}'
            logger.debug(msg)
            return CommonResponse.error(msg=msg)
        if site.url in [
            'https://greatposterwall.com/', 'https://dicmusic.com/',
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
        elif site.url in [
            'https://piggo.me/',
        ]:
            logger.debug('猪猪')
            details_html = etree.HTML(user_detail_res.text.encode('utf8'))
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
                        res = self.send_request(my_site=my_site, url=mirror + location.lstrip('/'), delay=25)
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
        res = self.parse_userinfo_html(my_site=my_site, details_html=details_html)
        if res.code != 0:
            return res
        return CommonResponse.success(data=details_html)

    def get_seeding_html(self, my_site: MySite, headers: dict, details_html=None):
        """请求做种数据相关页面"""
        site = get_object_or_404(WebSite, id=my_site.site)
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        seeding_detail_url = mirror + site.page_seeding.lstrip('/').format(my_site.user_id)
        logger.info(f'{site.name} 开始抓取站点做种信息，网址：{seeding_detail_url}')
        if site.url in [
            'https://greatposterwall.com/', 'https://dicmusic.com/'
        ]:
            seeding_detail_res = self.send_request(my_site=my_site, url=mirror + site.page_mybonus).json()
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
            # logger.info(details_html.content)
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
                'https://wintersakura.net/',
                'https://hudbt.hust.edu.cn/',
            ]:
                logger.info(f"{site.name} 抓取做种信息")
                # 单独发送请求，解决冬樱签到问题
                seeding_detail_res = requests.get(url=seeding_detail_url, verify=False,
                                                  cookies=toolbox.cookie2dict(my_site.cookie),
                                                  headers={
                                                      'user-agent': my_site.user_agent
                                                  })

            else:
                seeding_detail_res = self.send_request(my_site=my_site, url=seeding_detail_url, header=headers,
                                                       delay=25)
            logger.debug('做种信息：{}'.format(seeding_detail_res.text))
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
        err_msg = []
        try:
            status_today = my_site.sitestatus_set.filter(created_at__date__gte=datetime.today()).first()
            if not status_today:
                status_today = SiteStatus(site=my_site)
                status_latest = my_site.sitestatus_set.order_by('created_at').last()
                logger.info(f'status_latest: {status_latest}')
                if status_latest:
                    logger.info(f'status_latest: {status_latest.my_level}')
                    status_today.uploaded = status_latest.uploaded
                    status_today.downloaded = status_latest.downloaded
                    status_today.ratio = status_latest.ratio
                    status_today.my_bonus = status_latest.my_bonus
                    status_today.my_score = status_latest.my_score
                    status_today.seed_volume = status_latest.seed_volume
                    status_today.my_level = status_latest.my_level
                status_today.save()
            headers = {}
            if site.url in [
                'https://hdchina.org/',
                'https://hudbt.hust.edu.cn/',
                'https://wintersakura.net/',
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
                return CommonResponse.error(msg=detail_msg)
            # 解析注册时
            toolbox.get_time_join(my_site, details_html.data)
            # 发送请求，请求做种信息页面
            if site.url not in [
                'https://zhuque.in/',
            ]:
                seeding_html = self.get_seeding_html(my_site, headers=headers, details_html=details_html.data)
                if seeding_html.code != 0:
                    seeding_msg = f'做种页面访问失败!'
                    err_msg.append(seeding_msg)
                    logger.warning(f'{my_site.nickname} {seeding_msg}')
            # 请求时魔页面,信息写入数据库
            hour_bonus = self.get_hour_sp(my_site, headers=headers)
            if hour_bonus.code != 0:
                bonus_msg = f'时魔获取失败!'
                err_msg.append(bonus_msg)
                logger.warning(f'{my_site.nickname} {bonus_msg}')
            # 请求邮件页面，直接推送通知到手机
            if site.url not in [
                'https://dicmusic.com/',
                'https://greatposterwall.com/',
                'https://zhuque.in/',
            ]:
                if details_html.code == 0:
                    # 请求公告信息，直接推送通知到手机
                    self.get_notice_info(my_site, details_html.data)
                    # 请求邮件信息,直接推送通知到手机
                    self.get_mail_info(my_site, details_html.data, header=headers)

            # return self.parse_status_html(my_site, data)
            status = my_site.sitestatus_set.latest('created_at')
            if len(err_msg) <= 3:
                return CommonResponse.success(
                    msg=f'{my_site.nickname} 数据更新完毕! {("🆘 " + " ".join(err_msg)) if len(err_msg) > 0 else ""}',
                    data=status)
            return CommonResponse.error(msg=f'{my_site.nickname} 数据更新失败! 🆘 {" ".join(err_msg)}')
        except RequestException as nce:
            msg = f'🆘 与网站 {my_site.nickname} 建立连接失败，请检查网络？？'
            logger.error(msg)
            logger.error(traceback.format_exc(limit=5))
            return CommonResponse.error(msg=msg)
        except Exception as e:
            message = f'🆘 {my_site.nickname} 统计个人数据失败！原因：{err_msg} {e}'
            logger.error(message)
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg=message)

    def parse_userinfo_html(self, my_site, details_html):
        """解析个人主页"""
        site = get_object_or_404(WebSite, id=my_site.site)
        mirror = my_site.mirror if my_site.mirror_switch else site.url

        with lock:
            try:
                if 'greatposterwall' in site.url or 'dicmusic' in site.url:
                    logger.debug(details_html)
                    stats = details_html.get('stats')
                    downloaded = stats.get('downloaded')
                    uploaded = stats.get('uploaded')
                    ratio_str = stats.get('ratio').replace(',', '')
                    ratio = 'inf' if ratio_str == '∞' else ratio_str
                    if os.getenv("MYSQL_CONNECTION") and ratio == 'inf':
                        ratio = 0
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
                    if 0 < float(ratio) < 1:
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
                    if os.getenv("MYSQL_CONNECTION") and ratio == 'inf':
                        ratio = 0
                    invitation = details_html.get(site.my_invitation_rule)
                    my_level = details_html.get('class').get('name').strip(" ")
                    seed = details_html.get('seeding')
                    leech = details_html.get('leeching')
                    if 0 < float(ratio) < 1:
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
                    leech_status = details_html.xpath(site.my_leech_rule)
                    seed_status = details_html.xpath(site.my_seed_rule)
                    msg = f'下载数目字符串：{leech_status} \n  上传数目字符串：{seed_status}'
                    if len(leech_status) + len(seed_status) <= 0 and site.url.find('hd-space') < 0:
                        err_msg = f'{my_site.nickname} 获取用户数据失败：{msg}'
                        logger.error(err_msg)
                        return CommonResponse.error(msg=err_msg)
                    logger.info(msg)
                    leech = re.sub(r'\D', '', ''.join(details_html.xpath(site.my_leech_rule)).strip())
                    logger.debug(f'当前下载数：{leech}')
                    seed = ''.join(details_html.xpath(site.my_seed_rule)).strip()
                    logger.debug(f'当前做种数：{seed}')

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
                    ).replace(
                        'UserClass_Name', ''
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
                    ).replace('H&R:', '').replace("  ", "").strip()
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
                        if os.getenv("MYSQL_CONNECTION"):
                            ratio = 0
                    else:
                        ratio = round(int(uploaded) / int(downloaded), 3)
                    if 0 < ratio <= 1:
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
                        res_next_pt_invite = self.send_request(my_site, f'{mirror}Invites')
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
                        'https://xingtan.one/',
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
                        'https://leaves.red/',
                        'https://www.htpt.cc/',
                        'https://pt.btschool.club/',
                        'https://azusa.wiki/',
                        'https://pt.2xfree.org/',
                        'http://www.oshen.win/',
                        'https://sharkpt.net/',
                        'https://pt.soulvoice.club/',
                        'https://dajiao.cyou/',
                        'https://www.okpt.net/',
                        'https://pandapt.net/',
                        'https://ubits.club/',
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
                        'https://hd-space.org/',
                        'https://filelist.io/',
                        'https://www.pttime.org/',
                        'https://totheglory.im/',
                        'https://pt.keepfrds.com/',
                        'https://springsunday.net/',
                    ]:
                        # 无需解析字符串
                        seed_vol_size = ''.join(
                            seeding_html.xpath(site.my_seed_vol_rule)
                        ).replace('i', '').replace('&nbsp;', ' ')
                        logger.debug('做种信息字符串：{}'.format(seed_vol_size))
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
                            if len(vol) > 0:
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

    def get_torrent_detail(self, torrent_id: int, my_site: MySite, website: WebSite):
        """
        获取种子详情页数据
        :param website:
        :param torrent_id:
        :param my_site:
        :return:
        """
        try:
            mirror = my_site.mirror if my_site.mirror_switch else website.url
            detail_url = f'{mirror}{website.page_detail.format(torrent_id)}'
            torrent_detail = self.send_request(my_site=my_site, url=detail_url)
            download_url = ''.join(self.parse(website, torrent_detail, website.detail_download_url_rule))
            size = ''.join(self.parse(website, torrent_detail, website.detail_size_rule))
            files_count = ''.join(self.parse(website, torrent_detail, website.detail_count_files_rule))
            return CommonResponse.success(data={
                'title': ''.join(self.parse(website, torrent_detail, website.detail_title_rule)),
                'subtitle': ''.join(self.parse(website, torrent_detail, website.detail_subtitle_rule)),
                'magnet_url': download_url if download_url.startswith(
                    'http') else f'{mirror}{download_url.lstrip("/")}',
                'size': toolbox.FileSizeConvert.parse_2_byte(size.replace('\xa0', '')),
                'category': ''.join(self.parse(website, torrent_detail, website.detail_category_rule)).strip(),
                'tags': ''.join(self.parse(website, torrent_detail, website.detail_tags_rule)),
                'files_count': toolbox.get_decimals(files_count),
                'hash_string': ''.join(self.parse(website, torrent_detail, website.detail_hash_rule)),
                'sale_status': ''.join(self.parse(website, torrent_detail, website.detail_free_rule)),
                'sale_expire': ''.join(self.parse(website, torrent_detail, website.detail_free_expire_rule)),
                'douban_url': ''.join(self.parse(website, torrent_detail, website.detail_douban_rule)),
                'imdb_url': ''.join(self.parse(website, torrent_detail, website.detail_imdb_rule)),
                'poster': ''.join(self.parse(website, torrent_detail, website.detail_poster_rule)),
            })
        except Exception as e:
            logger.error(traceback.format_exc(3))
            return CommonResponse.error(msg=f'{website.name} 种子: {torrent_id} 详情页访问失败')

    def get_update_torrent(self, torrent):
        my_site = torrent.site
        website = get_object_or_404(WebSite, id=my_site.site)
        mirror = my_site.mirror if my_site.mirror_switch else website.url
        res_detail = self.get_torrent_detail(my_site, f'{mirror}{website.page_detail.format(torrent.tid)}')
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
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        url = mirror + site.page_mybonus
        if site.url in [
            'https://www.torrentleech.org/',
        ]:
            return CommonResponse.success(data=0)
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
                    'https://wintersakura.net/',
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
                        url=mirror + ''.join(url).lstrip('/'),
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
                    'https://dicmusic.com/'
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
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        url = my_site.torrents
        if not url or len(url) <= 10:
            url = mirror + site.page_torrents.lstrip('/')
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

    def search_torrents(self, my_site: MySite, key: str):
        site = get_object_or_404(WebSite, id=my_site.site)
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        logger.info(f"{site.name} 开始搜索 {key}")
        url = f'{mirror}{site.page_search.format(key)}'
        try:
            response = self.send_request(my_site, url)
            if response.status_code == 200:
                return CommonResponse.success(data=(my_site, response))
            elif response.status_code == 503:
                return CommonResponse.error(msg=f"{site.name} 我可能碰上CF盾了")
            else:
                return CommonResponse.error(msg=f"{site.name} 网站访问失败")
        except Exception as e:
            # raise
            title = f'{site.name} 网站访问失败'
            msg = f'{site.name} 网站访问失败！原因：{e}'
            # 打印异常详细信息
            logger.error(msg)
            logger.error(traceback.format_exc(limit=3))
            # toolbox.send_text(title=title, message=msg)
            return CommonResponse.error(msg=msg)

    @database_sync_to_async
    def get_website(self, my_site):  # This is a synchronous function
        return get_object_or_404(WebSite, id=my_site.site)

    async def parse_search_result(self, my_site: MySite, response: Response):
        """
        解析搜索结果
        :param my_site:
        :param response:
        :return:
        """
        # site = get_object_or_404(WebSite, id=my_site.site)
        site = await self.get_website(my_site)  # Use the async function
        mirror = my_site.mirror if my_site.mirror_switch else site.url
        logger.info(f"{site.name} 开始解析搜索结果")
        torrents = []
        try:
            trs = self.parse(site, response, site.torrents_rule)
            logger.info(f'{my_site.nickname} 共发现{len(trs)}条种子记录')
            logger.info('=' * 50)
            for tr in trs:
                logger.debug(tr)
                # logger.debug(etree.tostring(tr))
                sale_status = ''.join(tr.xpath(site.torrent_sale_rule))
                logger.debug('sale_status: {}'.format(sale_status))

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
                    mirror,
                    href.replace('&type=zip', '').replace(mirror, '').lstrip('/')
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
                # 发布时间
                on_release = ''.join(tr.xpath(site.torrent_release_rule))

                if site.url.find("totheglory") > 0:
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
                    on_release = ' '.join(tr.xpath(site.torrent_release_rule))
                logger.debug(sale_expire)
                if sale_expire.endswith(':'):
                    sale_expire = sale_expire + '00'
                # 如果促销结束时间为空，则为无限期
                sale_expire = None if not sale_expire else sale_expire
                # logger.debug(torrent_info.sale_expire)

                # 做种人数
                seeders = ''.join(tr.xpath(site.torrent_seeders_rule)).replace(',', '')
                # 下载人数
                leechers = ''.join(tr.xpath(site.torrent_leechers_rule)).replace(',', '')
                # 完成人数
                completers = ''.join(tr.xpath(site.torrent_completers_rule)).replace(',', '')
                # 存在则更新，不存在就创建
                # logger.debug(type(seeders), type(leechers), type(completers), )
                # logger.debug(seeders, leechers, completers)
                # logger.debug(''.join(tr.xpath(site.title_rule)))
                category = ''.join(tr.xpath(site.torrent_category_rule)).replace("promotion-tag-", "")
                file_parse_size = ''.join(tr.xpath(site.torrent_size_rule))
                # file_parse_size = ''.join(tr.xpath(''))
                logger.debug(file_parse_size)
                file_size = toolbox.FileSizeConvert.parse_2_byte(file_parse_size)
                # subtitle = subtitle if subtitle else title
                poster_url = ''.join(tr.xpath(site.torrent_poster_rule))  # 海报链接
                logger.debug(f'title：{title}\n size: {file_size}\n category：{category}\n '
                             f'magnet_url：{magnet_url}\n subtitle：{subtitle}\n sale_status：{sale_status}\n '
                             f'sale_expire：{sale_expire}\n seeders：{seeders}\n leechers：{leechers}\n'
                             f'H&R：{hr}\n completers：{completers}')
                torrent = {
                    'site': my_site.site,
                    'tid': tid,
                    'poster_url': poster_url,
                    'category': category,
                    'magnet_url': magnet_url,
                    'detail_url': f'{mirror}{site.page_detail.format(tid)}',
                    'title': title[:255],
                    'subtitle': subtitle[:255],
                    'sale_status': sale_status,
                    'sale_expire': sale_expire,
                    'hr': hr,
                    'published': on_release,
                    'size': file_size,
                    'seeders': int(seeders) if seeders else 0,
                    'leechers': int(leechers) if leechers else 0,
                    'completers': int(completers) if completers else 0,
                }
                logger.info(torrent)
                logger.info(len(torrent))
                torrents.append(torrent)
            return CommonResponse.success(data=torrents)
        except Exception as e:
            # raise
            title = f'{site.name} 解析种子信息：失败！'
            msg = f'{site.name} 解析种子页面失败！{e}'
            # toolbox.send_text(title=title, message=msg)
            logger.error(msg)
            logger.error(traceback.format_exc(limit=3))
            return CommonResponse.error(msg=msg)

    @staticmethod
    def parse_torrent_list(tr, site, my_site):
        sale_status = ''.join(tr.xpath(site.torrent_sale_rule))
        logger.debug('sale_status: {}'.format(sale_status))

        title_list = tr.xpath(site.torrent_subtitle_rule)
        logger.debug(title_list)
        subtitle = ''.join(title_list).strip('剩余时间：').strip('剩餘時間：').replace(
            '&nbsp;', '').strip('()').strip()
        title = ''.join(tr.xpath(site.torrent_title_rule)).replace('&nbsp;', '').strip()
        if not title and not subtitle:
            msg = f'未获取到标题与副标题，跳过本条消息！'
            logger.error(msg)
            return CommonResponse.error(msg=msg)
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
        logger.info('magnet_url: {}'.format(magnet_url))
        if site.url in [
            'https://totheglory.im/',
        ]:
            id_pattern = r'/dl/(\d+)/'
            tid = re.search(id_pattern, href).group(1)
        else:
            parsed_url = urlparse(magnet_url)
            query_params = parse_qs(parsed_url.query)
            if site.url in [
                'https://greatposterwall.com/',
                'https://dicmusic.com/',
            ]:
                query_params.pop('authkey', None)
                query_params.pop('torrent_pass', None)
                tid = query_params.get("id")[0]
                parsed_url = parsed_url._replace(query=urlencode(query_params, doseq=True))
                magnet_url = urlunparse(parsed_url)
            else:
                tid = query_params.get("id")[0]
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
            # 补足9位
            logger.info(f'促销时间字符串：{time_array}')
            if len(time_array) == 5:
                time_array.extend([0, 0, 0, 0])
                # 转化为标准时间字符串
                sale_expire = time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.struct_time(tuple([int(x) for x in time_array]))
                )
            else:
                sale_expire = None
        if site.url in [
            'https://kp.m-team.cc/',
        ]:
            # 限時：1時39分
            try:
                sale_expire = toolbox.calculate_expiry_time_from_string(sale_expire).strftime(
                    '%Y-%m-%d %H:%M:%S')
            except Exception as e:
                sale_expire = ''
        logger.debug(sale_expire)
        if sale_expire.endswith(':'):
            sale_expire = sale_expire + '00'
        # 如果促销结束时间为空，则为无限期
        sale_expire = None if not sale_expire else sale_expire
        # logger.debug(torrent_info.sale_expire)
        # 发布时间
        on_release = ''.join(tr.xpath(site.torrent_release_rule))
        # 做种人数
        seeders = ''.join(tr.xpath(site.torrent_seeders_rule)).replace(',', '')
        # 下载人数
        leechers = ''.join(tr.xpath(site.torrent_leechers_rule)).replace(',', '')
        # 完成人数
        completers = ''.join(tr.xpath(site.torrent_completers_rule)).replace(',', '')
        # 存在则更新，不存在就创建
        # logger.debug(type(seeders), type(leechers), type(completers), )
        # logger.debug(seeders, leechers, completers)
        # logger.debug(''.join(tr.xpath(site.title_rule)))
        category = ''.join(
            tr.xpath(site.torrent_category_rule)
        ).replace("styles/HHan/icons/icon-", "").replace(".svg", "")
        file_parse_size = ''.join(tr.xpath(site.torrent_size_rule))
        # file_parse_size = ''.join(tr.xpath(''))
        logger.debug(file_parse_size)
        file_size = toolbox.FileSizeConvert.parse_2_byte(file_parse_size)
        # subtitle = subtitle if subtitle else title
        poster_url = ''.join(tr.xpath(site.torrent_poster_rule))  # 海报链接
        tags = ','.join(tr.xpath(site.torrent_tags_rule))  # 标签
        logger.debug(f'title：{site}\n size: {file_size}\n category：{category}\n '
                     f'magnet_url：{magnet_url}\n subtitle：{subtitle}\n sale_status：{sale_status}\n '
                     f'sale_expire：{sale_expire}\n seeders：{seeders}\n leechers：{leechers}\n'
                     f'H&R：{hr}\n poster_url：{poster_url}\n tags：{tags}')
        torrent = {
            'site_id': my_site.site,
            'tid': tid,
            'poster': poster_url,
            'category': category,
            'magnet_url': magnet_url,
            # 'detail_url': f'{site.url}{site.page_detail.format(tid)}',
            'title': title,
            'subtitle': subtitle,
            'sale_status': sale_status,
            'sale_expire': sale_expire,
            'hr': hr,
            'published': on_release,
            'size': file_size,
            'seeders': int(seeders) if seeders else 0,
            'leechers': int(leechers) if leechers else 0,
            'completers': int(completers) if completers else 0,
        }
        return CommonResponse.success(data=torrent)

    def get_torrent_info_list(self, my_site: MySite, response: Response):
        count = 0
        new_count = 0
        torrents = []
        site = get_object_or_404(WebSite, id=my_site.site)
        mirror = my_site.mirror if my_site.mirror_switch else site.url

        try:
            with lock:
                trs = self.parse(site, response, site.torrents_rule)
                # logger.debug(f'种子页面：{response.text}')
                # logger.info(trs)
                logger.info(f'{my_site.nickname} 共发现{len(trs)}条种子记录')
                logger.info('=' * 50)
                for tr in trs:
                    try:
                        res = self.parse_torrent_list(tr, site, my_site)
                        if res.code != 0:
                            logger.error(res.msg)
                            continue
                        torrent_info = res.data
                        result = TorrentInfo.objects.update_or_create(
                            site=my_site,
                            tid=torrent_info.get("tid"),
                            defaults=torrent_info)
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
                    except Exception as e:
                        logger.exception(traceback.format_exc(5))
                        err_msg = f'当前种子解析出错啦！{e}'
                        logger.error(err_msg)
                        continue
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

    def generate_magnet_url(self, sid, torrent, my_site: MySite, website: WebSite):
        """
        生成下载链接
        :param my_site:
        :param sid:
        :param torrent:
        :param website:
        :return:
        """
        logger.info(f"{sid} - {torrent} - {my_site} - {website}")
        torrent_id = torrent.get("tid")
        if "totheglory.im" in website.url:
            return f'{website.url}{website.page_download.format(torrent_id, random.randint(100, 10000))}'
        if '海豹':
            pass
        if '海豚':
            pass
        if 'hdcity.city' in website.url:
            f'{website.url}{website.page_download.format(torrent_id, my_site.passkey)}'
        if "hdchina.org" in website.url:
            # 如果是瓷器，就从种子详情页获取下载链接
            torrent_details = self.get_torrent_detail(torrent_id, my_site, website)
            logger.info(f'瓷器种子 {torrent_id} 获取详情页结果： {torrent_details}')
            if torrent_details.code != 0:
                return torrent_details['magnet_url']
        return f'{website.url}{website.page_download.format(torrent_id)}'

    @staticmethod
    def get_qb_repeat_info(torrent, client):
        hash_string = torrent.get("hash")
        title = torrent.get("name")
        size = torrent.get("size")
        # 获取种子块HASH列表，并生成种子块HASH列表字符串的sha1值，保存
        pieces_hash_list = client.torrents_piece_hashes(torrent_hash=hash_string)
        pieces_hash_string = ''.join(str(pieces_hash) for pieces_hash in pieces_hash_list)
        pieces_qb = toolbox.sha1_hash(pieces_hash_string)
        # 获取文件列表，并生成文件列表字符串的sha1值，保存
        file_list = client.torrents_files(torrent_hash=hash_string)
        file_list_hash_string = ''.join(str(item) for item in file_list)
        filelist = toolbox.sha1_hash(file_list_hash_string)
        files_count = len(file_list)
        return {
            "title": title,
            "size": size,
            "hash_string": hash_string,
            "filelist": filelist,
            "files_count": files_count,
            "pieces_qb": pieces_qb,
        }

    def repeat_torrents(self, downloader_id: int):
        # 1. 获取下载器实例与分类
        client, downloader_category, downloader_name = toolbox.get_downloader_instance(downloader_id)
        try:
            if not client:
                msg = f'下载器： {downloader_id} 不可用？！'
                logger.error(msg)
                return msg
            website_list = WebSite.objects.filter(repeat_torrents=True).all()
            logger.debug(f'支持辅种的站点列表: {website_list}')

            my_site_list = MySite.objects.filter(repeat_torrents=True).all()
            logger.debug(f'开启辅种的站点列表: {my_site_list}')

            # 加载辅种配置项
            repeat = toolbox.parse_toml('repeat')
            logger.debug(f'加载辅种配置项: {repeat}')
            limit = repeat.get('limit', 15)
            iyuu_token = repeat.get('iyuu_token')
            push_once = repeat.get('push_once', 200)
            cache_expire = repeat.get('cache_expire', 604800)
            interval = repeat.get('interval', 1)
            timeout = repeat.get('timeout', 60)
            auto_torrent_management = repeat.get('auto_torrent_management', False)
            content_layout = repeat.get('content_layout', "Original")

            # 新的params数据，将会存储新的种子信息
            new_params = {}
            repeat_count = 0
            cached_count = 0
            push_count = 0
            repeat_params = {}
            pushed_hash = []

            if downloader_category == DownloaderCategory.qBittorrent:
                logger.info(f'从下载器 {downloader_name} 获取所有已完成种子信息')
                torrents = client.torrents_info(filter='completed')

                hash_lookup = {item["hash"]: item for item in torrents}

                logger.info(f'{downloader_name} 随机抽取 {push_once} 条数据')
                torrents = random.sample(torrents, min(len(torrents), push_once))

                try:
                    logger.info(f'{downloader_name} 开始生成需要辅种的数据')
                    new_func = functools.partial(self.get_qb_repeat_info, client=client)
                    to_server_data = pool.map(new_func, torrents)
                    logger.info(to_server_data)
                    for d in to_server_data:
                        hash_string = d.get('hash_string')
                        try:
                            t, created = TorrentInfo.objects.update_or_create(
                                hash_string=hash_string,
                                defaults=d
                            )
                            logger.debug(f'{t.hash_string} => 新增：{created}')
                        except Exception as e:
                            logger.error(f'{hash_string} => 保存到数据库出错了！{e}')
                            logger.error(traceback.format_exc(5))
                            continue
                    repeat_data = [item["hash"] for item in torrents]
                    logger.debug(f'本次需要辅种的数据：{repeat_data}')
                    try:
                        logger.info(f'{downloader_name} 开始上传辅种信息到服务器')
                        # res = requests.post(
                        #     url=f"{os.getenv('REPEAT_SERVER')}/api/website/torrents/repeat",
                        #     json={
                        #         "data": repeat_data,
                        #         "iyuu_token": iyuu_token,
                        #     },
                        #     headers={
                        #         "content-type": "application/json",
                        #         "AUTHORIZATION": os.getenv("TOKEN"),
                        #         "EMAIL": os.getenv("DJANGO_SUPERUSER_EMAIL"),
                        #     })
                        res = toolbox.get_torrents_hash_from_iyuu(hash_list=repeat_data)
                        logger.info(f'{downloader_name} 辅种返回结果 {res.dict()}')
                        if res.code != 0:
                            logger.info(res.msg)
                        else:
                            logger.info(res.data)
                            for info_hash, repeat_info in res.data.items():
                                logger.info(f'当前信息：{repeat_info}')
                                for torrent in repeat_info:
                                    torrent_hash = torrent["hash_string"]
                                    if torrent_hash in hash_lookup:
                                        logger.info(f'种子 {info_hash} 已存在，跳过')
                                        continue
                                    sid = torrent.get('site_id')
                                    website = website_list.filter(id=sid).first()
                                    logger.debug(f'当前站点：{website} - 站点ID: {sid}')
                                    if not website:
                                        logger.warning(f'还未支持此站点，站点ID：{sid}')
                                        continue
                                    website_id = website.id
                                    my_site = my_site_list.filter(site=website_id).first()
                                    logger.info(f'对应 我的站点：{my_site} - 站点ID: {sid}')
                                    if not my_site:
                                        logger.warning(f'你尚未添加站点：{website.name}')
                                        continue
                                    logger.info(f'生成辅种数据')
                                    if info_hash in hash_lookup:
                                        repeat_torrent = hash_lookup[info_hash]
                                        try:
                                            upload_limit = website.limit_speed * 1024 * 1024 * 0.92
                                            repeat_params.setdefault(website_id, []).append({
                                                "urls": self.generate_magnet_url(sid, torrent, my_site, website),
                                                # "category": repeat_torrent.get("category"),
                                                "save_path": repeat_torrent.get("save_path"),
                                                "cookie": my_site.cookie,
                                                "rename": repeat_torrent.get("name"),
                                                "upload_limit": int(upload_limit),
                                                "download_limit": 150 * 1024,
                                                "is_skip_checking": False,
                                                "is_paused": True,
                                                "info_hash": torrent_hash,
                                            })
                                            t, created = TorrentInfo.objects.update_or_create(
                                                hash_string=torrent_hash,
                                                defaults={
                                                    "site_id": sid,
                                                    "tid": torrent.get("tid"),
                                                })
                                            logger.debug(
                                                f'{t.hash_string} => 新增：{created}，限速：{upload_limit / 1024 / 1024}MB/S')
                                        except Exception as e:
                                            msg = f'{info_hash} {sid} - {torrent["tid"]}生成辅种数据失败：{e}'
                                            logger.error(msg)
                                            logger.error(traceback.format_exc(5))
                            logger.info(f'本次辅种数据，共有：{len(repeat_params)}个站点的辅种数据')
                            repeat_count = sum(len(values) for values in repeat_params.values())
                            logger.info(f'本次辅种，共有：{repeat_count}条辅种数据')
                    except Exception as e:
                        msg = f'{downloader_name} 上传辅种数据失败：{e}'
                        logger.error(msg)
                        return CommonResponse.error(msg=msg)

                    # 从缓存中获取旧的辅种数据
                    params = cache.get(f"params_data_{downloader_id}")
                    logger.info(f'当前缓存数据：{params}')
                    if params is not None:
                        logger.info(f'从缓存中获取旧的辅种数据，共有：{len(params)}个站点的辅种数据')
                        # 将新数据添加到旧数据中
                        for website_id, torrents in repeat_params.items():
                            params[website_id] = [dict(t) for t in set([tuple(d.items()) for d in
                                                                        params.get(website_id, []) + torrents])]
                    else:
                        if len(repeat_params) <= 0:
                            msg = f'下载器： {downloader_name} 没有可以辅种的数据？！'
                            logger.error(msg)
                            return CommonResponse.error(msg=msg)
                        params = repeat_params
                    # 3. 推送到下载器（使用Cookie）
                    for website_id, torrents in params.items():
                        # 提取每个站点的前十条数据，如果不足十条，则获取所有数据
                        top_limit_torrents = torrents[:limit]
                        logger.info(
                            f'提取 {website_list.get(id=website_id).name}： {len(top_limit_torrents)}条辅种数据：')

                        # 剩余的种子信息存入new_params，但是如果列表为空，就跳过
                        remaining_torrents = torrents[limit:]
                        cached_count = sum(len(values) for values in repeat_params.values())
                        logger.info(f'当前站点的剩余未推送种子：{len(remaining_torrents)}')
                        logger.info(f'缓存中共有：{cached_count}条辅种数据等待推送')

                        if remaining_torrents:
                            new_params[website_id] = remaining_torrents

                        logger.info(f'开始推送种子到下载器 {downloader_name}')
                        push_res = []
                        for torrent in top_limit_torrents:
                            time.sleep(interval)
                            logger.info(f'当前种子：{torrent}')
                            try:
                                r = client.torrents.add(
                                    urls=torrent['urls'],
                                    save_path=torrent['save_path'],
                                    # category=torrent['category'],
                                    paused=torrent['is_paused'],
                                    rename=torrent['rename'],
                                    cookie=torrent['cookie'],
                                    upload_limit=torrent['upload_limit'],
                                    download_limit=torrent['download_limit'],
                                    skip_checking=torrent['is_skip_checking'],
                                    use_auto_torrent_management=auto_torrent_management,
                                    content_layout=content_layout,
                                    timeout=timeout,
                                )
                                push_res.append({torrent['info_hash']: r})
                                push_count += 1
                                pushed_hash.append(torrent['info_hash'])
                            except Exception as e:
                                logger.error(f'推送种子到下载器 {downloader_name} 失败:{e}')
                                remaining_torrents.append(torrent)
                                continue

                        logger.debug(f'推送到下载器 {downloader_name} 结果：{push_res}')
                    logger.info(f'推送种子到下载器 {downloader_name} ,共推送:{push_count}条种子')

                    # 把剩余的数据继续放入缓存
                    logger.debug(f'剩余未推送站点：{len(new_params)} 个')
                    # cache.set(f"params_data_{downloader_id}", json.dumps(new_params))
                    cache.set(f"params_data_{downloader_id}", new_params, cache_expire)

                except Exception as e:
                    msg = f'{downloader_name} 推送种子信息到服务器失败！'
                    logger.error(msg)
                    logger.error(traceback.format_exc(5))

            if downloader_category == DownloaderCategory.Transmission:
                logger.info(f'正在从下载器 {downloader_name} 获取所有已完成种子信息')
                all_torrents = client.get_torrents()
                complete_torrents = [torrent for torrent in all_torrents if int(torrent.progress) == 100]
                logger.info('获取种子列表信息完成！')
                logger.info(f'生成 HASH 快搜信息')
                hash_lookup = {item.hashString: item for item in complete_torrents}

                logger.info(f'随机抽取 {push_once} 条数据')
                torrents = random.sample(complete_torrents, min(len(complete_torrents), push_once))

                try:
                    logger.info(f'开始生成需要辅种的数据')
                    repeat_data = [item.hashString for item in torrents]
                    to_server_data = [{
                        "title": t.name,
                        "size": t.size_when_done,
                        "hash_string": t.hashString,
                        "pieces_tr": toolbox.sha1_hash(t.pieces),
                        "files_count": len(t.get_files())
                    } for t in torrents]
                    logger.info(to_server_data)

                    for d in to_server_data:
                        hash_string = d.get('hash_string')
                        try:
                            t, created = TorrentInfo.objects.update_or_create(
                                hash_string=hash_string,
                                defaults=d
                            )
                            logger.debug(f'{t.hash_string} => 新增：{created}')
                        except Exception as e:
                            logger.error(f'{hash_string} => 保存到数据库出错了！{e}')
                            logger.error(traceback.format_exc(5))
                            continue
                    logger.info(f'{downloader_name} 需辅种数据 {repeat_data}')
                    try:
                        logger.info(f'开始上传辅种信息到服务器')
                        # res = requests.post(
                        #     url=f"{os.getenv('REPEAT_SERVER')}/api/website/torrents/repeat",
                        #     json={
                        #         "data": repeat_data,
                        #         "iyuu_token": iyuu_token,
                        #     },
                        #     headers={
                        #         "content-type": "application/json",
                        #         "AUTHORIZATION": os.getenv("TOKEN"),
                        #         "EMAIL": os.getenv("DJANGO_SUPERUSER_EMAIL"),
                        #     })
                        res = toolbox.get_torrents_hash_from_iyuu(hash_list=repeat_data)

                        logger.info(f'{downloader_name} 辅种返回结果 {res.dict()}')
                        if res.code != 0:
                            logger.error(res.msg)
                        else:
                            logger.info(res.data)
                            for info_hash, repeat_info in res.data.items():
                                logger.info(f'当前信息：{repeat_info}')
                                for torrent in repeat_info:
                                    logger.debug(torrent)
                                    torrent_hash = torrent["hash_string"]
                                    if torrent_hash in hash_lookup:
                                        logger.info(f'种子 {info_hash} 已存在，跳过')
                                        continue
                                    sid = torrent.get('site_id')
                                    website = website_list.filter(id=sid).first()
                                    logger.debug(f'当前站点：{website}')
                                    if not website:
                                        logger.warning(f'还未支持此站点，站点ID：{sid}')
                                        continue
                                    website_id = website.id
                                    my_site = my_site_list.filter(site=website_id).first()
                                    logger.info(f'对应 我的站点：{my_site}')
                                    if not my_site:
                                        logger.warning(f'你尚未添加站点：{website.name}')
                                        continue
                                    logger.info(f'{info_hash} 生成辅种数据')
                                    if info_hash in hash_lookup:
                                        repeat_torrent = hash_lookup[info_hash]
                                        try:
                                            repeat_params.setdefault(website_id, []).append({
                                                "torrent": self.generate_magnet_url(sid, torrent, my_site, website),
                                                "paused": True,
                                                # "labels": repeat_torrent.labels,
                                                "rename": repeat_torrent.name,
                                                "cookies": my_site.cookie,
                                                "download_dir": repeat_torrent.download_dir,
                                                "info_hash": torrent["hash_string"],
                                                "upload_limit": website.limit_speed * 1024 * 0.92,
                                            })
                                            t, created = TorrentInfo.objects.update_or_create(
                                                hash_string=torrent_hash,
                                                defaults={
                                                    "site_id": sid,
                                                    "tid": torrent.get("tid"),
                                                })
                                            logger.debug(f'{t.hash_string} => 新增：{created}')
                                        except Exception as e:
                                            msg = f'{info_hash} {sid} - {torrent["tid"]}生成辅种数据失败：{e}'
                                            logger.error(msg)
                            logger.info(f'本次辅种数据，共有：{len(repeat_params)}个站点的辅种数据')
                            repeat_count = sum(len(values) for values in repeat_params.values())
                            logger.info(f'本次辅种，共有：{repeat_count}条辅种数据')
                    except Exception as e:
                        msg = f'{downloader_name} 辅种数据处理失败：{e}'
                        logger.error(msg)
                        logger.error(traceback.format_exc(5))
                        return CommonResponse.error(msg=msg)

                    # 从缓存中获取旧的params数据
                    params = cache.get(f"params_data_{downloader_id}")

                    if params is not None:
                        logger.info(f'从缓存中获取旧的辅种数据，共有：{len(params)}条')
                        # 将新数据添加到旧数据中
                        for website_id, torrents in repeat_params.items():
                            params[website_id] = [dict(t) for t in set([tuple(d.items()) for d in
                                                                        params.get(website_id, []) + torrents])]
                    else:
                        if len(repeat_params) <= 0:
                            msg = '没有可以辅种的数据！'
                            logger.info(msg)
                            return CommonResponse.error(msg=msg)

                    params = repeat_params
                    for website_id, torrents in params.items():
                        # 提取每个站点前十条数据，如果不足十条，则获取所有数据
                        top_limit_torrents = torrents[:limit]
                        logger.info(
                            f'提取 {website_list.get(id=website_id).name}： {len(top_limit_torrents)}条辅种数据：')

                        # 剩余的种子信息存入new_params，但是如果列表为空，就跳过
                        remaining_torrents = torrents[limit:]
                        cached_count = sum(len(values) for values in repeat_params.values())
                        logger.info(f'当前站点的剩余未推送种子：{len(remaining_torrents)}')
                        logger.info(f'缓存中共有：{cached_count}条辅种数据等待推送')

                        push_res = []
                        for torrent in top_limit_torrents:
                            time.sleep(interval)
                            try:
                                r = client.add_torrent(
                                    torrent=torrent['torrent'],
                                    paused=torrent['paused'],
                                    cookies=torrent['cookies'],
                                    # labels=torrent['labels'],
                                    download_dir=torrent['download_dir'],
                                    timeout=timeout,
                                )
                                push_res.append({torrent['info_hash']: r.name})
                                logger.debug(f'{r.hashString} 打开上传限速：{torrent["upload_limit"] / 1024} MB/S')
                                client.change_torrent(
                                    ids=r.hashString,
                                    upload_limited=True,
                                    upload_limit=int(torrent["upload_limit"]),
                                    timeout=timeout,
                                )
                                push_count += 1
                                pushed_hash.append(torrent['info_hash'])
                                path, name = client.rename_torrent_path(
                                    torrent_id=r.hashString,
                                    location=r.name,
                                    name=torrent['rename']
                                )
                                logger.debug(f'{r.name} 修改默认存储路径结果，path: {path} - name：{name}')
                            except TransmissionError as e:
                                logger.error(f'推送种子到下载器 {downloader_name} 失败:{e.message}')
                                logger.error(f'推送失败的种子信息：{torrent}')
                                logger.error(traceback.format_exc(5))

                                if 'http error 404: Not Found' in e.message:
                                    logger.error(f'当前种子已被删除，正在向服务器报告！')
                                    # ToDo 向PTOOLS服务器报告，服务器收到后将hash存储到已被删除种子信息中，下次辅种跳过本种子
                                    pass
                                remaining_torrents.append(torrent)
                                continue
                            except Exception as e:
                                logger.error(f'推送种子到下载器 {downloader_name} 失败: {e}')
                                logger.error(f'推送失败的种子信息：{torrent}')
                                remaining_torrents.append(torrent)
                                continue
                        if remaining_torrents:
                            new_params[website_id] = remaining_torrents

                        logger.info(f'推送到下载器 {downloader_name} 结果：{push_res}')
                        logger.info(f'推送种子到下载器 {downloader_name} ,共推送:{push_count}条种子')

                        logger.debug(f'剩余未推送站点：{len(new_params)} 个')

                except Exception as e:
                    msg = f'{downloader_name} 推送种子信息到服务器失败！'
                    logger.error(msg)
                    logger.error(traceback.format_exc(5))
            # 把剩余的数据继续放入缓存
            cache.set(f"params_data_{downloader_id}", new_params, cache_expire)
            return CommonResponse.success(data=(repeat_count, cached_count, push_count, pushed_hash))
        except Exception as e:
            msg = f'下载器 {downloader_name} 辅种失败：{e}'
            logger.error(msg)
            logger.error(traceback.format_exc(5))
            return CommonResponse.error(msg=msg)

    def start_torrent(self, downloader_id: int):
        logger.debug(f'当前下载器: {downloader_id}')
        client, downloader_category, downloader_name = toolbox.get_downloader_instance(downloader_id)
        logger.debug(f'当前下载器: {downloader_name}')

        # 加载辅种配置项
        try:
            repeat = toolbox.parse_toml('repeat')
            verify_timeout = repeat.get('verify_timeout', 60)

            paused_count = 0
            recheck_count = 0
            resume_count = 0
            if downloader_category == DownloaderCategory.qBittorrent:
                logger.info(f'当前下载器: {downloader_name} 获取暂停状态的种子')
                torrents = client.torrents.info.paused()
                logger.info(f'当前下载器: {downloader_name} 当前待处理种子数量: {len(torrents)}')
                paused_count = len(torrents)

                logger.info('当前下载器: {downloader_name} 筛选进度为0且状态为暂停的种子')
                recheck_torrents = [torrent for torrent in torrents if torrent.get("progress") == 0]
                if len(recheck_torrents) > 0:
                    for t in recheck_torrents:
                        if t['name'] != t['content_path'].split('/')[-1]:
                            try:
                                client.torrents_rename_folder(
                                    torrent_hash=t['hash'],
                                    old_path=t['content_path'].split('/')[-1],
                                    new_path=t['name'],
                                )
                            except Exception as e:
                                logger.error(e)
                                continue
                recheck_hashes = [torrent.get("hash") for torrent in torrents if torrent.get("progress") == 0]
                logger.info(f'当前下载器: {downloader_name} 等待校验的种子数量: {len(recheck_hashes)}')
                recheck_count = len(recheck_hashes)

                if len(recheck_hashes) > 0:
                    logger.info(f'当前下载器: {downloader_name} 开始校验，等待等待{verify_timeout}秒')
                    client.torrents.recheck(torrent_hashes=recheck_hashes)
                    if client.app.web_api_version >= '2.8.4':
                        while len(client.torrents.info.checking()) > 0:
                            time.sleep(verify_timeout)
                    else:
                        time.sleep(verify_timeout)
                else:
                    logger.info(f'当前下载器 {downloader_name} 没有需要校验的种子！')

                logger.info('当前下载器: {downloader_name} 获取校验完成的种子')
                torrents = client.torrents.info.paused()
                completed_hashes = [torrent['hash'] for torrent in torrents if torrent['progress'] == 1]
                logger.info(f'当前下载器: {downloader_name} 校验完成的种子数量: {len(completed_hashes)}')
                resume_count = len(completed_hashes)

                logger.info(f'开始已完成的种子')
                if resume_count > 0:
                    client.torrents.resume(torrent_hashes=completed_hashes)

            if downloader_category == DownloaderCategory.Transmission:
                torrents = client.get_torrents()
                logger.info('当前下载器: {downloader_name} 筛选进度为0且状态为暂停的种子')
                recheck_hashes = [torrent.hashString for torrent in torrents if
                                  torrent.status == 'stopped' and torrent.progress == 0]
                logger.info(f'当前下载器: {downloader_name} 等待校验的种子数量: {len(recheck_hashes)}')
                paused_count = len(recheck_hashes)
                while len(recheck_hashes) > 0:
                    logger.info(f'当前下载器: {downloader_name} 开始校验，等待{verify_timeout}秒')
                    client.verify_torrent(ids=recheck_hashes)
                    time.sleep(verify_timeout)
                    recheck_hashes = [torrent.hashString for torrent in torrents if
                                      torrent.status == 'check_pending' or torrent.status == 'checking']
                recheck_count = len(recheck_hashes)

                torrents = client.get_torrents()
                logger.info('当前下载器: {downloader_name} 获取校验完成的种子')
                completed_hashes = [torrent.hashString for torrent in torrents if
                                    torrent.status == 'stopped' and torrent.progress == 100]
                logger.info(f'当前下载器: {downloader_name} 开始已完成的种子')
                resume_count = len(completed_hashes)
                if resume_count > 0:
                    client.start_torrent(ids=completed_hashes)
            return CommonResponse.success(data=(paused_count, recheck_count, resume_count))
        except Exception as e:
            msg = f'下载器  {downloader_name}  辅种失败：{e}'
            logger.error(msg)
            logger.error(traceback.format_exc(5))
            return CommonResponse.error(msg=msg)
