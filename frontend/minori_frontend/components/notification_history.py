"""Reminder attempt history and delivery mode inspector."""

from typing import Any

import streamlit as st
from minori_frontend.utils.dates import format_datetime_id


def render_reminder_details(notification: dict[str, Any], attempts: list[dict[str, Any]]) -> None:
    """Render notification status, lease metadata, and delivery attempt logs."""
    is_dry_run = notification.get("dry_run", True)
    mode_label = "Simulasi (Dry-Run)" if is_dry_run else "Pengiriman Nyata (Live)"

    st.markdown(
        f"""
        <div class="minori-card" style="margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: baseline;">
                <div>
                    <h3 style="margin: 0; color: #13263F; font-size: 1.125rem;">Pengingat #{notification.get("reference", "—")}</h3>
                    <div style="font-size: 12px; color: #64748B; margin-top: 2px;">
                        Template: <code>{notification.get("template_code", "—")}</code> • Saluran: <b>{notification.get("channel", "internal").upper()}</b>
                    </div>
                </div>
                <div style="text-align: right;">
                    <span style="background: {"#EDE9FE" if is_dry_run else "#DCFCE7"}; color: {"#6D28D9" if is_dry_run else "#15803D"}; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">
                        {mode_label}
                    </span>
                </div>
            </div>
            <div style="margin-top: 10px; font-size: 13px; color: #334155; line-height: 1.6;">
                <div>📅 <b>Jadwal Pengiriman:</b> {format_datetime_id(notification.get("scheduled_at"))}</div>
                <div>⏱️ <b>Tersedia di Antrean (Available At):</b> {format_datetime_id(notification.get("available_at"))}</div>
                <div>🔁 <b>Jumlah Percobaan (Attempt Count):</b> {notification.get("attempt_count", 0)} / {notification.get("max_attempts", 3)}</div>
                {f"<div>⚠️ <b>Kode Error Terakhir:</b> <code>{notification.get('last_error_code')}</code></div>" if notification.get("last_error_code") else ""}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**Riwayat Percobaan Pengiriman (Attempts)**")
    if not attempts:
        st.caption("Belum ada percobaan pengiriman tercatat.")
    else:
        for att in attempts:
            att_status = att.get("status", "processing")
            att_time = format_datetime_id(att.get("attempted_at"))
            fin_time = format_datetime_id(att.get("finished_at"))
            err = att.get("error_code")
            provider_ref = att.get("provider_reference")

            st.markdown(
                f"""
                <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px; margin-bottom: 6px;">
                    <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 600; color: #13263F;">
                        <span>Percobaan #{att.get("attempt_number", 1)}</span>
                        <span>{att_status.upper()}</span>
                    </div>
                    <div style="font-size: 12px; color: #64748B; margin-top: 4px;">
                        Waktu: {att_time} s/d {fin_time}
                        {f" • Error: <code>{err}</code>" if err else ""}
                        {f" • Provider Ref: <code>{provider_ref}</code>" if provider_ref else ""}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
