"""Behaviour Over Time (BOT) analysis module.

Mirrors `modules/analysis_bot.R` (489 LOC). Per-element time-series view
with three input modes (manual entry, CSV upload, ISA-derived synthetic),
trend and moving-average overlays, summary statistics, and a data
table + CSV download.

Pattern matches `analysis_metrics.py` (matplotlib via @render.plot, no pyvis)
and `analysis_boolean.py` (symmetric error handling via stored error string).
"""
from __future__ import annotations

from io import BytesIO

import numpy as np
import pandas as pd
from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..data_structure import Project
from ..event_bus import EventBus
from ..i18n import Translator, t

_YEAR_COL_CANDIDATES = ("year",)
_VALUE_COL_CANDIDATES = ("value", "measurement")


def _match_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    """Return the first column whose lowercase form matches a candidate, or None."""
    lower = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand in lower:
            return lower[cand]
    return None


def _compute_trend(years: np.ndarray, values: np.ndarray) -> tuple[float, float] | None:
    """Linear regression. Returns (slope, intercept) or None if degenerate."""
    if len(years) < 2:
        return None
    try:
        slope, intercept = np.polyfit(years, values, 1)
        return float(slope), float(intercept)
    except (ValueError, np.linalg.LinAlgError):
        return None


def _moving_average(values: np.ndarray, window: int) -> np.ndarray | None:
    """Centred moving average. Returns None if window > len(values)."""
    if len(values) < window or window < 2:
        return None
    return pd.Series(values).rolling(window=window, center=True).mean().to_numpy()


