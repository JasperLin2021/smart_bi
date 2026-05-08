from dataclasses import dataclass
from urllib.parse import urlencode

import httpx


WECHAT_WORK_PROVIDER = "wechat_work"
WECHAT_OAUTH_URL = "https://open.weixin.qq.com/connect/oauth2/authorize"
WECHAT_API_BASE = "https://qyapi.weixin.qq.com"


@dataclass
class WechatWorkUser:
    user_id: str
    name: str | None = None
    email: str | None = None
    mobile: str | None = None
    department_ids: list[str] | None = None


class WechatWorkClient:
    def __init__(self, corp_id: str, agent_id: str, app_secret: str, callback_url: str):
        self.corp_id = corp_id
        self.agent_id = agent_id
        self.app_secret = app_secret
        self.callback_url = callback_url

    def build_login_url(self, state: str) -> str:
        query = urlencode(
            {
                "appid": self.corp_id,
                "redirect_uri": self.callback_url,
                "response_type": "code",
                "scope": "snsapi_privateinfo",
                "state": state,
                "agentid": self.agent_id,
            }
        )
        return f"{WECHAT_OAUTH_URL}?{query}#wechat_redirect"

    def get_access_token(self) -> str:
        payload = self._get(
            "/cgi-bin/gettoken",
            {"corpid": self.corp_id, "corpsecret": self.app_secret},
        )
        token = payload.get("access_token")
        if not token:
            raise ValueError("企业微信未返回 access_token")
        return str(token)

    def get_user_id_by_code(self, code: str, access_token: str) -> str:
        payload = self._get(
            "/cgi-bin/auth/getuserinfo",
            {"access_token": access_token, "code": code},
        )
        user_id = payload.get("UserId") or payload.get("userid")
        if not user_id:
            raise ValueError("企业微信未返回 UserId")
        return str(user_id)

    def get_user(self, access_token: str, user_id: str) -> WechatWorkUser:
        payload = self._get(
            "/cgi-bin/user/get",
            {"access_token": access_token, "userid": user_id},
        )
        raw_departments = payload.get("department") or []
        return WechatWorkUser(
            user_id=str(payload.get("userid") or user_id),
            name=payload.get("name"),
            email=payload.get("email"),
            mobile=payload.get("mobile"),
            department_ids=[str(item) for item in raw_departments],
        )

    def send_textcard(
        self,
        access_token: str,
        to_user: str,
        title: str,
        content: str,
        url: str | None = None,
    ) -> None:
        self._post(
            "/cgi-bin/message/send",
            {"access_token": access_token},
            {
                "touser": to_user,
                "msgtype": "textcard",
                "agentid": self.agent_id,
                "textcard": {
                    "title": title,
                    "description": content,
                    "url": url or self.callback_url,
                },
                "enable_duplicate_check": 0,
            },
        )

    def _get(self, path: str, params: dict[str, str]) -> dict:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{WECHAT_API_BASE}{path}", params=params)
            response.raise_for_status()
            payload = response.json()
        self._ensure_success(payload)
        return payload

    def _post(self, path: str, params: dict[str, str], payload: dict) -> dict:
        with httpx.Client(timeout=10) as client:
            response = client.post(f"{WECHAT_API_BASE}{path}", params=params, json=payload)
            response.raise_for_status()
            data = response.json()
        self._ensure_success(data)
        return data

    @staticmethod
    def _ensure_success(payload: dict) -> None:
        errcode = payload.get("errcode", 0)
        if errcode not in (0, "0", None):
            errmsg = payload.get("errmsg") or "企业微信接口调用失败"
            raise ValueError(f"企业微信接口错误 {errcode}: {errmsg}")
