class CommonResponse:
    """
    统一的json返回格式
    """

    def __init__(self, data, code, msg):
        self.data = data
        self.code = code
        if msg is None:
            self.msg = ''
        else:
            self.msg = msg

    @classmethod
    def success(cls, data=None, status=0, msg=None):
        return cls(data, status, msg)

    @classmethod
    def error(cls, data=None, status=-1, msg=None):
        return cls(data, status, msg)

    def to_dict(self):
        return {
            "code": self.code,
            "msg": self.msg,
            "data": self.data
        }
