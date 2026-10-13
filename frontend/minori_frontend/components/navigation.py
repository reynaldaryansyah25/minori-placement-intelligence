"""Navigation page definitions using Streamlit multipage navigation API."""

import streamlit as st
from minori_frontend.pages.ai_vacancy_intelligence import render_ai_vacancy_page
from minori_frontend.pages.candidate_matching import render_matching_page
from minori_frontend.pages.candidates import render_candidates_page
from minori_frontend.pages.overview import render_overview_page
from minori_frontend.pages.placement_pipeline import render_pipeline_page
from minori_frontend.pages.reminder_center import render_reminder_page
from minori_frontend.pages.reports import render_reports_page
from minori_frontend.pages.vacancies import render_vacancies_page


def get_navigation_pages() -> list[st.Page]:
    """Define modern multipage routing with clean URL paths and material icons."""
    return [
        st.Page(
            render_overview_page,
            title="Overview",
            url_path="overview",
            icon=":material/dashboard:",
            default=True,
        ),
        st.Page(
            render_candidates_page,
            title="Candidates",
            url_path="candidates",
            icon=":material/person_search:",
        ),
        st.Page(
            render_vacancies_page,
            title="Vacancies",
            url_path="vacancies",
            icon=":material/work:",
        ),
        st.Page(
            render_matching_page,
            title="Candidate Matching",
            url_path="candidate-matching",
            icon=":material/fact_check:",
        ),
        st.Page(
            render_pipeline_page,
            title="Placement Pipeline",
            url_path="placement-pipeline",
            icon=":material/flight_takeoff:",
        ),
        st.Page(
            render_reminder_page,
            title="Reminder Center",
            url_path="reminder-center",
            icon=":material/notifications:",
        ),
        st.Page(
            render_ai_vacancy_page,
            title="AI Vacancy Intelligence",
            url_path="ai-vacancy-intelligence",
            icon=":material/auto_awesome:",
        ),
        st.Page(
            render_reports_page,
            title="Reports & Analytics",
            url_path="reports",
            icon=":material/analytics:",
        ),
    ]
