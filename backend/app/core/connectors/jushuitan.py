"""聚水潭 ERP 连接器（开放平台 v1/v2 API）。

认证方式：app_key + app_secret，每次请求使用 HMAC-MD5 签名。
文档参考：https://openweb.jushuitan.com/dev-doc
"""
from __future__ import annotations
import hashlib
import hmac
import json
import time
from typing import Iterator

import requests

from .base import BaseConnector, ConnectorError, FieldMeta, ObjectMeta, register

_BASE_URL = "https://openapi.erp.jushuitan.com"
_TIMEOUT = 20


def _sign(app_key: str, app_secret: str, params: dict) -> str:
    """聚水潭签名：将所有参数按 key 排序后拼接，附加 secret，MD5。"""
    sorted_items = sorted(params.items())
    sign_str = app_secret + "".join(f"{k}{v}" for k, v in sorted_items) + app_secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


@register
class JuShuiTanConnector(BaseConnector):
    CONNECTOR_TYPE = "jushuitan"
    LABEL = "聚水潭"
    ICON = "jst"

    def _call(self, path: str, biz_params: dict) -> dict:
        app_key = self.config.get("app_key", "")
        app_secret = self.config.get("app_secret", "")
        access_token = self.config.get("access_token", "")
        ts = int(time.time())
        params = {
            "app_key": app_key,
            "access_token": access_token,
            "timestamp": ts,
            "version": "2",
            "charset": "utf-8",
            "biz": json.dumps(biz_params, ensure_ascii=False),
        }
        params["sign"] = _sign(app_key, app_secret, params)
        try:
            resp = requests.post(f"{_BASE_URL}{path}", data=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise ConnectorError(f"聚水潭 API 请求失败: {exc}") from exc
        if data.get("code") != 0:
            raise ConnectorError(f"聚水潭返回错误: {data.get('msg', data)}")
        return data.get("data", {})

    def test_connection(self) -> tuple[bool, str]:
        try:
            self._call("/open/jushuitan/shop/list/query", {"page_index": 1, "page_size": 1})
            return True, "连接成功"
        except ConnectorError as exc:
            return False, str(exc)

    def list_objects(self) -> list[ObjectMeta]:
        return [
            ObjectMeta(
                name="orders",
                label="销售订单",
                description="线上/线下销售订单（含子项明细）",
                supports_incremental=True,
                incremental_field="modified",
                fields=[
                    FieldMeta("so_id", "订单ID", "string"),
                    FieldMeta("shop_id", "店铺ID", "number"),
                    FieldMeta("shop_name", "店铺名称", "string"),
                    FieldMeta("status", "订单状态", "string"),
                    FieldMeta("pay_time", "付款时间", "datetime"),
                    FieldMeta("send_time", "发货时间", "datetime"),
                    FieldMeta("created", "创建时间", "datetime"),
                    FieldMeta("modified", "修改时间", "datetime"),
                    FieldMeta("receiver_name", "收货人", "string"),
                    FieldMeta("receiver_mobile", "收货手机", "string"),
                    FieldMeta("receiver_state", "省份", "string"),
                    FieldMeta("receiver_city", "城市", "string"),
                    FieldMeta("goods_amount", "商品金额", "number"),
                    FieldMeta("post_amount", "运费", "number"),
                    FieldMeta("discount_amount", "优惠金额", "number"),
                    FieldMeta("pay_amount", "实付金额", "number"),
                    FieldMeta("logistics_company", "物流公司", "string"),
                    FieldMeta("l_id", "快递单号", "string"),
                    FieldMeta("platform", "平台", "string"),
                    FieldMeta("sku_list", "SKU明细(JSON)", "string"),
                ],
            ),
            ObjectMeta(
                name="purchase_orders",
                label="采购订单",
                description="采购单据，含到货明细",
                supports_incremental=True,
                incremental_field="modified",
                fields=[
                    FieldMeta("po_id", "采购单ID", "string"),
                    FieldMeta("supplier_name", "供应商", "string"),
                    FieldMeta("wms_co_id", "仓库ID", "number"),
                    FieldMeta("status", "状态", "string"),
                    FieldMeta("created", "创建时间", "datetime"),
                    FieldMeta("modified", "修改时间", "datetime"),
                    FieldMeta("total_amount", "采购总额", "number"),
                    FieldMeta("items", "采购明细(JSON)", "string"),
                ],
            ),
            ObjectMeta(
                name="inventory",
                label="库存快照",
                description="当前各仓库 SKU 库存数量",
                supports_incremental=False,
                fields=[
                    FieldMeta("sku_id", "SKUID", "number"),
                    FieldMeta("i_id", "货品编码", "string"),
                    FieldMeta("name", "货品名称", "string"),
                    FieldMeta("wms_co_id", "仓库ID", "number"),
                    FieldMeta("qty", "可用库存", "number"),
                    FieldMeta("lock_qty", "锁定库存", "number"),
                    FieldMeta("on_way_qty", "在途库存", "number"),
                ],
            ),
            ObjectMeta(
                name="sku",
                label="商品SKU",
                description="所有 SKU 基础信息",
                supports_incremental=True,
                incremental_field="modified",
                fields=[
                    FieldMeta("sku_id", "SKUID", "number"),
                    FieldMeta("i_id", "货品编码", "string"),
                    FieldMeta("name", "货品名称", "string"),
                    FieldMeta("category", "类目", "string"),
                    FieldMeta("cost_price", "成本价", "number"),
                    FieldMeta("sale_price", "销售价", "number"),
                    FieldMeta("weight", "重量(g)", "number"),
                    FieldMeta("bar_code", "条码", "string"),
                    FieldMeta("modified", "修改时间", "datetime"),
                ],
            ),
            ObjectMeta(
                name="refund_orders",
                label="退货退款单",
                description="售后退货及退款记录",
                supports_incremental=True,
                incremental_field="modified",
                fields=[
                    FieldMeta("rs_id", "退货单ID", "string"),
                    FieldMeta("so_id", "原订单ID", "string"),
                    FieldMeta("status", "状态", "string"),
                    FieldMeta("refund_amount", "退款金额", "number"),
                    FieldMeta("reason", "退货原因", "string"),
                    FieldMeta("created", "创建时间", "datetime"),
                    FieldMeta("modified", "修改时间", "datetime"),
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
            "orders": "/open/jushuitan/order/list/query",
            "purchase_orders": "/open/jushuitan/purchase/list/query",
            "inventory": "/open/jushuitan/inventory/list/query",
            "sku": "/open/jushuitan/sku/list/query",
            "refund_orders": "/open/jushuitan/refund/list/query",
        }
        path = path_map.get(object_name)
        if not path:
            raise ConnectorError(f"不支持的对象: {object_name}")

        page_index = 1
        while True:
            biz: dict = {"page_index": page_index, "page_size": 50, **filters}
            if watermark and incremental_field:
                biz[f"start_{incremental_field}"] = watermark
            data = self._call(path, biz)
            # 聚水潭返回结构通常为 {"datas": [...], "total_count": N}
            items = data.get("datas") or data.get("data") or []
            if not items:
                break
            yield items
            total = data.get("total_count", 0)
            if page_index * 50 >= total:
                break
            page_index += 1