@module.ui
def analysis_bot_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("bot.title")),
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5(t("bot.element_picker")),
                ui.output_ui("element_picker_ui"),
                ui.tags.hr(),
                ui.h5(t("bot.data_source")),
                ui.input_radio_buttons(
                    "data_source",
                    None,
                    {
                        "manual": t("bot.source_manual"),
                        "csv": t("bot.source_csv"),
                        "isa": t("bot.source_isa"),
                    },
                    selected="manual",
                ),
                ui.tags.hr(),
                ui.output_ui("input_panel"),
                ui.tags.hr(),
                ui.input_slider(
                    "year_range",
                    t("bot.year_range"),
                    min=1950, max=2030, value=(1950, 2030), step=1, sep="",
                ),
                ui.input_checkbox("show_trend", t("bot.show_trend"), value=True),
                ui.input_checkbox("show_moving_avg", t("bot.show_moving_avg"), value=False),
                ui.input_slider(
                    "window_size", t("bot.window_size"),
                    min=2, max=10, value=3, step=1,
                ),
                width=300,
            ),
            ui.navset_tab(
                ui.nav_panel(
                    t("bot.tab_timeseries"),
                    ui.output_plot("bot_plot", height="320px"),
                    ui.tags.hr(),
                    ui.output_ui("bot_summary"),
                ),
                ui.nav_panel(
                    t("bot.tab_data"),
                    ui.output_data_frame("bot_table"),
                    ui.tags.hr(),
                    ui.download_button("bot_download", t("bot.download_csv")),
                ),
                id="bot_tabs",
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def analysis_bot_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    # Per-element time-series data: dict keyed by element_id → DataFrame[Year, Value].
    bot_data_store: reactive.Value[dict[str, pd.DataFrame]] = reactive.value({})
    bot_error_store: reactive.Value[str | None] = reactive.value(None)

    @output
    @render.ui
    def element_picker_ui():
        event_bus.isa_change.get()
        elements = project_data.get().isa_data.elements
        if not elements:
            return ui.tags.p(t("bot.no_element_selected"), class_="text-muted")
        choices = {el.id: f"{el.type} · {el.label}" for el in elements}
        return ui.input_selectize("element", None, choices=choices)

    @reactive.effect
    @reactive.event(input.add_point, ignore_init=True)
    def _handle_manual_add() -> None:
        eid = input.element()
        if not eid:
            return  # silent no-op; spec §4 validation rule
        try:
            year = int(input.year() or 0)
            value = float(input.value() or 0)
        except (TypeError, ValueError):
            bot_error_store.set("Invalid year or value.")
            return
        store = dict(bot_data_store.get())  # copy for immutable swap
        existing = store.get(eid)
        if existing is None or existing.empty:
            store[eid] = pd.DataFrame({"Year": [year], "Value": [value]})
        else:
            mask = existing["Year"] == year
            if mask.any():
                # Match on year only — replace value.
                updated = existing.copy()
                updated.loc[mask, "Value"] = value
                store[eid] = updated
            else:
                store[eid] = pd.concat(
                    [existing, pd.DataFrame({"Year": [year], "Value": [value]})],
                    ignore_index=True,
                )
        bot_data_store.set(store)
        bot_error_store.set(None)

    @reactive.effect
    @reactive.event(input.csv_upload, ignore_init=True)
    def _handle_csv_upload() -> None:
        files = input.csv_upload()
        if not files:
            return
        eid = input.element()
        if not eid:
            bot_error_store.set(t("bot.no_element_selected"))
            return
        path = files[0]["datapath"]
        try:
            raw = pd.read_csv(path)
            year_col = _match_column(list(raw.columns), _YEAR_COL_CANDIDATES)
            value_col = _match_column(list(raw.columns), _VALUE_COL_CANDIDATES)
            if year_col is None or value_col is None:
                bot_error_store.set(t("bot.csv_error"))
                return
            df = pd.DataFrame({
                "Year": pd.to_numeric(raw[year_col], errors="coerce"),
                "Value": pd.to_numeric(raw[value_col], errors="coerce"),
            }).dropna().reset_index(drop=True)
            if df.empty:
                bot_error_store.set(t("bot.csv_no_rows"))
                return
            df["Year"] = df["Year"].astype(int)
            store = dict(bot_data_store.get())
            store[eid] = df  # replace, not append (spec §3)
            bot_data_store.set(store)
            bot_error_store.set(None)
        except Exception:
            bot_error_store.set(t("bot.csv_error"))

    @reactive.effect
    @reactive.event(input.element, input.data_source, input.year_range, ignore_init=True)
    def _handle_isa_synthetic() -> None:
        if (input.data_source() or "manual") != "isa":
            return
        eid = input.element()
        if not eid:
            return
        # Find the element to read its confidence.
        confidence = 3
        for el in project_data.get().isa_data.elements:
            if el.id == eid:
                confidence = el.confidence if el.confidence is not None else 3
                break
        # Map confidence (1-5) to noise scale: confidence 5 → 0.15, confidence 1 → 0.75.
        noise_scale = (6 - int(confidence)) * 0.15
        lo, hi = input.year_range() or (1950, 2030)
        years = np.arange(int(lo), int(hi) + 1)
        seed = hash(eid) & 0xFFFFFFFF
        rng = np.random.default_rng(seed=seed)
        # Smooth baseline + per-element noise.
        baseline = np.linspace(10.0, 20.0, len(years))
        noise = rng.normal(loc=0.0, scale=noise_scale * 5, size=len(years))
        values = baseline + noise
        df = pd.DataFrame({"Year": years, "Value": values})
        store = dict(bot_data_store.get())
        store[eid] = df
        bot_data_store.set(store)
        bot_error_store.set(None)

    @reactive.effect
    def _stale_warning() -> None:
        # Subscribe to ISA changes; isolate the store reads so this effect
        # does NOT re-fire on our own writes (manual add, csv upload, synthetic).
        event_bus.isa_change.get()
        with reactive.isolate():
            store = bot_data_store.get()
            if not store:
                return
            current_element_ids = {el.id for el in project_data.get().isa_data.elements}
            stale_keys = set(store.keys()) - current_element_ids
            if not stale_keys:
                return
            new_store = {k: v for k, v in store.items() if k in current_element_ids}
            bot_data_store.set(new_store)
            active = input.element()
            if active in stale_keys:
                ui.notification_show(
                    t("bot.stale_warning"),
                    duration=5,
                    type="warning",
                )

    @reactive.calc
    def _active_frame() -> pd.DataFrame | None:
        eid = input.element()
        if not eid:
            return None
        df = bot_data_store.get().get(eid)
        if df is None or df.empty:
            return None
        return df.sort_values("Year").reset_index(drop=True)

    @reactive.calc
    def _filtered_frame() -> pd.DataFrame | None:
        df = _active_frame()
        if df is None:
            return None
        lo, hi = input.year_range() or (1950, 2030)
        return df[(df["Year"] >= lo) & (df["Year"] <= hi)].reset_index(drop=True)

    @reactive.calc
    def _trend_coeffs() -> tuple[float, float] | None:
        if not input.show_trend():
            return None
        df = _filtered_frame()
        if df is None or df.empty:
            return None
        return _compute_trend(df["Year"].to_numpy(), df["Value"].to_numpy())

    @reactive.calc
    def _summary_stats() -> dict | None:
        df = _filtered_frame()
        if df is None or df.empty:
            return None
        values = df["Value"].to_numpy()
        coeffs = _compute_trend(df["Year"].to_numpy(), values)
        slope = coeffs[0] if coeffs is not None else float("nan")
        return {
            "mean": float(np.mean(values)),
            "sd": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "slope": slope,
        }

    @output
    @render.ui
    def input_panel():
        mode = input.data_source() or "manual"
        if mode == "manual":
            return ui.div(
                ui.input_numeric("year", t("bot.year"), value=2000, min=1900, max=2100, step=1),
                ui.input_numeric("value", t("bot.value"), value=0.0, step=0.1),
                ui.input_action_button(
                    "add_point", t("bot.add_point"),
                    class_="btn btn-primary btn-block",
                ),
            )
        if mode == "csv":
            return ui.div(
                ui.input_file("csv_upload", t("bot.upload_csv"), accept=[".csv"]),
                ui.tags.p(t("bot.upload_help"), class_="text-muted small"),
            )
        # mode == "isa"
        return ui.tags.p(t("bot.upload_help"), class_="text-muted small")

    @output
    @render.plot
    def bot_plot():
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 3.2))
        df = _filtered_frame()
        err = bot_error_store.get()
        if err:
            ax.text(0.5, 0.5, err, ha="center", va="center",
                    color="#a02020", transform=ax.transAxes, wrap=True)
            ax.axis("off")
            fig.tight_layout()
            return fig
        if df is None or df.empty:
            ax.text(0.5, 0.5, t("bot.no_data_yet"),
                    ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            fig.tight_layout()
            return fig
        is_synthetic = (input.data_source() or "manual") == "isa"
        legend_label = (
            f"{t('bot.synthetic_legend')} {t('bot.value')}"
            if is_synthetic else t("bot.value")
        )
        ax.plot(df["Year"], df["Value"], marker="o", color="#4a90b8",
                linewidth=2, markersize=5, label=legend_label)
        ax.set_xlabel(t("bot.year"))
        ax.set_ylabel(t("bot.value"))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        coeffs = _trend_coeffs()
        if coeffs is not None:
            slope, intercept = coeffs
            xs = df["Year"].to_numpy()
            ys = slope * xs + intercept
            ax.plot(xs, ys, color="#a02020", linestyle="--", linewidth=1.5,
                    label=t("bot.trend_label"))

        if input.show_moving_avg():
            window_raw = input.window_size()
            window = 3 if window_raw in (None, "") else int(window_raw)
            ma = _moving_average(df["Value"].to_numpy(), window)
            if ma is not None:
                ax.plot(df["Year"].to_numpy(), ma, color="#2d8b50", linewidth=1.8,
                        label=t("bot.moving_avg_label"))
        ax.legend(loc="best")
        if is_synthetic:
            fig.text(
                0.5, 0.5, t("bot.synthetic_warning"),
                alpha=0.18, ha="center", va="center",
                fontsize=44, color="#a02020", weight="bold",
                transform=fig.transFigure,
            )
        fig.tight_layout()
        return fig

    @output
    @render.ui
    def bot_summary():
        err = bot_error_store.get()
        if err:
            return ui.tags.div(err, class_="alert alert-danger")
        s = _summary_stats()
        if s is None:
            return ui.tags.p(t("bot.no_data_yet"), class_="text-muted")
        return ui.tags.dl(
            ui.tags.dt(t("bot.summary_mean")),
            ui.tags.dd(f"{s['mean']:.4f}"),
            ui.tags.dt(t("bot.summary_sd")),
            ui.tags.dd(f"{s['sd']:.4f}"),
            ui.tags.dt(t("bot.summary_min")),
            ui.tags.dd(f"{s['min']:.4f}"),
            ui.tags.dt(t("bot.summary_max")),
            ui.tags.dd(f"{s['max']:.4f}"),
            ui.tags.dt(t("bot.summary_slope")),
            ui.tags.dd(f"{s['slope']:.6f}"),
            class_="row",
        )

    @output
    @render.data_frame
    def bot_table():
        df = _filtered_frame()
        if df is None:
            return pd.DataFrame(columns=["Year", "Value"])
        return df

    @render.download_button(filename="bot_data.csv")
    def bot_download():
        df = _filtered_frame()
        if df is None:
            yield b"Year,Value\n"
            return
        buf = BytesIO()
        df.to_csv(buf, index=False)
        yield buf.getvalue()
