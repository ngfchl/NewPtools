import json
import logging
import re
import time
import traceback
from datetime import datetime

import aip
import cloudscraper
import dateutil.parser
import toml as toml

from my_site.models import MySite, SiteStatus
from toolbox.models import BaiduOCR
from toolbox.schema import CommonResponse
from website.models import WebSite

# Create your views here.
logger = logging.getLogger('ptools')


def parse_token(cmd):
    """从配置文件解析获取相关项目"""
    data = toml.load('db/ptools.toml')
    return data.get(cmd)


def cookie2dict(source_str: str) -> dict:
    """
    cookies字符串转为字典格式,传入参数必须为cookies字符串
    """
    dist_dict = {}
    list_mid = source_str.strip().split(';')
    for i in list_mid:
        # 以第一个选中的字符分割1次，
        if len(i) <= 0:
            continue
        list2 = i.split('=', 1)
        dist_dict[list2[0]] = list2[1]
    return dist_dict


# 获取字符串中的数字
get_decimals = lambda x: re.search("\d+(\.\d+)?", x).group() if re.search("\d+(\.\d+)?", x) else 0


class FileSizeConvert:
    """文件大小和字节数互转"""

    @staticmethod
    def parse_2_byte(file_size: str) -> int:
        if not file_size:
            return 0
        """将文件大小字符串解析为字节"""
        regex = re.compile(r'(\d+(?:\.\d+)?)\s*([kmgtp]?b)', re.IGNORECASE)

        order = ['b', 'kb', 'mb', 'gb', 'tb', 'pb', 'eb']

        for value, unit in regex.findall(file_size):
            return int(float(value) * (1024 ** order.index(unit.lower())))

    @staticmethod
    def parse_2_file_size(byte: int) -> str:
        if not byte:
            return '0B'
        units = ["B", "KB", "MB", "GB", "TB", "PB", 'EB']
        size = 1024.0
        for i in range(len(units)):
            if (byte / size) < 1:
                return "%.3f %s" % (byte, units[i])
            byte = byte / size


def baidu_ocr_captcha(self, img_url):
    """百度OCR高精度识别，传入图片URL"""
    # 获取百度识别结果
    ocr = BaiduOCR.objects.filter(enable=True).first()
    if not ocr:
        logger.error('未设置百度OCR文本识别API，无法使用本功能！')
        return CommonResponse.error(msg='未设置百度OCR文本识别API，无法使用本功能！')
    try:
        ocr_client = aip.AipOcr(appId=ocr.app_id, secretKey=ocr.secret_key, apiKey=ocr.api_key)
        res1 = ocr_client.basicGeneralUrl(img_url)
        logger.info(res1)
        if res1.get('error_code'):
            res1 = ocr_client.basicAccurateUrl(img_url)
        logger.info('res1: {}'.format(res1))
        if res1.get('error_code'):
            return CommonResponse.error(msg=res1.get('error_msg'))
        res2 = res1.get('words_result')[0].get('words')
        # 去除杂乱字符
        imagestring = ''.join(re.findall('[A-Za-z0-9]+', res2)).strip()
        logger_info = '百度OCR天空验证码：{}，长度：{}'.format(imagestring, len(imagestring))
        logger.info(logger_info)
        # 识别错误就重来

        return CommonResponse.success(data=imagestring)
    except Exception as e:
        msg = '百度OCR识别失败：{}'.format(e)
        logger.info(traceback.format_exc(limit=3))
        # raise
        self.send_text(title='OCR识别出错咯', message=msg)
        return CommonResponse.error(msg=msg)


def parse_ptpp_cookies(self, data_list):
    # 解析前端传来的数据
    datas = json.loads(data_list.get('cookies'))
    info_list = json.loads(data_list.get('info'))
    userdata_list = json.loads(data_list.get('userdata'))
    cookies = []
    try:
        for data, info in zip(datas, info_list):
            cookie_list = data.get('cookies')
            host = data.get('host')
            cookie_str = ''
            for cookie in cookie_list:
                cookie_str += '{}={};'.format(cookie.get('name'), cookie.get('value'))
            # logger.info(domain + cookie_str)
            cookies.append({
                'url': data.get('url'),
                'host': host,
                'icon': info.get('icon'),
                'info': info.get('user'),
                'passkey': info.get('passkey'),
                'cookies': cookie_str.rstrip(';'),
                'userdatas': userdata_list.get(host)
            })
        logger.info('站点记录共{}条'.format(len(cookies)))
        # logger.info(cookies)
        return CommonResponse.success(data=cookies)
    except Exception as e:
        # raise
        # 打印异常详细信息
        logger.error(traceback.format_exc(limit=3))
        return CommonResponse.error(msg='Cookies解析失败，请确认导入了正确的cookies备份文件！{}'.format(e))


