import random
import re
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


def sht_sign(host, username, password, cookie, user_agent):
    try:
        cookies_dict = cookie2dict(cookie)
        # 登录界面URL
        login_ui_url = f'{host}/member.php?mod=logging&action=login&infloat=yes&handlekey=login&ajaxtarget=fwin_content_login'
        print(login_ui_url)
        # 创建请求对象
        session = requests.Session()
        # 打开登录界面
        response = session.get(
            url=login_ui_url,
            headers={
                "User-Agent": user_agent,
                "Referer": f'{host}/forum.php',
            },
            cookies=cookies_dict
        )
        print(f'打开登录界面：{response.content.decode("utf8")}')
        html_code = response.content.decode('utf8').replace('<?xml version="1.0" encoding="utf-8"?>', '').replace(
            '<root><![CDATA[', '').replace(']]></root>', '')
        # 检测到签到链接
        # pattern = r'<!\[CDATA\[(.*?)\]\]>'
        # match = re.search(pattern, response.content.decode('utf8'), re.DOTALL)
        # html_code = match.group(1)
        check_login = etree.HTML(html_code).xpath('//a[@href="plugin.php?id=dd_sign:index"]')
        print(f'Cookie有效检测：签到链接存在数量 {len(check_login)}')
        # 如果检测到签到链接，则直接使用Cookie，否则重新获取Cookie
        if not check_login or len(check_login) <= 0:
            print(f'Cookie失效，重新获取')
            # 解析登录界面数据，获取formhash与loginhash
            html_object = etree.HTML(response.content.decode('utf8')[55:-10])
            # 获取form表单对象
            form = html_object.xpath('//form')[0]
            # 获取提交链接
            login_action_link = form.xpath('@action')[0]
            print(login_action_link)
            # 解析相关字段
            fields = form.xpath('.//input[@type="hidden"]')

            form_data = {
                "formhash": '',
                "referer": f'{host}/forum.php',
                "username": username,
                "password": password,
                "cookietime": 2592000
            }
            # 输出需要填写的字段名和值
            for field in fields:
                name = field.get('name')
                value = field.get('value', '')
                form_data[name] = value
                print(f"字段名: {name}, 值: {value}")

            print(f"登录参数：{form_data}")
            # 登录
            login_action_url = f'{host}{login_action_link}'
            login_response = session.post(
                url=login_action_url,
                data=form_data,
                headers={
                    "User-Agent": user_agent,
                    'referer': f"{host}/forum.php",
                },
                cookies={
                    '_safe': 'vqd37pjm4p5uodq339yzk6b7jdt6oich'
                }
            )
            print(f"登录反馈：{login_response.content.decode('utf8')}")
            cookies_dict = session.cookies.get_dict()
            msg = f"新获取的Cookie：{cookies_dict}"
            print(msg)
            # send_text(message=msg, title='请及时更新98Cookie!')
        # 检测签到与否
        check_sign_url = f'{host}/plugin.php?id=dd_sign:index'
        check_sign_response = session.get(
            url=check_sign_url,
            headers={
                "User-Agent": user_agent,
                "Referer": f'{host}/forum.php',
            },
            cookies=cookies_dict,
        )
        print(f"签到检测：{check_sign_response.content.decode('utf8')}")
        check_sign = etree.HTML(check_sign_response.content.decode('utf8')).xpath('//a[contains(text(),"今日已签到")]')
        print(f'签到与否检测 {check_sign}')
        if not check_sign or len(check_sign) <= 0:
            # 打开签到界面
            sign_ui_url = f'{host}/plugin.php?id=dd_sign&mod=sign&infloat=yes&handlekey=pc_click_ddsign&inajax=1&ajaxtarget=fwin_content_pc_click_ddsign'
            # 获取idhash
            sign_response = session.get(
                url=sign_ui_url,
                headers={
                    "User-Agent": user_agent,
                    'referer': f"{host}/plugin.php?id=dd_sign:index",
                },
                cookies=cookies_dict,
            )
            print(f'签到界面: {sign_response.content.decode("utf8")}')
            # 使用正则表达式提取字段
            match = re.compile(
                r'signhash=(.+?)".*name="formhash" value="(\w+)".*name="signtoken" value="(\w+)".*secqaa_(.+?)\"',
                re.S)
            signhash, formhash, signtoken, idhash = re.findall(match, sign_response.content.decode('utf8'))[0]
            print(f'签到界面参数: \n链接: {signhash} \n'
                  f' formhash: {formhash} \n signtoken:{signtoken}\n idhash: {idhash}\n')
            # 获取计算题
            calc_ui_url = f'{host}/misc.php?mod=secqaa&action=update&idhash={idhash}&{round(random.uniform(0, 1), 16)}'
            calc_response = session.get(
                url=calc_ui_url,
                headers={
                    "User-Agent": user_agent,
                    'referer': f"{host}/plugin.php?id=dd_sign:index",
                },
                cookies=cookies_dict,
            )
            print(f'计算题: {calc_response.content.decode("utf8")}')
            # 解析签到数据
            pattern = r'(\d+\s*[-+*/]\s*\d+)'
            match = re.search(pattern, calc_response.content.decode('utf8'))
            print(f'解析出的计算题: {match.group(0)}')
            calc_result = eval(match.group(1))
            print(f'计算结果: {calc_result}')
            # 校验签到计算结果
            calc_check_url = f'{host}/misc.php?mod=secqaa&action=check&inajax=1&modid=&idhash={idhash}&secverify={calc_result}'
            print(f"签到检测链接：{calc_check_url}")
            calc_check_response = session.get(
                url=calc_check_url,
                headers={
                    "User-Agent": user_agent,
                    'referer': f"{host}/plugin.php?id=dd_sign:index",
                },
                cookies=cookies_dict,
            )
            print(f"签到校验结果: {calc_check_response.content.decode('utf8')}")
            if 'succeed' in calc_check_response.content.decode('utf8'):
                # 发送签到请求
                sign_form_data = {
                    "formhash": formhash,
                    "signtoken": signtoken,
                    "secqaahash": idhash,
                    "secanswer": calc_result,
                }
                sign_post_url = f'{host}/plugin.php?id=dd_sign&mod=sign&signsubmit=yes&handlekey=pc_click_ddsign&signhash={signhash}&inajax=1'
                print(f"签到链接: {sign_post_url}")
                sign_response = session.post(
                    url=sign_post_url,
                    headers={
                        "User-Agent": user_agent,
                        'referer': f"{host}/plugin.php?id=dd_sign:index",
                    },
                    cookies=cookies_dict,
                    data=sign_form_data,
                )
                print(f"签到结果页：{sign_response.content.decode('utf8')}")
                match = re.search(r"showDialog\('([^']*)'", sign_response.content.decode('utf8'))
                result = match.group(1)
                print(f'本次签到：{result}')
            elif '已经签到过啦，请明天再来！' in sign_response.content.decode('utf8'):
                result = f't98已经签到过啦！请不要重复签到！'
            else:
                result = f't98签到失败!请检查网页！!'
        else:
            result = f't98已经签到过啦！请不要重复签到！'
            print(result)
        # 检查当前积分与金币
        credit_url = f'{host}/home.php?mod=spacecp&ac=credit&op=base'
        credit_response = session.get(
            url=credit_url,
            headers={
                "User-Agent": user_agent,
                'referer': f"{host}/plugin.php?id=dd_sign:index",
            },
            cookies=cookies_dict,
        )
        print(f'积分金币页面详情：{credit_response.content.decode("utf8")}')

        pattern = re.compile(
            r'(金钱:\s)*<\/em>(\d+)|(色币:\s)*<\/em>(\d+)|(积分:\s)*<\/em>(\d+)|(评分:\s)*<\/em>(\d+)',
            re.S)
        matches = re.findall(pattern, credit_response.content.decode("utf8"))
        info = '，'.join([''.join(match) for match in matches])
        print(f'积分金币详情: {info}')
        msg = f"本次签到:{result}\n积分金币详情: {info}"
        print(msg)

    except Exception as e:
        msg = f'98签到失败：{e}'
        print(msg)
        print(traceback.format_exc(8))


