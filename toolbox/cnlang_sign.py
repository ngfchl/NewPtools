# -*- coding: utf8 -*-

"""
cron: 0 9,20 * * *
new Env('国语世界签到');
"""

import os
# from bs4 import BeautifulSoup
import re

import requests
from lxml import etree


# from sendNotify import send


def start(cookie, username):
    try:
        s = requests.session()
        flb_url = "cnlang.org"
        headers = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                   'Accept - Encoding': 'gzip, deflate, br',
                   'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                   'cache-control': 'max-age=0',
                   'Upgrade-Insecure-Requests': '1',
                   'Host': flb_url,
                   'Cookie': cookie,
                   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36 Edg/97.0.1072.62'}

        # 访问Pc主页
        print(flb_url)
        user_info = s.get('https://' + flb_url + '/dsu_paulsign-sign.html?mobile=no', headers=headers).text
        html = user_info
        user_name = re.search(r'title="访问我的空间">(.*?)</a>', user_info)

        # 解析 HTML 页面
        # soup = BeautifulSoup(html, 'html.parser')
        tree = etree.HTML(html)

        # 找到 name 为 formhash 的 input 标签
        # formhash_input = soup.find('input', {'name': 'formhash'})
        formhash_value = ''.join(tree.xpath('//input[@name="formhash"]/@value'))

        # 从 input 标签中提取 formhash 的值
        # formhash_value = re.search(r'value="(.+?)"', str(formhash_input)).group(1)

        print("formhash：" + formhash_value)
        # 随机获取心情
        xq = s.get('https://v1.hitokoto.cn/?encode=text').text
        # 保证字数符合要求
        print("想说的话：" + xq)
        while (len(xq) < 6 | len(xq) > 50):
            xq = s.get('https://v1.hitokoto.cn/?encode=text').text
            print("想说的话：" + xq)
        if user_name:
            print("登录用户名为：" + user_name.group(1))
            print("环境用户名为：" + username)
        else:
            print("未获取到用户名")
        if user_name is None or (user_name.group(1) != username):
            raise Exception("【国语视界】cookie失效")
        # 获取签到链接,并签到
        qiandao_url = 'plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1'

        # 签到
        payload = dict(formhash=formhash_value, qdxq='kx', qdmode='1', todaysay=xq, fastreply='0')
        qdjg = s.post('https://' + flb_url + '/' + qiandao_url, headers=headers, data=payload).text

        html = qdjg

        # soup = BeautifulSoup(html, 'html.parser')
        # div = soup.find('div', {'class': 'c'})  # 找到 class 为 clash，id 为 c 的 div
        # content = div.text  # 获取 div 的文本内容
        content = ''.join(etree.HTML(html).xpath('//div[@class="c"]/text()'))

        print(content)
        # 获取积分
        user_info = s.get(
            'https://' + flb_url + '/home.php?mod=spacecp&ac=credit&showcredit=1&inajax=1&ajaxtarget=extcreditmenu_menu',
            headers=headers).text
        current_money = re.search(r'<span id="hcredit_2">(\d+)</span>', user_info).group(1)
        log_info = content + "当前大洋余额{}".format(current_money)
        print(log_info)
        # send("签到结果", log_info)
        return log_info
    except Exception as e:
        msg = f'签到失败，失败原因: {e}'
        print(msg)
        return msg


def get_addr():
    pub_page = "http://fuliba2023-1256179406.file.myqcloud.com/"
    ret = requests.get(pub_page)
    ret.encoding = "utf-8"
    bbs_addr = re.findall(r'<a href=.*?><i>https://(.*?)</i></a>', ret.text)[1]
    return bbs_addr


if __name__ == '__main__':
    # cookie = ""
    # user_name = ""
    cookie = os.getenv("CNLANG_COOKIE")
    user_name = os.getenv("CNLANG_UNAME")
    start(cookie, user_name)
