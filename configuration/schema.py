from typing import Optional, List

from ninja import Schema


class GitLog(Schema):
    date: str
    data: str
    hex: str


class UpdateSchemaOut(Schema):
    local_logs: GitLog
    update_notes: List[GitLog]
    update: bool


class UserIn(Schema):
    username: str
    password: str


class SettingsIn(Schema):
    name: str
    content: str


class NotifySchema(Schema):
    id: Optional[int]
    name: str
    enable: bool = True
    corpid: Optional[str]
    corpsecret: str
    agentid: Optional[str]
    touser: Optional[str]
    custom_server: Optional[str]


class WechatSignatureSchema(Schema):
    msg_signature: str
    timestamp: int
    nonce: int
    echostr: str
