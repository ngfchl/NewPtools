import ipaddress
import re


def is_valid_ip_address(ip_str):
    """
    判断字符串是否为ip地址
    :param ip_str:
    :return:
    """
    try:
        ipaddress.IPv4Address(ip_str)
        return True
    except ipaddress.AddressValueError:
        pass

    try:
        ipaddress.IPv6Address(ip_str)
        return True
    except ipaddress.AddressValueError:
        pass

    return False


def extract_storage_size(input_string):
    """
    从字符串正则解析文件大小
    :param input_string:
    :return: ‘’MB，GB，TB，PB
    """
    # 定义正则表达式
    pattern = re.compile(r'(\d+(\.\d+)?)\s+(B|KB|MB|GB|TB|PB)')

    # 使用正则表达式进行匹配
    match = pattern.search(input_string)

    # 提取匹配的结果
    if match:
        value = float(match.group(1))
        unit = match.group(3)
        return f"{value} {unit}"
    else:
        return "0"
