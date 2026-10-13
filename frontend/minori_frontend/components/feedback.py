"""Actionable staff feedback without transport details or exception payloads."""

import streamlit as st
from minori_frontend.api_client import ApiClientError


def show_api_error(exc: Exception) -> None:
    messages = {
        401: "Sesi Anda belum dapat diverifikasi. Hubungi pengelola untuk memulihkan akses.",
        403: "Akun Anda tidak memiliki akses untuk tindakan ini.",
        404: "Data tidak lagi tersedia. Muat ulang halaman untuk melihat data terbaru.",
        409: "Tindakan belum dapat diproses. Periksa status kandidat, persetujuan, kuota, dan jadwal kegiatan.",
        422: "Periksa kembali kolom wajib dan format data sebelum menyimpan.",
        503: "Layanan sedang tidak tersedia. Silakan coba beberapa saat lagi.",
        504: "Layanan memerlukan waktu lebih lama. Silakan coba lagi.",
    }
    message = messages.get(exc.status_code) if isinstance(exc, ApiClientError) else None
    if (
        isinstance(exc, ApiClientError)
        and exc.status_code == 409
        and "inactive candidate" in str(exc.detail)
    ):
        message = (
            "Kandidat nonaktif tidak dapat dijadwalkan. Pilih penempatan dengan kandidat aktif."
        )
    st.error(message or "Tindakan belum berhasil. Silakan muat ulang atau hubungi pengelola.")


def show_success(message):
    st.session_state["minori_feedback"] = message
    st.success(message)


def show_warning(message):
    st.warning(message)


def show_info(message):
    st.info(message)