if __name__ == "__main__":
    host = 'https://jq2t4.com'
    # host = 'https://www.b9m4w.com'
    # 设置访问地址
    # 设置账号密码
    username = 'ngfchl'
    password = 'T5!YM6*Y$MQ34P&z'
    cookie = '_safe=vqd37pjm4p5uodq339yzk6b7jdt6oich; PHPSESSID=gleblmbk3ald93mp00eahrn4bq; cPNj_2132_lastfp=ccbd90c11a5c245b96e894fe47dcf4be; cPNj_2132_saltkey=nzQg9IvR; cPNj_2132_lastvisit=1688177305; cPNj_2132_auth=ad70VV%2FLpk8c8bKFRCEjEcvRzwn9NF4H16V1JKrDYkaiZu6RLA9dAq%2Bv6on%2B37WtGRdyPa4T%2BIIU9RoMzga37EaRx7Q; cPNj_2132_lastcheckfeed=446742%7C1688195593; cPNj_2132_lip=180.98.138.85%2C1688180176; cPNj_2132_nofavfid=1; cPNj_2132_sid=0; cPNj_2132_ulastactivity=1688387106%7C0; cPNj_2132_lastact=1688387110%09misc.php%09patch'
    user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.58'

    sht_sign(host=host, username=username, password=password, cookie=cookie, user_agent=user_agent)
