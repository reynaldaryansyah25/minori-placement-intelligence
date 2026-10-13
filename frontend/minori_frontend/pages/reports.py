"""Operational reports, distributions, and verified CSV exports."""

import io
from typing import Any

import streamlit as st
from minori_frontend.api_client import BackendClient
from minori_frontend.components.feedback import show_api_error
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.page_header import render_page_header
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.formatting import format_program, format_status_label


def to_csv(data: list[dict[str, Any]]) -> str:
    """Serialize list of dicts to RFC 4180 CSV string without extra libraries."""
    if not data:
        return ""
    keys = list(data[0].keys())
    output = io.StringIO()
    output.write(",".join(f'"{k}"' for k in keys) + "\n")
    for row in data:
        vals = [f'"{str(row.get(k, "")).replace('"', '""')}"' for k in keys]
        output.write(",".join(vals) + "\n")
    return output.getvalue()


def render_reports_page() -> None:
    apply_theme()
    settings = FrontendSettings()
    client = BackendClient(settings)

    render_page_header(
        title="Laporan & Analitik Operasional",
        description="Agregasi data real-time kualifikasi penempatan, pemenuhan kuota, status pengingat, dan ekspor dokumen CSV.",
        breadcrumb="MINORI Intelligence / Reports",
    )

    try:
        summary = client.get_overview_summary()
        candidates = client.list_candidates()
        vacancies = client.list_vacancies()
        placements = client.list_placements()
        reminders = client.list_reminders()
    except Exception as exc:
        show_api_error(exc)
        return

    tab_dist, tab_unmet, tab_export = st.tabs(
        ["Distribusi Operasional", "Verifikasi & Syarat Belum Terpenuhi", "Ekspor Dokumen CSV"]
    )

    with tab_dist:
        st.markdown("##### 1. Distribusi Status Kandidat & Penempatan")
        c1, c2 = st.columns(2)

        with c1:
            with st.container(border=True):
                st.markdown(
                    "<h4 style='margin:0 0 10px 0; font-size:14px; color:#13263F; font-weight:700;'>Status Kandidat Terdaftar</h4>",
                    unsafe_allow_html=True,
                )
                cand_status_counts: dict[str, int] = {}
                for cand in candidates:
                    st_code = cand.get("status", "registered")
                    cand_status_counts[st_code] = cand_status_counts.get(st_code, 0) + 1

                if cand_status_counts:
                    st.bar_chart(
                        data={
                            "Status": [format_status_label(k) for k in cand_status_counts.keys()],
                            "Jumlah": list(cand_status_counts.values()),
                        },
                        x="Jumlah",
                        y="Status",
                        horizontal=True,
                        color="#0F766E",
                        height=200,
                    )

        with c2:
            with st.container(border=True):
                st.markdown(
                    "<h4 style='margin:0 0 10px 0; font-size:14px; color:#13263F; font-weight:700;'>Distribusi Lowongan per Sektor Industri</h4>",
                    unsafe_allow_html=True,
                )
                sector_map = {
                    "agriculture": "Pertanian",
                    "food_service": "Pengolahan Makanan",
                    "caregiving": "Kaigo / Perawat",
                    "manufacturing": "Manufaktur / Pengelasan",
                    "engineering": "Teknik Mesin CAD",
                    "accommodation": "Perhotelan & Resor",
                }
                vac_sector_counts: dict[str, int] = {}
                for vac in vacancies:
                    sec = vac.get("sector", "General")
                    label = sector_map.get(sec, sec.replace("_", " ").title())
                    vac_sector_counts[label] = vac_sector_counts.get(label, 0) + 1

                if vac_sector_counts:
                    st.bar_chart(
                        data={
                            "Sektor": list(vac_sector_counts.keys()),
                            "Lowongan": list(vac_sector_counts.values()),
                        },
                        x="Lowongan",
                        y="Sektor",
                        horizontal=True,
                        color="#13263F",
                        height=200,
                    )

        st.markdown("##### 2. Distribusi Kelayakan Matching & Status Pengingat")
        c3, c4 = st.columns(2)

        with c3:
            with st.container(border=True):
                st.markdown(
                    "<h4 style='margin:0 0 10px 0; font-size:14px; color:#13263F; font-weight:700;'>Kelayakan Matching Pasangan</h4>",
                    unsafe_allow_html=True,
                )
                el_data = {
                    "Hasil Evaluasi": [
                        "Memenuhi Persyaratan",
                        "Perlu Verifikasi",
                        "Belum Memenuhi",
                    ],
                    "Jumlah": [
                        summary.get("eligible_matches", 0),
                        summary.get("needs_review_matches", 0),
                        summary.get("not_eligible_matches", 0),
                    ],
                }
                st.bar_chart(
                    data=el_data,
                    x="Jumlah",
                    y="Hasil Evaluasi",
                    horizontal=True,
                    color="#0F766E",
                    height=190,
                )

        with c4:
            with st.container(border=True):
                st.markdown(
                    "<h4 style='margin:0 0 10px 0; font-size:14px; color:#13263F; font-weight:700;'>Pengiriman Pengingat</h4>",
                    unsafe_allow_html=True,
                )
                rem_data = {
                    "Status": [
                        "Menunggu Pengiriman",
                        "Simulasi Berhasil",
                        "Terkirim",
                        "Gagal Kirim",
                        "Terlewat",
                    ],
                    "Jumlah": [
                        summary.get("pending_reminders", 0),
                        summary.get("simulated_reminders", 0),
                        summary.get("sent_reminders", 0),
                        summary.get("failed_reminders", 0),
                        summary.get("missed_reminders", 0),
                    ],
                }
                st.bar_chart(
                    data=rem_data,
                    x="Jumlah",
                    y="Status",
                    horizontal=True,
                    color="#B7791F",
                    height=190,
                )

    with tab_unmet:
        st.markdown("##### Kandidat Memerlukan Verifikasi Staf")
        review_candidates = [
            c for c in candidates if c.get("status") in ("registered", "preparing")
        ]
        if not review_candidates:
            st.caption("Semua kandidat telah memiliki status siap atau aktif.")
        else:
            for rc in review_candidates:
                st.markdown(
                    f"- **{rc.get('full_name')}** (`{rc.get('reference')}`) — Status: *{rc.get('status')}* • Program: *{format_program(rc.get('preferred_program'))}* • Domisili: *{rc.get('domicile_city')}*"
                )

        st.markdown(
            "<hr style='margin: 14px 0; border: none; border-top: 1px solid #E2E8F0;'>",
            unsafe_allow_html=True,
        )
        st.markdown("##### Ringkasan Syarat yang Kerap Belum Terpenuhi")
        st.markdown(
            """
            Berdasarkan evaluasi rule engine pada lowongan aktif:
            1. **Tingkat Bahasa Jepang (JLPT / JFT-Basic)**: Sebagian kandidat baru memiliki level N5 atau A1, sementara lowongan SSW umumnya mensyaratkan minimum JFT-Basic A2.2 atau JLPT N4.
            2. **Masa Berlaku Sertifikasi Keahlian**: Sertifikasi kompetensi OTIT/SSW memerlukan dokumen fisik yang aktif pada saat tanggal keberangkatan yang direncanakan.
            3. **Kesesuaian Pengalaman Kerja**: Minimal 6-12 bulan pada sektor yang relevan (pertanian, pengelasan, atau perawatan).
            """
        )

    with tab_export:
        st.markdown("##### Unduh Data Resmi (CSV Export)")
        st.caption("Ekspor data tabular operasional langsung dari database backend.")

        col_e1, col_e2, col_e3, col_e4 = st.columns(4)

        with col_e1:
            cand_rows = [
                {
                    "reference": c.get("reference"),
                    "full_name": c.get("full_name"),
                    "program": c.get("preferred_program"),
                    "domicile_city": c.get("domicile_city"),
                    "status": c.get("status"),
                }
                for c in candidates
            ]
            csv_cand = to_csv(cand_rows)
            st.download_button(
                "📥 Ekspor Kandidat (CSV)",
                data=csv_cand,
                file_name="minori_candidates.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with col_e2:
            vac_rows = [
                {
                    "reference": v.get("reference"),
                    "title": v.get("title"),
                    "employer_name": v.get("employer_name"),
                    "program": v.get("program"),
                    "prefecture": v.get("prefecture"),
                    "quota": v.get("quota"),
                    "status": v.get("status"),
                }
                for v in vacancies
            ]
            csv_vac = to_csv(vac_rows)
            st.download_button(
                "📥 Ekspor Lowongan (CSV)",
                data=csv_vac,
                file_name="minori_vacancies.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with col_e3:
            plc_rows = [
                {
                    "reference": p.get("reference"),
                    "candidate_id": p.get("candidate_id"),
                    "vacancy_id": p.get("vacancy_id"),
                    "status": p.get("status"),
                    "planned_departure_at": p.get("planned_departure_at"),
                }
                for p in placements
            ]
            csv_plc = to_csv(plc_rows)
            st.download_button(
                "📥 Ekspor Penempatan (CSV)",
                data=csv_plc,
                file_name="minori_placements.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with col_e4:
            rem_rows = [
                {
                    "reference": r.get("reference"),
                    "candidate_id": r.get("candidate_id"),
                    "template_code": r.get("template_code"),
                    "status": r.get("status"),
                    "scheduled_at": r.get("scheduled_at"),
                }
                for r in reminders
            ]
            csv_rem = to_csv(rem_rows)
            st.download_button(
                "📥 Ekspor Pengingat (CSV)",
                data=csv_rem,
                file_name="minori_reminders.csv",
                mime="text/csv",
                use_container_width=True,
            )


if __name__ == "__main__":
    render_reports_page()
