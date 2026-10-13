"""Reminder operations monitor and notification simulation center."""

from typing import Any

import streamlit as st
from minori_frontend.api_client import BackendClient
from minori_frontend.auth import is_admin
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.empty_state import render_empty_state
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.metric_card import render_metric_card
from minori_frontend.components.notification_history import render_reminder_details
from minori_frontend.components.page_header import render_page_header
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.dates import format_datetime_id
from minori_frontend.utils.formatting import format_status_label


def render_reminder_page() -> None:
    apply_theme()
    settings = FrontendSettings()
    client = BackendClient(settings)
    can_mutate = is_admin()

    render_page_header(
        title="Pusat Pengingat & Notifikasi (Reminder Center)",
        description="Monitoring antrean notifikasi terkelola, sinkronisasi jadwal, dan eksekusi uji coba (Dry-Run Simulation).",
        breadcrumb="MINORI Operations / Reminder Center",
    )

    # Fetch reminders list
    try:
        reminders = client.list_reminders()
        candidates_map = {c["id"]: c for c in client.list_candidates()}
    except Exception as exc:
        show_api_error(exc)
        return

    # Count by status
    counts: dict[str, int] = {}
    for r in reminders:
        st_val = r.get("status", "pending")
        counts[st_val] = counts.get(st_val, 0) + 1

    # Status Summary Row
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        render_metric_card(
            "Menunggu Kirim",
            counts.get("pending", 0),
            subtext="Siap dikirim",
            badge="Antrean",
            badge_type="info",
        )
    with m2:
        render_metric_card(
            "Simulasi Sukses",
            counts.get("simulated", 0),
            subtext="Uji coba selesai",
            badge="Simulasi",
            badge_type="neutral",
        )
    with m3:
        render_metric_card(
            "Terkirim",
            counts.get("sent", 0),
            subtext="Terkirim sukses",
            badge="Terkirim",
            badge_type="success",
        )
    with m4:
        render_metric_card(
            "Sedang Diproses",
            counts.get("processing", 0),
            subtext="Dalam pengiriman",
            badge="Proses",
            badge_type="warning",
        )
    with m5:
        render_metric_card(
            "Gagal Kirim",
            counts.get("failed", 0),
            subtext="Perlu pemeriksaan",
            badge="Gagal",
            badge_type="danger",
        )
    with m6:
        render_metric_card(
            "Terlewat",
            counts.get("missed", 0),
            subtext="Jadwal terlewati",
            badge="Kedaluwarsa",
            badge_type="warning",
        )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Operational Controls
    if can_mutate:
        st.markdown("##### Tindakan Sinkronisasi Antrean")
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            if st.button(
                "🔄 Sinkronisasi Aktivitas",
                use_container_width=True,
                help="Menghasilkan pengingat otomatis untuk jadwal penempatan yang aktif",
            ):
                try:
                    generated = client.generate_reminders()
                    show_success(f"{len(generated)} jadwal pengingat berhasil disinkronkan!")
                    st.rerun()
                except Exception as exc:
                    show_api_error(exc)
        with col_c2:
            if st.button(
                "🛡️ Rapikan Antrean Tertunda",
                use_container_width=True,
                help="Memulihkan jadwal antrean yang terhenti",
            ):
                try:
                    res = client.recover_reminders()
                    show_success(
                        f"Pemeriksaan antrean selesai: {res.get('recovered_count', 0)} item dirapikan."
                    )
                    st.rerun()
                except Exception as exc:
                    show_api_error(exc)
        with col_c3:
            if st.button(
                "🧪 Uji Simulasi Pengiriman",
                type="primary",
                use_container_width=True,
                help="Menguji pengiriman notifikasi terdekat secara aman",
            ):
                try:
                    sim = client.simulate_reminder()
                    if sim:
                        show_success(
                            f"Simulasi pengiriman berhasil untuk notifikasi #{sim.get('reference')}!"
                        )
                    else:
                        st.info("Tidak ada pengingat yang perlu disimulasikan saat ini.")
                    st.rerun()
                except Exception as exc:
                    show_api_error(exc)
    else:
        st.info(
            "Mode Reviewer: Operasi sinkronisasi dan simulasi antrean memerlukan hak akses staf admin."
        )

    # Table of Reminders
    if not reminders:
        render_empty_state(
            title="Tidak ada data pengingat",
            description="Antrean notifikasi pengingat saat ini kosong. Jadwalkan aktivitas di Placement Pipeline dan klik Sinkronisasi.",
        )
        return

    table_data = []
    for r in reminders:
        cid = r.get("candidate_id")
        cname = candidates_map.get(cid, {}).get("full_name", str(cid)[:8])
        is_sim = r.get("dry_run", True)
        table_data.append(
            {
                "id": r.get("id"),
                "Referensi": r.get("reference"),
                "Kandidat": cname,
                "Template": r.get("template_code"),
                "Jadwal Kirim": format_datetime_id(r.get("scheduled_at")),
                "Tersedia": format_datetime_id(r.get("available_at")),
                "Status": format_status_label(r.get("status")),
                "Mode": "Simulasi" if is_sim else "Live",
                "Percobaan": f"{r.get('attempt_count', 0)}/{r.get('max_attempts', 3)}",
                "Error": r.get("last_error_code") or "—",
            }
        )

    st.markdown("##### Tabel Monitoring Antrean Pengingat")
    selected_indices = render_interactive_table(table_data, key="reminders_table", height=280)

    selected_rem: dict[str, Any] | None = None
    if selected_indices:
        selected_id = table_data[selected_indices[0]]["id"]
        selected_rem = next((r for r in reminders if r["id"] == selected_id), None)
    else:
        selected_rem = reminders[0]

    if selected_rem:
        st.markdown(
            "<hr style='margin: 14px 0; border: none; border-top: 1px solid #E2E8F0;'>",
            unsafe_allow_html=True,
        )
        # Fetch attempt history and routing
        try:
            attempts = client.get_reminder_attempts(selected_rem["id"])
        except Exception:
            attempts = []
        try:
            routing = client.get_recipient_routing(selected_rem["id"])
        except Exception:
            routing = None
        render_reminder_details(selected_rem, attempts, routing=routing)


if __name__ == "__main__":
    render_reminder_page()
