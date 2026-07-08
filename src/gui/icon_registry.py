"""Central registry for GUI icon assets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
ICONS_DIR = ASSETS_DIR / "icons"

PAGE_ICONS: dict[str, str] = {
    "dashboard": "dashboard.svg",
    "sync": "sync.svg",
    "history": "history.svg",
    "task_management": "task_management.svg",
    "data_source": "data_source.svg",
    "forms": "forms.svg",
    "schedule": "schedule.svg",
    "diagnostics": "diagnostics.svg",
    "log_center": "log_center.svg",
    "settings": "settings.svg",
}

ACTION_ICONS: dict[str, str] = {
    "collapse_sidebar": "menu_fold.svg",
    "settings": "topbar_settings.svg",
    "help": "topbar_help.svg",
    "user": "topbar_user.svg",
    "chevron_down": "chevron_down.svg",
    "chevron_left": "chevron_left.svg",
    "chevron_right": "chevron_right.svg",
    "export": "export.svg",
    "filter": "filter.svg",
    "refresh": "refresh.svg",
    "copy": "copy.svg",
    "trash": "trash.svg",
    "close": "close.svg",
    "more": "more_horizontal.svg",
}

STATUS_ICONS: dict[str, str] = {
    "success": "status_ok.svg",
    "danger": "status_err.svg",
    "warning": "metric_pending_warning.svg",
    "neutral": "info.svg",
}

METRIC_ICONS: dict[str, str] = {
    "dashboard_trend": "metric_sync_count.svg",
    "dashboard_success_rate": "metric_success_rate.svg",
    "dashboard_failed": "metric_failed_task.svg",
    "dashboard_pending": "metric_pending_warning.svg",
    "dashboard_avg_time": "metric_avg_time.svg",
    "history_clock": "summary_clock.svg",
    "history_fail": "summary_fail.svg",
    "history_rows": "summary_rows.svg",
    "history_document": "summary_document.svg",
    "sync_mode": "sync_mode.svg",
    "sync_target": "sync_target.svg",
    "sync_progress": "sync_progress.svg",
    "sync_result": "sync_result.svg",
    "sync_record": "sync_record.svg",
    "sync_runtime": "sync_runtime.svg",
    "sync_status": "sync_status.svg",
}

HEALTH_ICONS: dict[str, str] = {
    "kingdee": "health_api.svg",
    "database": "health_database.svg",
    "scheduler": "health_scheduler.svg",
    "log": "health_log.svg",
}

PAGE_SECTION_ICONS: dict[str, str] = {
    "data_source_api": "data_source_api.svg",
    "data_source_database": "data_source_database.svg",
    "forms_configured": "forms_configured.svg",
    "forms_fields": "forms_fields.svg",
    "forms_missing": "forms_missing.svg",
    "forms_updated": "forms_updated.svg",
    "forms_validation_missing": "forms_validation_missing.svg",
    "forms_validation_type": "forms_validation_type.svg",
    "forms_validation_fix": "forms_validation_fix.svg",
    "diagnostic_api": "diagnostic_api.svg",
    "diagnostic_database": "diagnostic_database.svg",
    "diagnostic_field": "diagnostic_field.svg",
    "diagnostic_retry": "diagnostic_retry.svg",
    "diagnostic_suggestion": "diagnostic_suggestion.svg",
    "diagnostic_total": "diagnostic_total.svg",
    "log_total": "log_total.svg",
    "log_error": "log_error.svg",
    "log_warning": "log_warning.svg",
    "log_recent": "log_recent.svg",
    "log_size": "log_size.svg",
    "schedule_status": "schedule_status.svg",
    "schedule_running": "schedule_running.svg",
    "schedule_result": "schedule_result.svg",
    "schedule_heartbeat": "schedule_heartbeat.svg",
    "schedule_interval": "schedule_interval.svg",
    "schedule_last": "schedule_last.svg",
    "schedule_next": "schedule_next.svg",
    "schedule_success": "schedule_success.svg",
    "schedule_queue": "schedule_queue.svg",
}

_REGISTRIES = (
    PAGE_ICONS,
    ACTION_ICONS,
    STATUS_ICONS,
    METRIC_ICONS,
    HEALTH_ICONS,
    PAGE_SECTION_ICONS,
)


def normalize_source(source: str) -> str:
    """Return an icon filename without the optional icons/ prefix."""

    return source.removeprefix("icons/")


def icon_source(source: str) -> str:
    """Return the canonical icon-source property value used by widgets."""

    return f"icons/{normalize_source(source)}"


def icon_path(source: str) -> Path:
    """Return the absolute path for an icon source."""

    return ICONS_DIR / normalize_source(source)


def qicon(source: str) -> QIcon:
    """Create a QIcon for a registered or direct icon source."""

    return QIcon(str(icon_path(source)))


def page_icon_source(page_id: str) -> str:
    """Return the icon filename for a page id."""

    return PAGE_ICONS[page_id]


def token_source(token: str) -> str:
    """Resolve a semantic token or direct filename to an icon filename."""

    for registry in _REGISTRIES:
        if token in registry:
            return registry[token]
    return normalize_source(token)


def required_icon_files() -> set[str]:
    """Return all icon files required by the registry."""

    files: set[str] = set()
    for registry in _REGISTRIES:
        files.update(registry.values())
    return files
