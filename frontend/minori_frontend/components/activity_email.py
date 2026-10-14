"""Select a participant's persisted schedule before preparing a staff-approved email."""

import streamlit as st
from minori_frontend.api_client import read_all
from minori_frontend.auth import is_admin
from minori_frontend.components.feedback import show_api_error, show_success
from minori_frontend.components.presentation import section
from minori_frontend.utils.dates import format_datetime_id, now_wib, parse_to_wib
from minori_frontend.utils.labels import STEP_LABELS


def render_activity_email_picker(client, candidates):
    with st.container(border=True):
        section(
            "Siapkan email kegiatan",
            "Pilih kandidat dan jadwal resmi, lalu tinjau pesan sebelum menyetujui pengiriman.",
        )
        try:
            placements = [
                p
                for p in read_all(client.list_placements)
                if p["status"] in {"preparing", "in_progress"}
                and candidates.get(p["candidate_id"], {}).get("status") != "inactive"
            ]
            options = {
                p["candidate_id"]: candidates.get(p["candidate_id"], {}).get(
                    "full_name", "Kandidat"
                )
                for p in placements
            }
            if not options:
                st.caption(
                    "Belum ada peserta dengan penempatan aktif. Proses persetujuan dan penempatan terlebih dahulu."
                )
                return
            handoff = st.session_state.pop("reminder_candidate_handoff", None)
            if handoff in options:
                st.session_state["email_activity_candidate"] = handoff
            if st.session_state.get("email_activity_candidate") not in options:
                st.session_state["email_activity_candidate"] = next(iter(options))
            candidate_id = st.selectbox(
                "Kandidat penerima pengingat",
                list(options),
                format_func=options.get,
                key="email_activity_candidate",
            )
            participant_placements = [p for p in placements if p["candidate_id"] == candidate_id]
            placement = participant_placements[0]
            if len(participant_placements) > 1:
                selected = st.selectbox(
                    "Penempatan peserta",
                    list(range(len(participant_placements))),
                    format_func=lambda i: "Penempatan " + str(i + 1),
                )
                placement = participant_placements[selected]
            activities = [
                a
                for a in client.list_activities(placement["id"])
                if a["status"] in {"scheduled", "in_progress"}
                and parse_to_wib(a.get("scheduled_at"))
                and parse_to_wib(a["scheduled_at"]) > now_wib()
            ]
            if activities:
                activity_options = {
                    a["id"]: STEP_LABELS.get(a["step_type"], "Kegiatan")
                    + " · "
                    + format_datetime_id(a["scheduled_at"])
                    + " · "
                    + (a.get("location") or "Lokasi perlu dikonfirmasi")
                    for a in activities
                }
                activity_id = st.selectbox(
                    "Jadwal yang dikirim melalui email",
                    list(activity_options),
                    format_func=activity_options.get,
                )
                if st.button(
                    "Siapkan email untuk jadwal ini",
                    type="primary",
                    disabled=not is_admin(),
                    width="stretch",
                ):
                    reminder = client.prepare_activity_email(placement["id"], activity_id)
                    st.session_state["prepared_reminder_id"] = reminder["id"]
                    show_success(
                        "Jadwal dipilih. Susun email dengan AI atau gunakan template, lalu edit dan konfirmasikan di bawah."
                    )
                    st.rerun()
            else:
                st.caption(
                    "Belum ada kegiatan mendatang. Jadwalkan wawancara, kesehatan, dokumen, orientasi, atau keberangkatan terlebih dahulu."
                )
            if st.button("Kelola jadwal peserta", width="stretch"):
                st.session_state["placement_handoff_id"] = placement["id"]
                from minori_frontend.components.navigation import navigate_to

                navigate_to("placement-pipeline")
        except Exception as exc:
            show_api_error(exc)
