"""易仓 WMS 连接器（EzWMS OpenAPI）。

认证方式：client_id + client_secret 换取 access_token（OAuth2 client_credentials）。
文档参考：https://open.eccang.com
"""
from __future__ import annotations
import time
from typing import Iterator

import requests

from .base import BaseConnector, ConnectorError, FieldMeta, ObjectMeta, register

_TOKEN_URL = "https://open.eccang.com/oauth2/access_token"
_BASE_URL = "https://open.eccang.com"
_TIMEOUT = 20


@register
class YiCangConnector(BaseConnector):
    CONNECTOR_TYPE = "yicang"
    LABEL = "易仓"
    ICON = "yicang"

    def __init__(self, config: dict):
        super().__init__(config)
        self._token: str | None = None
        self._token_expires: float = 0.0

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        client_id = self.config.get("client_id", "")
        client_secret = self.config.get("client_secret", "")
        try:
            resp = requests.post(
                _TOKEN_URL,
                data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise ConnectorError(f"易仓获取 Token 失败: {exc}") from exc
        if "access_token" not in data:
            raise ConnectorError(f"易仓 Token 响应异常: {data}")
        self._token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 7200)
        return self._token

    def _call(self, path: str, params: dict | None = None, payload: dict | None = None) -> dict:
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            if payload is not None:
                resp = requests.post(f"{_BASE_URL}{path}", json=payload, headers=headers, timeout=_TIMEOUT)
            else:
                resp = requests.get(f"{_BASE_URL}{path}", params=params, headers=headers, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise ConnectorError(f"易仓 API 请求失败: {exc}") from exc
        if data.get("code") not in (0, 200, "0", "200", None):
            raise ConnectorError(f"易仓返回错误: {data.get('message', data)}")
        return data.get("data", data)

    def test_connection(self) -> tuple[bool, str]:
        try:
            self._call("/api/warehouse/list", params={"pageNo": 1, "pageSize": 1})
            return True, "连接成功"
        except ConnectorError as exc:
            return False, str(exc)

    def list_objects(self) -> list[ObjectMeta]:
        return [
            ObjectMeta(
                name="inbound_orders",
                label="入库单",
                description="入库通知单及到货明细",
                supports_incremental=True,
                incremental_field="updateTime",
                fields=[
                    FieldMeta("referenceNo", "参考号", "string"),
                    FieldMeta("warehouseCode", "仓库编码", "string"),
                    FieldMeta("warehouseName", "仓库名称", "string"),
                    FieldMeta("status", "状态", "string"),
                    FieldMeta("expectedQty", "预期数量", "number"),
                    FieldMeta("receivedQty", "实收数量", "number"),
                    FieldMeta("createTime", "创建时间", "datetime"),
                    FieldMeta("updateTime", "更新时间", "datetime"),
                    FieldMeta("items", "明细(JSON)", "string"),
                ],
            ),
            ObjectMeta(
                name="outbound_orders",
                label="出库单",
                description="出库订单及发货明细",
                supports_incremental=True,
                incremental_field="updateTime",
                fields=[
                    FieldMeta("orderNo", "出库单号", "string"),
                    FieldMeta("referenceNo", "参考号(平台单号)", "string"),
                    FieldMeta("warehouseCode", "仓库编码", "string"),
                    FieldMeta("warehouseName", "仓库名称", "string"),
                    FieldMeta("status", "状态", "string"),
                    FieldMeta("shippedQty", "发货数量", "number"),
                    FieldMeta("carrierCode", "承运商编码", "string"),
                    FieldMeta("trackingNo", "快递单号", "string"),
                    FieldMeta("createTime", "创建时间", "datetime"),
                    FieldMeta("updateTime", "更新时间", "datetime"),
                    FieldMeta("items", "明细(JSON)", "string"),
                ],
            ),
            ObjectMeta(
                name="inventory",
                label="库存快照",
                description="各仓库当前 SKU 可用库存",
                supports_incremental=False,
                fields=[
                    FieldMeta("sku", "SKU编码", "string"),
                    FieldMeta("productName", "品名", "string"),
                    FieldMeta("warehouseCode", "仓库编码", "string"),
                    FieldMeta("availableQty", "可用库存", "number"),
                    FieldMeta("totalQty", "总库存", "number"),
                    FieldMeta("lockQty", "锁定库存", "number"),
                    FieldMeta("onWayQty", "在途库存", "number"),
                ],
            ),
            ObjectMeta(
                name="products",
                label="产品档案",
                description="SKU 基础信息及包装规格",
                supports_incremental=True,
                incremental_field="updateTime",
                fields=[
                    FieldMeta("sku", "SKU编码", "string"),
                    FieldMeta("productName", "产品名称", "string"),
                    FieldMeta("category", "品类", "string"),
                    FieldMeta("weight", "重量(g)", "number"),
                    FieldMeta("length", "长(cm)", "number"),
                    FieldMeta("width", "宽(cm)", "number"),
                    FieldMeta("height", "高(cm)", "number"),
                    FieldMeta("barcode", "条码", "string"),
                    FieldMeta("createTime", "创建时间", "datetime"),
                    FieldMeta("updateTime", "更新时间", "datetime"),
                ],
            ),
            ObjectMeta(
                name="warehouses",
                label="仓库列表",
                description="已接入的仓库信息",
                supports_incremental=False,
                fields=[
                    FieldMeta("warehouseCode", "仓库编码", "string"),
                    FieldMeta("warehouseName", "仓库名称", "string"),
                    FieldMeta("country", "国家", "string"),
                    FieldMeta("type", "仓库类型", "string"),
                    FieldMeta("status", "状态", "string"),
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
        filters = filters or {}
        path_map = {
            "inbound_orders": "/api/inbound/list",
            "outbound_orders": "/api/outbound/list",
            "inventory": "/api/inventory/list",
            "products": "/api/product/list",
            "warehouses": "/api/warehouse/list",
        }
        path = path_map.get(object_name)
        if not path:
            raise ConnectorError(f"不支持的对象: {object_name}")

        page = 1
        while True:
            params: dict = {"pageNo": page, "pageSize": 50, **filters}
            if watermark and incremental_field:
                params["startTime"] = watermark
            data = self._call(path, params=params)
            items = data.get("list") or data.get("records") or (data if isinstance(data, list) else [])
            if not items:
                break
            yield items
            total = data.get("total", 0) if isinstance(data, dict) else 0
            if page * 50 >= total:
                break
            page += 1
