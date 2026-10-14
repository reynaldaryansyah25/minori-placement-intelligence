"""Existing reminder synchronization, simulation, and delivery monitoring."""

import streamlit as st
from minori_frontend.api_client import BackendClient, read_all
from minori_frontend.auth import is_admin
from minori_frontend.components.activity_email import render_activity_email_picker
from minori_frontend.components.ai_email import render_email_actions
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.empty_state import render_empty_state
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.layout import apply_theme
from minori_frontend.components.metric_card import render_metrics
from minori_frontend.components.notification_history import render_reminder_details
from minori_frontend.components.page_header import render_page_header
from minori_frontend.components.presentation import section
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.dates import format_datetime_id
from minori_frontend.utils.formatting import format_status_label
from minori_frontend.utils.labels import TEMPLATE_LABELS


def render_reminder_page():
    apply_theme()
    client = BackendClient(FrontendSettings())
    render_page_header(
        "Pusat pengingat", "Pantau pengingat kegiatan, tujuan pengiriman, dan riwayat percobaan."
    )
    try:
        reminders = read_all(
            client.list_reminders,
        )
        candidates = {
            c["id"]: c
            for c in read_all(
                client.list_candidates,
            )
        }
    except Exception as exc:
        show_api_error(exc)
        return
    render_activity_email_picker(client, candidates)
    prepared = st.session_state.pop("prepared_reminder_id", None)
    if prepared:
        st.session_state["reminder_detail_id"] = prepared
        st.session_state["reminder_status_filter"] = None
        st.session_state["reminder_search"] = ""
    counts = {}
    for item in reminders:
        counts[item.get("status")] = counts.get(item.get("status"), 0) + 1
    render_metrics(
        [
            ("Menunggu", counts.get("pending", 0), "Menunggu jadwal pengiriman"),
            (
                "Terkirim ke server email",
                counts.get("sent", 0),
                "SMTP berhasil; penerimaan kandidat belum dipastikan",
            ),
            ("Simulasi selesai", counts.get("simulated", 0), "Tanpa pengiriman email"),
            (
                "Perlu diperiksa",
                counts.get("failed", 0) + counts.get("missed", 0),
                "Gagal atau jadwal terlewat",
            ),
        ]
    )
    controls = st.columns(3)
    if controls[0].button("Sinkronkan jadwal", disabled=not is_admin(), width="stretch"):
        try:
            result = client.generate_reminders()
            show_success(f"{len(result)} pengingat telah disinkronkan dengan jadwal kegiatan.")
            st.rerun()
        except Exception as exc:
            show_api_error(exc)
    if controls[1].button("Pulihkan antrean", disabled=not is_admin(), width="stretch"):
        try:
            result = client.recover_reminders()
            show_success(f"{result.get('recovered_count', 0)} pengingat selesai diperiksa.")
            st.rerun()
        except Exception as exc:
            show_api_error(exc)
    if controls[2].button("Uji simulasi", type="primary", disabled=not is_admin(), width="stretch"):
        try:
            result = client.simulate_reminder()
            if result:
                show_success("Simulasi pengiriman pengingat selesai.")
                st.rerun()
            else:
                st.info("Belum ada pengingat simulasi yang jatuh tempo.")
        except Exception as exc:
            show_api_error(exc)
    statuses = [None, "pending", "processing", "sent", "simulated", "failed", "missed", "cancelled"]
    query_col, status_col = st.columns([3, 1])
    with query_col:
        query = st.text_input(
            "Pencarian pengingat",
            placeholder="Cari nama kandidat…",
            label_visibility="collapsed",
            key="reminder_search",
        )
    with status_col:
        status = st.selectbox(
            "Status pengingat",
            statuses,
            format_func=lambda value: (
                "Semua status" if value is None else format_status_label(value)
            ),
            label_visibility="collapsed",
            key="reminder_status_filter",
        )
    records = [
        r
        for r in reminders
        if (not status or r.get("status") == status)
        and (
            not query
            or query.lower()
            in candidates.get(r.get("candidate_id"), {}).get("full_name", "").lower()
        )
    ]
    if not records:
        render_empty_state(
            "Pengingat tidak ditemukan",
            "Ubah filter atau jadwalkan aktivitas melalui Alur Penempatan.",
        )
        return
    listing, details = st.columns([1.4, 1], gap="large")
    with listing:
        with st.container(border=True):
            section("Daftar pengingat", "Pilih pengingat untuk melihat hasil pengiriman.")
            selected = render_interactive_table(
                [
                    {
                        "id": row["id"],
                        "Kandidat": candidates.get(row.get("candidate_id"), {}).get(
                            "full_name", "Kandidat tidak tersedia"
                        ),
                        "Kegiatan": TEMPLATE_LABELS.get(
                            row.get("template_code"), "Pengingat kegiatan"
                        ),
                        "Jadwal kirim": format_datetime_id(row.get("scheduled_at")),
                        "Status": format_status_label(row.get("status")),
                        "Mode": "Simulasi" if row.get("dry_run", True) else "Pengiriman",
                    }
                    for row in records
                ],
                key="reminders_table",
                height=380,
                default_first=False,
            )
        if selected:
            signature = records[selected[0]]["id"]
            if signature != st.session_state.get("reminder_table_selection"):
                st.session_state["reminder_detail_id"] = signature
                st.session_state["reminder_table_selection"] = signature
        options = {
            r["id"]: candidates.get(r["candidate_id"], {}).get("full_name", "Kandidat")
            + " · "
            + TEMPLATE_LABELS.get(r["template_code"], "Pengingat")
            + " · "
            + format_datetime_id(r.get("event_at"))
            for r in records
        }
        if st.session_state.get("reminder_detail_id") not in options:
            st.session_state["reminder_detail_id"] = records[0]["id"]
        identifier = st.selectbox(
            "Pengingat yang ditinjau",
            list(options),
            format_func=options.get,
            key="reminder_detail_id",
        )
        reminder = next(r for r in records if r["id"] == identifier)
    with details:
        with st.container(border=True):
            try:
                attempts = client.get_reminder_attempts(reminder["id"])
                routing = client.get_recipient_routing(reminder["id"])
            except Exception as exc:
                show_api_error(exc)
                return
            render_reminder_details(reminder, attempts, routing)
            render_email_actions(client, reminder, routing)


if __name__ == "__main__":
    render_reminder_page()
