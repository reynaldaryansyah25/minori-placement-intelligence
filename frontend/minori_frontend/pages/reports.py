"""Backend-derived distributions and human-readable operational CSV exports."""

import csv
import io
from collections import Counter
from typing import Any

import streamlit as st
from minori_frontend.api_client import BackendClient, read_all
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.feedback import show_api_error
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.metric_card import render_metrics
from minori_frontend.components.page_header import render_page_header
from minori_frontend.components.presentation import distribution, section
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.dates import format_datetime_id
from minori_frontend.utils.formatting import format_status_label
from minori_frontend.utils.labels import (
    SECTOR_LABELS,
    TEMPLATE_LABELS,
    catalog_label,
    program_short,
)


def to_csv(data: list[dict[str, Any]]) -> str:
    if not data:
        return ""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(data[0]), quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for row in data:
        writer.writerow(
            {
                key: "'" + value
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@"))
                else value
                for key, value in row.items()
            }
        )
    return output.getvalue()


def render_reports_page():
    apply_theme()
    client = BackendClient(FrontendSettings())
    render_page_header(
        "Laporan & analitik",
        "Lihat distribusi operasional, kebutuhan verifikasi, dan unduh laporan untuk tim.",
    )
    try:
        summary = client.get_overview_summary()
        candidates = read_all(
            client.list_candidates,
        )
        vacancies = read_all(
            client.list_vacancies,
        )
        placements = read_all(
            client.list_placements,
        )
        reminders = read_all(
            client.list_reminders,
        )
        evaluations = read_all(
            client.list_matching_results,
        )
    except Exception as exc:
        show_api_error(exc)
        return
    cmap = {c["id"]: c.get("full_name") for c in candidates}
    vmap = {v["id"]: v.get("title") for v in vacancies}
    render_metrics(
        [
            (
                "Kandidat",
                summary.get("total_candidates", len(candidates)),
                "Terdaftar dalam layanan",
            ),
            ("Lowongan aktif", summary.get("active_vacancies", 0), "Menerima kandidat"),
            ("Penempatan aktif", summary.get("active_placements", 0), "Dalam proses"),
            ("Perlu verifikasi", summary.get("needs_review_matches", 0), "Berdasarkan evaluasi"),
        ]
    )
    charts, review, exports = st.tabs(["Distribusi", "Perlu verifikasi", "Unduh laporan"])
    with charts:
        left, right = st.columns(2, gap="large")
        with left:
            with st.container(border=True):
                section("Status kandidat")
                distribution(
                    [
                        (format_status_label(status), count)
                        for status, count in Counter(c.get("status") for c in candidates).items()
                    ]
                )
            with st.container(border=True):
                section("Kelayakan pencocokan")
                distribution(
                    [
                        ("Memenuhi persyaratan", summary.get("eligible_matches", 0)),
                        ("Perlu verifikasi", summary.get("needs_review_matches", 0)),
                        ("Belum memenuhi", summary.get("not_eligible_matches", 0)),
                    ]
                )
        with right:
            with st.container(border=True):
                section("Lowongan menurut sektor")
                distribution(
                    [
                        (catalog_label(sector, SECTOR_LABELS), count)
                        for sector, count in Counter(v.get("sector") for v in vacancies).items()
                    ],
                    color="navy",
                )
            with st.container(border=True):
                section("Status pengiriman")
                distribution(
                    [
                        (format_status_label(status), count)
                        for status, count in Counter(r.get("status") for r in reminders).items()
                    ],
                    color="amber",
                )
    with review:
        with st.container(border=True):
            section(
                "Kandidat yang memerlukan peninjauan", "Berdasarkan hasil evaluasi yang tersimpan"
            )
            latest = {}
            for evaluation in evaluations:
                latest.setdefault(
                    (evaluation.get("candidate_id"), evaluation.get("vacancy_id")), evaluation
                )
            rows = []
            for evaluation in latest.values():
                if evaluation.get("eligibility_status") not in {"NEEDS_REVIEW", "NOT_ELIGIBLE"}:
                    continue
                explanation = evaluation.get("explanation") or {}
                checks = explanation.get("checks", []) if isinstance(explanation, dict) else []
                messages = [
                    item.get("message", "")
                    for item in checks
                    if item.get("outcome") in {"FAIL", "REVIEW"}
                ]
                rows.append(
                    {
                        "Kandidat": cmap.get(
                            evaluation.get("candidate_id"), "Kandidat tidak tersedia"
                        ),
                        "Lowongan": vmap.get(
                            evaluation.get("vacancy_id"), "Lowongan tidak tersedia"
                        ),
                        "Hasil": format_status_label(evaluation.get("eligibility_status")),
                        "Perlu ditinjau": " ".join(messages) or "Tinjau kelengkapan persyaratan",
                    }
                )
            render_interactive_table(rows, key="report_review", height=360)
            if not rows:
                st.caption("Belum ada hasil evaluasi yang memerlukan peninjauan.")
    with exports:
        with st.container(border=True):
            section(
                "Unduh laporan operasional",
                "Data dari layanan penempatan dengan kolom yang mudah dibaca.",
            )
            datasets = [
                (
                    "Kandidat",
                    "candidates",
                    [
                        {
                            "Nama": c.get("full_name"),
                            "Program": program_short(c.get("preferred_program")),
                            "Domisili": c.get("domicile_city"),
                            "Status": format_status_label(c.get("status")),
                        }
                        for c in candidates
                    ],
                ),
                (
                    "Lowongan",
                    "vacancies",
                    [
                        {
                            "Posisi": v.get("title"),
                            "Perusahaan": v.get("employer_name"),
                            "Prefektur": v.get("prefecture"),
                            "Kuota": v.get("quota"),
                            "Status": format_status_label(v.get("status")),
                        }
                        for v in vacancies
                    ],
                ),
                (
                    "Penempatan",
                    "placements",
                    [
                        {
                            "Kandidat": cmap.get(p.get("candidate_id"), "Kandidat tidak tersedia"),
                            "Posisi": vmap.get(p.get("vacancy_id"), "Lowongan tidak tersedia"),
                            "Status": format_status_label(p.get("status")),
                            "Rencana keberangkatan": format_datetime_id(
                                p.get("planned_departure_at")
                            ),
                        }
                        for p in placements
                    ],
                ),
                (
                    "Pengingat",
                    "reminders",
                    [
                        {
                            "Kandidat": cmap.get(r.get("candidate_id"), "Kandidat tidak tersedia"),
                            "Kegiatan": TEMPLATE_LABELS.get(
                                r.get("template_code"), "Pengingat kegiatan"
                            ),
                            "Status": format_status_label(r.get("status")),
                            "Jadwal kirim": format_datetime_id(r.get("scheduled_at")),
                        }
                        for r in reminders
                    ],
                ),
            ]
            for title, filename, data in datasets:
                description, download = st.columns([3, 1], vertical_alignment="center")
                description.write(f"{title} · {len(data)} data")
                download.download_button(
                    "Unduh CSV",
                    data=to_csv(data).encode("utf-8-sig"),
                    file_name=f"minori_{filename}.csv",
                    mime="text/csv",
                    key="download_" + filename,
                    disabled=not data,
                    width="stretch",
                )


if __name__ == "__main__":
    render_reports_page()
