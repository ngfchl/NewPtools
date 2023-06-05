from typing import Optional

from ninja import Schema


class UpdateSchemaOut(Schema):
    cid: str
    delta: str
    restart: str
    local_logs: list
    update_notes: list
    update: str
    update_tip: str
    branch: str


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
