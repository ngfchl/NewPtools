from typing import Generic, TypeVar, List

from pydantic.generics import GenericModel
from pydantic.schema import Optional

# class BaseResponse(Schema):

T = TypeVar('T')


class CommonResponse(GenericModel, Generic[T]):
    code: int
    msg: Optional[str]
    data: T

    """
    统一的json返回格式
    """

    def __init__(self, code: int = 0, data: object = None, msg: str = ''):
        super().__init__(code=code, data=data, msg=msg)
        # self.data = data
        # self.code = code.3333
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


class CommonPaginateSchema(GenericModel, Generic[T]):
    per_page: int
    total: int
    items: List[T]
