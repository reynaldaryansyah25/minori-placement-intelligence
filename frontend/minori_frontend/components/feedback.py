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
        413: "Ukuran unggahan sandbox maksimal 2 MB.",
        429: "Batas penggunaan demo tercapai. Tunggu sesi atau kuota layanan tersedia kembali; reset data tidak menghapus batas pemakaian.",
        503: "Layanan sedang tidak tersedia. Silakan coba beberapa saat lagi.",
        504: "Layanan memerlukan waktu lebih lama. Silakan coba lagi.",
    }
    message = messages.get(exc.status_code) if isinstance(exc, ApiClientError) else None
    safe_ai_messages = {
        "Dokumen tidak memuat teks. PDF scan memerlukan OCR terlebih dahulu.",
        "Ukuran dokumen harus antara 1 byte dan 5 MB.",
        "Arsip dokumen melebihi batas aman.",
        "Dokumen dengan makro atau objek tertanam tidak didukung.",
        "Dokumen dengan referensi eksternal tidak didukung.",
        "Maksimal 100 baris lowongan per dokumen.",
        "Dokumen rusak atau formatnya tidak sesuai. Ekspor ulang dokumen.",
        "Struktur hasil AI tidak valid. Analisis ulang atau tinjau secara manual.",
        "Bukti AI tidak ditemukan dalam sumber. Tinjau dokumen atau analisis ulang.",
        "AI belum diaktifkan. Gunakan peninjauan manual.",
        "AI sementara tidak tersedia. Coba kembali atau gunakan peninjauan manual.",
        "Data kandidat, jadwal, atau penerima berubah. Susun ulang email.",
        "Pengingat sudah disetujui atau pernah diproses. Pengiriman ganda diblokir.",
        "Bahasa draf AI memuat informasi yang perlu dikonfirmasi. Gunakan template aman.",
    }
    if (
        isinstance(exc, ApiClientError)
        and isinstance(exc.detail, str)
        and exc.detail in safe_ai_messages
    ):
        message = exc.detail
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
