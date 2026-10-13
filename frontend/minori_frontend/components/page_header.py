"""Consistent page hierarchy from the MINORI reference."""

from minori_frontend.components.presentation import html, text


def render_page_header(title, description, breadcrumb=None, backend_status=None, demo_mode=True):
    html(
        f'<div class="page-heading"><div class="eyebrow">Operasional penempatan</div>'
        f"<h1>{text(title)}</h1><p>{text(description)}</p></div>"
    )
