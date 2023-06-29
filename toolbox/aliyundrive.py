import calendar
import datetime
import json
import logging
from typing import List

import requests
from django.core.cache import cache


# refresh_token生成器
def refresh_token_generator(refresh_token_list):
    for refresh_token_item in refresh_token_list:
        yield refresh_token_item


# 更新 access_token
def update_access_token(query_body, account):
    update_access_token_url = 'https://auth.aliyundrive.com/v2/account/token'
    headers = {'Content-Type': 'application/json'}
    error_message = [account, '更新 access_token 失败']
    response = requests.post(url=update_access_token_url, data=json.dumps(query_body), headers=headers)
    json_data = response.json()
    if 'code' in json_data:
        if json_data['code'] == 'RefreshTokenExpired' or json_data['code'] == 'InvalidParameter.RefreshToken':
            error_message.append('refresh_token已过期或无效')
        else:
            error_message.append(json_data['message'])
        raise Exception(','.join(error_message))
    else:
        return json_data['nick_name'], json_data['refresh_token'], json_data['access_token']


# 执行签到
def sign_in(query_body, access_token, account, welfare):
    sign_in_url = 'https://member.aliyundrive.com/v1/activity/sign_in_list'
    headers = {
        'Authorization': 'Bearer ' + access_token,
        'Content-Type': 'application/json'
    }
    send_message = [account]
    response = requests.post(url=sign_in_url, data=json.dumps(query_body), headers=headers)
    json_data = response.json()
    if not json_data['success']:
        send_message.append('签到失败')
        raise Exception(','.join(send_message))
    else:
        try:
            send_message.append('签到成功')
            send_message.append('本月累计签到 ' + str(json_data['result']['signInCount']) + ' 天')
            if welfare:
                reward_info = get_reward(access_token, json_data['result']['signInCount'])
                send_message.append(f'本次签到获得{reward_info.get("name", "")}{reward_info.get("description", "")}')
            send_message_str = ','.join(send_message)
            logging.info(f'[aliyunpan_signin]:{send_message_str}')
            return send_message_str
        except Exception as e:
            send_message.append('但是解析签到信息失败，请去阿里云盘APP查看。')
            send_message_str = ','.join(send_message)
            logging.info(f'[aliyunpan_signin]:{send_message_str}')
            raise Exception(send_message_str)


# 领取奖励
def get_reward(access_token, sign_in_day):
    reward_url = "https://member.aliyundrive.com/v1/activity/sign_in_reward?_rx-s=mobile"
    headers = {
        "authorization": access_token,
        "Content-Type": "application/json"
    }
    data = {"signInDay": sign_in_day}
    response = requests.post(reward_url, headers=headers, json=data)
    json_data = response.json()
    if not json_data["success"]:
        raise Exception(json_data["message"])
    return json_data["result"]


# 主程序
def aliyundrive_sign_in(refresh_token_list: List[str], welfare: bool = True):
    message_list = []
    refresh_token_gen = refresh_token_generator(refresh_token_list)
    for refresh_token_item in refresh_token_gen:
        aliyundrive_sign_in_list = cache.get(f"aliyundrive_sign_in_list", [])
        if refresh_token_item in aliyundrive_sign_in_list:
            message_list.append(f'{refresh_token_item} 已签到,跳过')
            continue
        query_body = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token_item
        }
        try:
            nick_name, refresh_token, access_token = update_access_token(query_body, refresh_token_item)
            message = sign_in(query_body, access_token, nick_name, welfare)
            message_list.append(message)
            # 签到成功的
            # 将 refresh_token_item 添加到已签到列表中
            aliyundrive_sign_in_list.append(refresh_token_item)
            # 获取当前时间
            now = datetime.datetime.now()

            # 计算当天结束的时间
            end_of_day = now.replace(hour=23, minute=59, second=59)

            # 计算当前时间到当天结束的时间间隔
            expiration = end_of_day - now

            # 将数据存入缓存并设置有效期
            cache.set(f"aliyundrive_sign_in_list", aliyundrive_sign_in_list, expiration)
        except Exception as e:
            message_list.append(str(e))
    messages = '\n'.join(message_list)
    today = datetime.date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    if not welfare and today.day == last_day:
        messages += f'\n月底啦，快去领奖励。'
    return messages
