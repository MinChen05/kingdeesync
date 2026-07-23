"""Forms management routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.config.config_manager import config_manager

router = APIRouter()


@router.get("")
def get_forms():
    """Get all syncable forms with their mappings."""
    table_mapping = config_manager.get_table_mapping()

    forms = []
    for form_name, table_name in table_mapping.items():
        inc_field = config_manager.get_increment_field(form_name) or ""
        enabled = config_manager.get_form_enabled(form_name)
        forms.append({
            "form_name": form_name,
            "table_name": table_name,
            "enabled": enabled,
            "incremental_field": inc_field,
        })

    return {
        "ok": True,
        "data": forms,
    }


@router.put("/{form_name}")
def update_form(form_name: str, payload: dict):
    """Update form configuration (enabled, incremental_field)."""
    table_mapping = config_manager.get_table_mapping()

    if form_name not in table_mapping:
        raise HTTPException(status_code=404, detail=f"Form not found: {form_name}")

    if "enabled" in payload:
        config_manager.set_form_enabled(form_name, bool(payload["enabled"]))

    if "incremental_field" in payload:
        field = str(payload["incremental_field"]).strip()
        if field:
            config_manager.set_increment_field(form_name, field)
        else:
            config_manager.remove_increment_field(form_name)

    return {"ok": True}
