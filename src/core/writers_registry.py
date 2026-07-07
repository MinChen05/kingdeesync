"""Registry for domain-specific table writers."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

from src.core.masterdata_writer import (
    insert_assistantdata,
    insert_bd_material,
    insert_bd_stock,
    insert_bos_assistantdata_detail,
    insert_customer_data,
    insert_eng_bom,
    insert_eng_bom_child,
    insert_stk_inventory,
)
from src.core.production_writer import (
    insert_prd_instock,
    insert_prd_moentry,
    insert_prd_ppbom,
    insert_prd_ppbom_entry,
    insert_prd_ppbom_main,
    insert_production_orders,
)
from src.core.sales_writer import (
    insert_ap_payable,
    insert_ar_receivable,
    insert_delivery_notice,
    insert_forecast_orders,
    insert_purchase_instock,
    insert_purchase_order,
    insert_sales_orders,
    insert_sales_outstock,
    insert_sales_returnstock,
    insert_sub_subreqorder,
)

WriterFunc = Callable[[Any, List[Dict]], int]

WRITER_REGISTRY: Dict[str, WriterFunc] = {
    "insert_sales_orders": insert_sales_orders,
    "insert_sales_returnstock": insert_sales_returnstock,
    "insert_sales_outstock": insert_sales_outstock,
    "insert_delivery_notice": insert_delivery_notice,
    "insert_forecast_orders": insert_forecast_orders,
    "insert_purchase_order": insert_purchase_order,
    "insert_purchase_instock": insert_purchase_instock,
    "insert_sub_subreqorder": insert_sub_subreqorder,
    "insert_ap_payable": insert_ap_payable,
    "insert_ar_receivable": insert_ar_receivable,
    "insert_production_orders": insert_production_orders,
    "insert_prd_moentry": insert_prd_moentry,
    "insert_prd_ppbom": insert_prd_ppbom,
    "insert_prd_ppbom_entry": insert_prd_ppbom_entry,
    "insert_prd_ppbom_main": insert_prd_ppbom_main,
    "insert_prd_instock": insert_prd_instock,
    "insert_customer_data": insert_customer_data,
    "insert_stk_inventory": insert_stk_inventory,
    "insert_bd_material": insert_bd_material,
    "insert_bd_stock": insert_bd_stock,
    "insert_bos_assistantdata_detail": insert_bos_assistantdata_detail,
    "insert_assistantdata": insert_assistantdata,
    "insert_eng_bom": insert_eng_bom,
    "insert_eng_bom_child": insert_eng_bom_child,
}


class WriterRegistry:
    """Resolves writer names from tables.json to concrete callables."""

    def __init__(self, *, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self._writers = dict(WRITER_REGISTRY)

    def has(self, method_name: str) -> bool:
        return method_name in self._writers

    def get(self, method_name: str) -> WriterFunc:
        writer = self._writers.get(method_name)
        if writer is None:
            known = ", ".join(sorted(self._writers))
            raise KeyError(f"unknown writer '{method_name}'. known writers: {known}")
        return writer

    def execute(self, manager: Any, method_name: str, data: List[Dict]) -> int:
        writer = self.get(method_name)
        return writer(manager, data)

    def missing_methods(self, insert_method_map: Dict[str, str]) -> Dict[str, str]:
        return {
            form_name: method_name
            for form_name, method_name in insert_method_map.items()
            if method_name and method_name not in self._writers
        }

    def known_methods(self) -> List[str]:
        return sorted(self._writers)
