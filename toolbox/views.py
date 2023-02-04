import toml as toml


# Create your views here.

def parse_token(cmd):
    """从配置文件解析获取相关项目"""
    data = toml.load('db/ptools.toml')
    return data.get(cmd)
