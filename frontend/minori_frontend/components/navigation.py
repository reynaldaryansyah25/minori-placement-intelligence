"""Eight native Streamlit pages and functional cross-page navigation."""

import streamlit as st
from minori_frontend.pages.ai_vacancy_intelligence import render_ai_vacancy_page
from minori_frontend.pages.candidate_matching import render_matching_page
from minori_frontend.pages.candidates import render_candidates_page
from minori_frontend.pages.overview import render_overview_page
from minori_frontend.pages.placement_pipeline import render_pipeline_page
from minori_frontend.pages.reminder_center import render_reminder_page
from minori_frontend.pages.reports import render_reports_page
from minori_frontend.pages.vacancies import render_vacancies_page

PAGE_DEFINITIONS = [
    (render_overview_page, "Ringkasan", "overview", "dashboard"),
    (render_candidates_page, "Kandidat", "candidates", "group"),
    (render_vacancies_page, "Lowongan", "vacancies", "work"),
    (render_matching_page, "Pencocokan Kandidat", "candidate-matching", "target"),
    (render_pipeline_page, "Alur Penempatan", "placement-pipeline", "layers"),
    (render_reminder_page, "Pusat Pengingat", "reminder-center", "notifications"),
    (render_ai_vacancy_page, "Analisis Lowongan", "ai-vacancy-intelligence", "description"),
    (render_reports_page, "Laporan & Analitik", "reports", "bar_chart"),
]


def get_navigation_pages():
    return [
        st.Page(render, title=title, url_path=path, icon=f":material/{icon}:", default=index == 0)
        for index, (render, title, path, icon) in enumerate(PAGE_DEFINITIONS)
    ]


def navigate_to(path):
    for definition, page in zip(PAGE_DEFINITIONS, get_navigation_pages(), strict=True):
        if definition[2] == path:
            st.switch_page(page)
            return
    raise ValueError("Page is not registered")
