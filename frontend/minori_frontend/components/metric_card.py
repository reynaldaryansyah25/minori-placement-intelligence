"""Quiet operational metrics, using backend values only."""

from minori_frontend.components.presentation import html, text


def metric_markup(label, value, subtext=None):
    return (
        f'<div class="minori-metric"><div class="minori-metric-label">{text(label)}</div>'
        f'<div class="minori-metric-value">{text(value)}</div>'
        f'<div class="minori-metric-subtext">{text(subtext or "")}</div></div>'
    )


def render_metric_card(label, value, subtext=None, badge=None, badge_type="neutral"):
    html(metric_markup(label, value, subtext))


def render_metrics(items):
    html('<div class="metric-grid">' + "".join(metric_markup(*item) for item in items) + "</div>")
