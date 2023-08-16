# encoding:utf-8
import json

import requests


def send_text(token: str, title: str, content: str, template: str = "markdown"):
    """
    push plus 通知推送
    :param template: 模板类型，可选：txt markdown json html
    :param token:
    :param title: 标题
    :param content: 内容
    :return:
    """
    url = 'http://www.pushplus.plus/send'
    data = {
        "token": token,
        "title": title,
        "content": content,
        "template": template,
    }
    try:
        body = json.dumps(data).encode(encoding='utf-8')
        headers = {'Content-Type': 'application/json'}
        res = requests.post(url, data=body, headers=headers)
        return res.json().get("msg")
    except Exception as e:
        return f'pushplus 消息推送失败！{e}'
