"""Notification delivery details without queue identifiers or raw errors."""

import streamlit as st
from minori_frontend.components.data_table import render_interactive_table
from minori_frontend.components.presentation import detail_grid, section
from minori_frontend.components.status_badge import render_status_badge
from minori_frontend.config import FrontendSettings
from minori_frontend.utils.dates import format_datetime_id
from minori_frontend.utils.labels import TEMPLATE_LABELS

ERROR_DESCRIPTIONS = {
    "PROVIDER_UNAVAILABLE": "Layanan pengiriman belum tersedia",
    "PROVIDER_TIMEOUT": "Layanan pengiriman melewati batas waktu tunggu",
    "PROVIDER_REJECTED": "Pesan belum diterima oleh layanan pengiriman",
    "LEASE_EXPIRED": "Pemrosesan terhenti dan dijadwalkan kembali",
    "SCHEDULE_CHANGED": "Jadwal kegiatan diperbarui",
    "ACTIVITY_CANCELLED": "Kegiatan dibatalkan",
    "EVENT_PASSED": "Waktu kegiatan telah berlalu",
    "RECIPIENT_INACTIVE": "Kandidat tidak aktif",
    "SIMULATED_UNAVAILABLE": "Simulasi kegagalan koneksi",
}


def render_reminder_details(notification, attempts, routing=None):
    section(
        TEMPLATE_LABELS.get(notification.get("template_code"), "Pengingat kegiatan"),
        "Rincian pengiriman",
    )
    render_status_badge(notification.get("status"))
    detail_grid(
        [
            ("Mode", "Simulasi" if notification.get("dry_run", True) else "Pengiriman"),
            ("Jadwal kirim", format_datetime_id(notification.get("scheduled_at"))),
            (
                "Percobaan",
                f"{notification.get('attempt_count', 0)} dari {notification.get('max_attempts', 3)}",
            ),
            ("Tersedia kembali", format_datetime_id(notification.get("available_at"))),
        ]
    )
    if notification.get("last_error_code"):
        st.warning(
            ERROR_DESCRIPTIONS.get(
                notification["last_error_code"], "Pengiriman memerlukan pemeriksaan."
            )
        )
    with st.expander("Tujuan pengiriman", expanded=True):
        if FrontendSettings().public_reviewer_mode and not FrontendSettings().interactive_demo_mode:
            st.caption("Tujuan dan isi email hanya tersedia bagi staf.")
        elif routing is None:
            st.caption("Informasi tujuan pengiriman belum tersedia.")
        elif not routing.get("delivery_allowed"):
            st.info("Mode simulasi: tidak ada email yang dikirim.")
        else:
            mode = routing.get("routing_mode")
            st.caption(
                "Inbox pengujian lokal"
                if mode == "mailpit"
                else "Penerima pengujian yang dikonfigurasi"
            )
            st.text(routing.get("effective_recipient") or "Tujuan belum dikonfigurasi")
    section("Riwayat pengiriman")
    if not attempts:
        st.caption("Belum ada percobaan pengiriman yang tercatat.")
    else:
        labels = {
            "succeeded": "Terkirim ke server email",
            "simulated": "Simulasi selesai",
            "failed": "Gagal",
            "abandoned": "Dijadwalkan ulang",
            "processing": "Diproses",
        }
        render_interactive_table(
            [
                {
                    "Percobaan": item.get("attempt_number"),
                    "Hasil": labels.get(item.get("status"), "Belum tersedia"),
                    "Waktu": format_datetime_id(item.get("attempted_at")),
                    "Catatan": ERROR_DESCRIPTIONS.get(item.get("error_code"), "—"),
                }
                for item in attempts
            ],
            key="attempts_" + notification["id"],
            height=260,
            page_size=5,
        )
