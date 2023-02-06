from ninja import Schema
from pydantic.schema import Optional


# class BaseResponse(Schema):


class CommonResponse(Schema):
    code: int
    data: object
    msg: Optional[str]

    """
    统一的json返回格式
    """

    def __init__(self, code: int = 0, data: object = None, msg: str = ''):
        super().__init__(code=code, data=data, msg=msg)
        # self.data = data
        # self.code = code
        # if msg is None:
        #     self.msg = ''
        # else:
        #     self.msg = msg

    @classmethod
    def success(cls, code=0, data=None, msg=''):
        return cls(code, data, msg)

    @classmethod
    def error(cls, code=-1, data=None, msg=''):
        return cls(code, data, msg)

    def to_dict(self):
        return {
            "code": self.code,
            "msg": self.msg,
            "data": self.data
        }