# @transaction.atomic
def get_uid_and_passkey(self, cookie: dict):
    url = cookie.get('url')
    host = cookie.get('host')
    site = WebSite.objects.filter(url__contains=host).first()
    # logger.info('查询站点信息：', site, site.url, url)
    if not site:
        return CommonResponse.error(msg='尚未支持此站点：{}'.format(url))
    # 如果有更新cookie，如果没有继续创建
    userdatas = cookie.get('userdatas')
    time_stamp = cookie.get('info').get('joinTime')
    if not time_stamp:
        time_join = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(time_stamp) / 1000))
    else:
        time_join = datetime.now()
    uid = cookie.get('info').get('id')
    if not uid:
        try:
            logger.info('备份文件未获取到User_id，尝试获取中')
            scraper = cloudscraper.create_scraper(browser={
                'browser': self.browser,
                'platform': self.platform,
                'mobile': False
            })
            response = scraper.get(
                url=site.url + site.page_index,
                cookies=cookie.get('cookies'),
            )
            logger.info(response.text)
            uid = ''.join(self.parse(site, response, site.my_uid_rule)).split('=')[-1]
            # passkey = self.parse(site, response, site.my_passkey_rule)[0]
            logger.info(f'uid:{uid}')
        except Exception as e:
            passkey_msg = f'{site.name} Uid获取失败，请手动添加！'
            msg = f'{site.name} 信息导入失败！ {passkey_msg}：{e}'
            logger.info(passkey_msg)
            return CommonResponse.error(
                msg=msg
            )
    result = MySite.objects.update_or_create(site=site.id, defaults={
        'cookie': cookie.get('cookies'),
        'user_id': uid,
        'time_join': time_join,
    })
    my_site = result[0]
    passkey_msg = ''
    logger.info('开始导入PTPP历史数据')
    for key, value in userdatas.items():
        logger.info(key)
        try:
            downloaded = value.get('downloaded')
            uploaded = value.get('uploaded')
            seeding_size = value.get('seedingSize')
            my_bonus = value.get('bonus')
            ratio = value.get('ratio')
            seed = value.get('seeding')
            my_level_str = value.get('levelName')
            if 'hdcity' in site.url:
                my_level = my_level_str.replace('[', '').replace(']', '').strip(" ").strip()
            else:
                my_level = re.sub(u"([^\u0041-\u005a\u0061-\u007a])", "", my_level_str).strip(" ")
            if not my_level:
                my_level = 'User'
            if ratio is None or ratio == 'null':
                continue
            if type(ratio) == str:
                ratio = ratio.strip('\n').strip()
            if float(ratio) < 0:
                ratio = 'inf'
            if not value.get(
                    'id') or key == 'latest' or not downloaded or not uploaded or not seeding_size or not my_bonus:
                continue
            create_time = dateutil.parser.parse(key).date()
            count_status = SiteStatus.objects.filter(site=my_site,
                                                     created_at__date=create_time).count()
            if count_status >= 1:
                continue
            res_status = SiteStatus.objects.update_or_create(
                site=my_site,
                created_at__date=create_time,
                defaults={
                    'uploaded': uploaded,
                    'downloaded': downloaded,
                    'ratio': float(ratio),
                    'my_bonus': my_bonus,
                    'my_level': my_level,
                    'seed_volume': seeding_size,
                    'seed': seed if seed else 0,
                })
            res_status[0].created_at = create_time
            res_status[0].save()
            logger.info(f'数据导入结果: 日期: {create_time}，True为新建，false为更新')
            logger.info(res_status)
        except Exception as e:
            msg = '{}{} 数据导入出错，错误原因：{}'.format(site.name, key, traceback.format_exc(limit=3))
            logger.error(msg)
            continue
    return CommonResponse.success(
        # status=StatusCodeEnum.NO_PASSKEY_WARNING,
        msg=site.name + (' 信息导入成功！' if result[1] else ' 信息更新成功！ ') + passkey_msg
    )
