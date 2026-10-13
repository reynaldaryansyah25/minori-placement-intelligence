"""Reminder attempt history and delivery mode inspector."""

from typing import Any

import streamlit as st
from minori_frontend.utils.dates import format_datetime_id

ERROR_DESCRIPTIONS = {
    "PROVIDER_UNAVAILABLE": "Penyedia email pengujian sedang sibuk atau tidak merespons",
    "PROVIDER_TIMEOUT": "Batas waktu tunggu koneksi habis",
    "PROVIDER_REJECTED": "Format pesan tidak diterima oleh penyedia",
    "LEASE_EXPIRED": "Waktu pemrosesan melebihi batas dan telah dirapikan",
    "SCHEDULE_CHANGED": "Jadwal kegiatan diperbarui sehingga pengingat disesuaikan",
    "ACTIVITY_CANCELLED": "Kegiatan dibatalkan oleh staf",
    "EVENT_PASSED": "Waktu kegiatan telah terlewati",
    "RECIPIENT_INACTIVE": "Status peserta tidak aktif",
    "SIMULATED_UNAVAILABLE": "Simulasi uji coba kegagalan jaringan untuk validasi ketahanan sistem",
}


def render_reminder_details(
    notification: dict[str, Any],
    attempts: list[dict[str, Any]],
    routing: dict[str, Any] | None = None,
) -> None:
    """Render notification status, demo recipient routing, and delivery attempt logs."""
    is_dry_run = notification.get("dry_run", True)
    mode_label = "Simulasi Aman (Dry-Run)" if is_dry_run else "Pengiriman Nyata"

    template_code = notification.get("template_code", "—")
    template_name = (
        "Pemberitahuan Wawancara (H-3)"
        if "interview" in str(template_code)
        else (
            "Pemberitahuan Pemeriksaan Medis (H-1)"
            if "medical" in str(template_code)
            else str(template_code)
        )
    )

    err_code = notification.get("last_error_code")
    err_desc = ERROR_DESCRIPTIONS.get(err_code, err_code) if err_code else None

    st.markdown(
        f"""
        <div class="minori-card" style="margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: baseline;">
                <div>
                    <h3 style="margin: 0; color: #13263F; font-size: 1.125rem;">Pengingat #{notification.get("reference", "—")}</h3>
                    <div style="font-size: 13px; color: #64748B; margin-top: 3px;">
                        Jenis: <b>{template_name}</b> &nbsp;|&nbsp; Saluran: <b>{str(notification.get("channel", "internal")).title()}</b>
                    </div>
                </div>
                <div style="text-align: right;">
                    <span style="background: {"#EDE9FE" if is_dry_run else "#DCFCE7"}; color: {"#6D28D9" if is_dry_run else "#15803D"}; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 600;">
                        {mode_label}
                    </span>
                </div>
            </div>
            <div style="margin-top: 12px; font-size: 13px; color: #334155; line-height: 1.7;">
                <div>📅 <b>Jadwal Pengiriman:</b> {format_datetime_id(notification.get("scheduled_at"))}</div>
                <div>⏱️ <b>Waktu Tersedia di Antrean:</b> {format_datetime_id(notification.get("available_at"))}</div>
                <div>🔁 <b>Percobaan Pengiriman:</b> {notification.get("attempt_count", 0)} dari batas maksimal {notification.get("max_attempts", 3)} kali</div>
                {f"<div style='margin-top: 4px; color: #B91C1C;'>⚠️ <b>Catatan Kegagalan:</b> {err_desc}</div>" if err_desc else ""}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Demo Recipient Routing Card
    with st.container(border=True):
        st.markdown(
            "<h4 style='margin:0 0 8px 0; font-size:13px; color:#13263F; font-weight:700;'>🛡️ Pengalihan Pengiriman Demo (Demo Recipient Routing)</h4>",
            unsafe_allow_html=True,
        )
        intended = (routing or {}).get(
            "intended_recipient"
        ) or f"kandidat-{str(notification.get('candidate_id', 'demo'))[:8]}@demo.minori.internal"
        effective = (routing or {}).get("effective_recipient") or "Mailpit (Inbox Lokal Terisolasi)"
        mode = (routing or {}).get("routing_mode") or ("dry_run" if is_dry_run else "mailpit")

        st.markdown(
            f"""
            <div style="font-size: 12px; color: #475569; line-height: 1.6;">
                <div>• <b>Alamat Penerima Fiktif:</b> <code style="color:#0F766E;">{intended}</code></div>
                <div>• <b>Tujuan Pengiriman Uji:</b> <b>{effective}</b> (Mode: {mode})</div>
                <div style="margin-top: 4px; color: #15803D; font-weight: 500;">
                    ✓ Terlindungi: Email fiktif tidak pernah dikirim ke internet untuk menjaga kerahasiaan dan kepatuhan data.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.markdown("**Riwayat Percobaan Pengiriman**")
    if not attempts:
        st.caption("Belum ada percobaan pengiriman yang dicatat.")
    else:
        for att in attempts:
            att_status = str(att.get("status", "processing")).lower()
            status_indo = (
                "Berhasil (Terkirim)"
                if att_status == "succeeded"
                else (
                    "Simulasi Berhasil"
                    if att_status == "simulated"
                    else ("Gagal Kirim" if att_status == "failed" else "Sedang Diproses")
                )
            )
            att_time = format_datetime_id(att.get("attempted_at"))
            fin_time = format_datetime_id(att.get("finished_at"))
            raw_err = att.get("error_code")
            err_text = ERROR_DESCRIPTIONS.get(raw_err, raw_err) if raw_err else None

            st.markdown(
                f"""
                <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px 12px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 600; color: #13263F;">
                        <span>Percobaan #{att.get("attempt_number", 1)}</span>
                        <span style="color: {"#15803D" if "berhasil" in status_indo.lower() else "#B91C1C"};">{status_indo}</span>
                    </div>
                    <div style="font-size: 12px; color: #64748B; margin-top: 4px;">
                        Waktu: {att_time} s/d {fin_time}
                        {f"<div style='color: #B91C1C; margin-top: 3px;'>Catatan: {err_text}</div>" if err_text else ""}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
