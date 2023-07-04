import random
import traceback

import requests
from lxml import etree


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
        dist_dict[list2[0].strip()] = list2[1].strip()
    return dist_dict


def sign_ssd_forum(cookie, user_agent, todaysay):
    try:
        # 访问签到页
        sign_url = 'https://ssdforum.org/plugin.php?id=dsu_paulsign:sign'
        sign_response = requests.get(
            url=sign_url,
            headers={
                'User-Agent': user_agent,
                'Referer': 'https://ssdforum.org/',
            },
            cookies=cookie2dict(cookie),
        )
        print(f'签到页HTML：{sign_response.content.decode("gbk")}')
        html_object = etree.HTML(sign_response.content.decode('gbk'))
        sign_check = html_object.xpath('//div[@class="c"]/text()')
        print(f"签到检测：{sign_check}")
        sign_text = ''
        if not sign_check or len(sign_check):
            print(f"签到检测：{len(sign_check)}")
            # action_url = html_object.xpath('//form[@id="qiandao"]/@action')
            formhash = ''.join(html_object.xpath('//form[@id="qiandao"]/input[@name="formhash"]/@value'))
            # 获取并生成签到参数
            qdxq_options = ['kx', 'ng', 'ym', 'wl', 'nu', 'ch', 'fd', 'yl', 'shuai']
            form_data = {
                'formhash': formhash,
                'qdxq': random.choice(qdxq_options),  # replace with the desired value
                'qdmode': '1',  # replace with the desired value
                'todaysay': random.choice(todaysay),  # replace with the desired value
            }
            # 发送签到请求
            sign_in_url = 'https://ssdforum.org/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1'
            sign_in_response = requests.post(
                url=sign_in_url,
                headers={
                    'User-Agent': user_agent,
                    'Referer': 'https://ssdforum.org/',
                },
                cookies=cookie2dict(cookie),
                data=form_data,
            )
            # 解析签到反馈
            print(f'签到反馈：{sign_in_response.content.decode("gbk")}')
            sign_text = ''.join(etree.HTML(sign_in_response.content.decode('gbk')).xpath('//div[@class="c"]/text()'))
        else:
            sign_text = '今日已签到'
            print(sign_text)
        sign_response = requests.get(
            url=sign_url,
            headers={
                'User-Agent': user_agent,
                'Referer': 'https://ssdforum.org/',
            },
            cookies=cookie2dict(cookie),
        )
        print(f"签到页：{sign_response.content.decode('gbk')}")
        sign_title_rule = '//div[@class="mn"]/h1[1]/text()'
        sign_content_rule = '//div[@class="mn"]/p/text()'
        title = etree.HTML(sign_response.content.decode('gbk')).xpath(sign_title_rule)
        content = etree.HTML(sign_response.content.decode('gbk')).xpath(sign_content_rule)
        print(f'签到结果:{sign_text}。{title} {content}')
    except Exception as e:
        msg = f'ssdforum签到失败，{e}'
        print(traceback.format_exc(5))
        print(msg)


if __name__ == '__main__':
    cookie = 'Cq0h_2132_saltkey=PlZdJhrL; Cq0h_2132_lastvisit=1686272763; Cq0h_2132_seccodecSZdhhOT=258.a4e0d7b52e9b5bb984; Cq0h_2132_ulastactivity=6e56f7fEu7sGrrt2Yg%2BfE6GbJVMAUlX4A9iYNQiLn1rrV7tY30E3; Cq0h_2132_auth=1751iXhcaZMiXnwVGQ3vPhNfKgg6zF9ad5SS5KlaQMK4417s7A%2BoS8K4iC4P7k6dtooM2fQw14RYd1gw1eI1YfCBotU; Cq0h_2132_resendemail=1688450291; Cq0h_2132_myrepeat_rr=R0; Cq0h_2132_nofavfid=1; Cq0h_2132_study_nge_extstyle=auto; Cq0h_2132_study_nge_extstyle_default=auto; Cq0h_2132_seccodecSBRervv=259.adfadbe8b80a93d8fa; Cq0h_2132_sendmail=1; Cq0h_2132_noticeTitle=1; Cq0h_2132_sid=UNnaJo; Cq0h_2132_lip=240e%3A479%3Ac210%3A2f7%3Afdc4%3A75a7%3A11bd%3A173b%2C1688459218; Cq0h_2132_lastact=1688459222%09plugin.php%09'
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
    todaysay = [
        '今天',
        '明天',
        '后天',
        '周一',
        '周二',
        '周三',
        'Hello World!',
    ]
    sign_ssd_forum(cookie, user_agent, todaysay)
