"""Notifications shared by several analysis tabs."""
from __future__ import annotations

from shiny import ui

from ..i18n import t

# One id for every tab's "data changed — re-run" notice: Shiny replaces a
# notification with the same id instead of stacking a second copy, so an ISA
# change that invalidates several tabs at once shows the notice once.
DATA_CHANGED_ID = "sespy-data-changed"


def notify_data_changed() -> None:
    """Tell the user that shown results predate the current data."""
    ui.notification_show(t("analysis.common.data_changed_rerun"),
                         duration=5, type="warning", id=DATA_CHANGED_ID)
