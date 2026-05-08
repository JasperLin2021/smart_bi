"""纷享销客 CRM 连接器。

认证方式：corpId + appId + appSecret 换取 corpAccessToken（有效期2小时）。
文档参考：https://www.fxiaoke.com/open/
"""
from __future__ import annotations
import time
from typing import Iterator

import requests

from .base import BaseConnector, ConnectorError, FieldMeta, ObjectMeta, register

_AUTH_URL = "https://api.fxiaoke.com/cgi/corpAccessToken/get/V2"
_BASE_URL = "https://api.fxiaoke.com"
_TIMEOUT = 20

# 纷享销客对象 API 路径映射
_OBJECT_API = {
    "Account":       "/cgi/crm/custom/data/query",   # 客户
    "Contact":       "/cgi/crm/custom/data/query",   # 联系人
    "SalesOrder":    "/cgi/crm/custom/data/query",   # 销售订单
    "Opportunity":   "/cgi/crm/custom/data/query",   # 商机
    "VisitRecord":   "/cgi/crm/custom/data/query",   # 拜访记录
    "Contract":      "/cgi/crm/custom/data/query",   # 合同
}


@register
class FenXiangConnector(BaseConnector):
    CONNECTOR_TYPE = "fenxiang"
    LABEL = "纷享销客"
    ICON = "fenxiang"

    def __init__(self, config: dict):
        super().__init__(config)
        self._token: str | None = None
        self._token_expires: float = 0.0
        self._current_open_user_id: str = ""

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        corp_id = self.config.get("corp_id", "")
        app_id = self.config.get("app_id", "")
        app_secret = self.config.get("app_secret", "")
        try:
            resp = requests.post(
                _AUTH_URL,
                json={"appId": app_id, "appSecret": app_secret, "permanentCode": self.config.get("permanent_code", "")},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise ConnectorError(f"纷享销客获取 Token 失败: {exc}") from exc
        if data.get("errorCode") != 0:
            raise ConnectorError(f"纷享销客 Token 失败: {data.get('errorMessage', data)}")
        self._token = data["corpAccessToken"]
        self._current_open_user_id = data.get("openUserId", "")
        self._corp_id = corp_id
        self._token_expires = time.time() + data.get("expiresIn", 7200)
        return self._token

    def _call(self, path: str, payload: dict) -> dict:
        token = self._get_token()
        payload.update({
            "corpAccessToken": token,
            "corpId": self.config.get("corp_id", ""),
            "currentOpenUserId": self._current_open_user_id,
        })
        try:
            resp = requests.post(f"{_BASE_URL}{path}", json=payload, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise ConnectorError(f"纷享销客 API 请求失败: {exc}") from exc
        if data.get("errorCode") != 0:
            raise ConnectorError(f"纷享销客返回错误: {data.get('errorMessage', data)}")
        return data

    def test_connection(self) -> tuple[bool, str]:
        try:
            self._call(
                "/cgi/crm/custom/data/query",
                {"apiName": "AccountObj", "data": {"dataObjectApiName": "AccountObj", "search_query_info": {"limit": 1, "offset": 0, "filters": []}}},
            )
            return True, "连接成功"
        except ConnectorError as exc:
            return False, str(exc)

    def list_objects(self) -> list[ObjectMeta]:
        return [
            ObjectMeta(
                name="Account",
                label="客户",
                description="CRM 客户档案",
                supports_incremental=True,
                incremental_field="last_modified_time",
                fields=[
                    FieldMeta("_id", "记录ID", "string"),
                    FieldMeta("name", "客户名称", "string"),
                    FieldMeta("account_type", "客户类型", "string"),
                    FieldMeta("industry", "行业", "string"),
                    FieldMeta("owner", "负责人", "string"),
                    FieldMeta("province", "省份", "string"),
                    FieldMeta("city", "城市", "string"),
                    FieldMeta("phone", "电话", "string"),
                    FieldMeta("annual_revenue", "年收入", "number"),
                    FieldMeta("employee_count", "员工人数", "number"),
                    FieldMeta("create_time", "创建时间", "datetime"),
                    FieldMeta("last_modified_time", "最后修改时间", "datetime"),
                ],
            ),
            ObjectMeta(
                name="Contact",
                label="联系人",
                description="客户联系人信息",
                supports_incremental=True,
                incremental_field="last_modified_time",
                fields=[
                    FieldMeta("_id", "记录ID", "string"),
                    FieldMeta("name", "姓名", "string"),
                    FieldMeta("account_id", "所属客户ID", "string"),
                    FieldMeta("title", "职位", "string"),
                    FieldMeta("mobile", "手机", "string"),
                    FieldMeta("email", "邮箱", "string"),
                    FieldMeta("department", "部门", "string"),
                    FieldMeta("create_time", "创建时间", "datetime"),
                    FieldMeta("last_modified_time", "最后修改时间", "datetime"),
                ],
            ),
            ObjectMeta(
                name="Opportunity",
                label="商机",
                description="销售商机跟进记录",
                supports_incremental=True,
                incremental_field="last_modified_time",
                fields=[
                    FieldMeta("_id", "记录ID", "string"),
                    FieldMeta("name", "商机名称", "string"),
                    FieldMeta("account_id", "客户ID", "string"),
                    FieldMeta("stage", "销售阶段", "string"),
                    FieldMeta("amount", "预计金额", "number"),
                    FieldMeta("close_date", "预计成交日期", "date"),
                    FieldMeta("probability", "赢单概率(%)", "number"),
                    FieldMeta("owner", "负责人", "string"),
                    FieldMeta("create_time", "创建时间", "datetime"),
                    FieldMeta("last_modified_time", "最后修改时间", "datetime"),
                ],
            ),
            ObjectMeta(
                name="SalesOrder",
                label="销售订单",
                description="CRM 销售订单及明细",
                supports_incremental=True,
                incremental_field="last_modified_time",
                fields=[
                    FieldMeta("_id", "记录ID", "string"),
                    FieldMeta("name", "订单编号", "string"),
                    FieldMeta("account_id", "客户ID", "string"),
                    FieldMeta("status", "订单状态", "string"),
                    FieldMeta("amount", "订单金额", "number"),
                    FieldMeta("discount_amount", "优惠金额", "number"),
                    FieldMeta("pay_amount", "实付金额", "number"),
                    FieldMeta("order_date", "下单日期", "date"),
                    FieldMeta("owner", "负责人", "string"),
                    FieldMeta("create_time", "创建时间", "datetime"),
                    FieldMeta("last_modified_time", "最后修改时间", "datetime"),
                ],
            ),
            ObjectMeta(
                name="VisitRecord",
                label="拜访记录",
                description="销售人员客户拜访记录",
                supports_incremental=True,
                incremental_field="last_modified_time",
                fields=[
                    FieldMeta("_id", "记录ID", "string"),
                    FieldMeta("account_id", "客户ID", "string"),
                    FieldMeta("visit_type", "拜访方式", "string"),
                    FieldMeta("visit_date", "拜访日期", "date"),
                    FieldMeta("owner", "拜访人", "string"),
                    FieldMeta("purpose", "拜访目的", "string"),
                    FieldMeta("result", "拜访结果", "string"),
                    FieldMeta("create_time", "创建时间", "datetime"),
                    FieldMeta("last_modified_time", "最后修改时间", "datetime"),
                ],
            ),
            ObjectMeta(
                name="Contract",
                label="合同",
                description="客户合同档案",
                supports_incremental=True,
                incremental_field="last_modified_time",
                fields=[
                    FieldMeta("_id", "记录ID", "string"),
                    FieldMeta("name", "合同编号", "string"),
                    FieldMeta("account_id", "客户ID", "string"),
                    FieldMeta("amount", "合同金额", "number"),
                    FieldMeta("start_date", "合同开始日期", "date"),
                    FieldMeta("end_date", "合同结束日期", "date"),
                    FieldMeta("status", "合同状态", "string"),
                    FieldMeta("owner", "负责人", "string"),
                    FieldMeta("create_time", "创建时间", "datetime"),
                    FieldMeta("last_modified_time", "最后修改时间", "datetime"),
                ],
            ),
        ]

    def fetch_pages(
        self,
        object_name: str,
        filters: dict | None = None,
        incremental_field: str | None = None,
        watermark: str | None = None,
    ) -> Iterator[list[dict]]:
        # 纷享销客对象 API 名称映射
        api_name_map = {
            "Account":     "AccountObj",
            "Contact":     "ContactObj",
            "Opportunity": "OpportunityObj",
            "SalesOrder":  "SalesOrderObj",
            "VisitRecord": "VisitRecordObj",
            "Contract":    "ContractObj",
        }
        api_name = api_name_map.get(object_name)
        if not api_name:
            raise ConnectorError(f"不支持的对象: {object_name}")

        extra_filters = []
        if watermark and incremental_field:
            extra_filters.append({
                "field_name": incremental_field,
                "field_values": [watermark],
                "operator": "GT",
            })

        offset = 0
        limit = 50
        while True:
            payload = {
                "apiName": api_name,
                "data": {
                    "dataObjectApiName": api_name,
                    "search_query_info": {
                        "limit": limit,
                        "offset": offset,
                        "filters": extra_filters,
                        "orders": [{"fieldName": incremental_field or "create_time", "isAsc": "true"}],
                    },
                },
            }
            data = self._call("/cgi/crm/custom/data/query", payload)
            items = data.get("data", {}).get("dataList", [])
            if not items:
                break
            # Flatten field_data_list into a plain dict
            yield [
                {f["fieldName"]: f.get("value") for f in (item.get("fieldData", item.get("field_data_list", [])))}
                for item in items
            ]
            total = data.get("data", {}).get("total", 0)
            offset += limit
            if offset >= total:
                break
