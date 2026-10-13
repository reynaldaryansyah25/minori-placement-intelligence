"""Reference design tokens adapted to native Streamlit widgets and responsive layout."""

import streamlit as st

ENTERPRISE_CSS = """
<style>
:root {
 --navy:#17283f; --teal:#0f766e; --teal-dark:#0a625b; --bg:#f6f8fb;
 --ink:#1c2a3d; --muted:#617087; --border:#e3e9f0; --amber:#a56815;
 --red:#aa3b44; --paper:#fff; --radius:12px;
}
html,body,[data-testid="stAppViewContainer"],.stApp {
 background:var(--bg);color:var(--ink);
 font-family:Inter,"Segoe UI",-apple-system,BlinkMacSystemFont,Arial,sans-serif;
 -webkit-font-smoothing:antialiased;
}
[data-testid="stMainBlockContainer"] {max-width:1540px;padding:22px 38px 64px;}
[data-testid="stVerticalBlock"] {gap:16px;}
[data-testid="stHeader"] {background:transparent;height:36px;pointer-events:none;}
[data-testid="stHeader"] button {pointer-events:auto;}
[data-testid="stToolbar"],#MainMenu,footer,[data-testid="stDecoration"] {display:none;}
[data-testid="stSidebar"] {background:#fff;border-right:1px solid var(--border);width:252px!important;min-width:252px!important;max-width:252px!important;}
[data-testid="stSidebarHeader"] {height:12px!important;min-height:12px!important;}
[data-testid="stSidebarCollapseButton"] {position:absolute;right:4px;top:4px;}
[data-testid="stSidebarContent"] {padding:0!important;}
[data-testid="stSidebarUserContent"] {padding:4px 12px!important;}
.st-key-mobile_nav {display:none;}
.st-key-action_center [data-testid="stVerticalBlock"] {gap:8px;}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:6px;}
[data-testid="stSidebar"] [data-testid="stPageLink"] a {padding:10px 12px;border-radius:8px;color:#596a7f;}
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {background:#f3f6fa;}
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] {
 background:#ebf4f2;color:var(--teal-dark);font-weight:750;box-shadow:inset 3px 0 var(--teal);
}
[data-testid="stSidebar"] [data-testid="stPageLink"] p {font-size:13px;font-weight:550;}
[data-testid="stSidebar"] [data-testid="stPageLink"] a * {color:inherit!important;}
.st-key-nav_active [data-testid="stPageLink"] a {background:#ebf4f2;color:var(--teal-dark)!important;box-shadow:inset 3px 0 var(--teal);}
div[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .section-head),
div[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .profile-head) {
 background:white;border-radius:12px;border-color:var(--border);padding:20px;
}
.brand {display:flex;gap:12px;align-items:center;padding:4px 6px 23px;border-bottom:1px solid var(--border);margin-bottom:22px;}
.brand-mark {width:40px;height:40px;border-radius:10px;background:var(--navy);color:#fff;display:grid;place-items:center;font-size:22px;font-weight:760;}
.brand-title {font-size:14px;font-weight:750;color:var(--navy);}
.brand-sub {font-size:11px;color:var(--muted);margin-top:2px;}
.nav-label,.eyebrow {font-size:10px;letter-spacing:.115em;text-transform:uppercase;font-weight:750;}
.nav-label {color:#8894a6;margin:18px 12px 10px;}
.sidebar-status {margin-top:26px;border:1px solid #dde9e7;background:#f6fbfa;border-radius:9px;padding:13px;font-size:11px;color:var(--muted);}
.sidebar-status strong {display:block;font-size:12px;color:var(--navy);margin-bottom:5px;}
.status-dot {display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--teal);margin-right:7px;}
.status-dot.offline {background:var(--amber);}
.topbar {display:flex;justify-content:space-between;align-items:center;gap:16px;border-bottom:1px solid var(--border);padding:0 0 18px;margin-bottom:12px;font-size:12px;color:var(--muted);}
.topbar b {color:var(--navy);font-weight:700;}
.topbar-right {display:flex;align-items:center;gap:18px;font-size:11px;}
.demo-pill {background:#fff6e6;border:1px solid #f6e3bb;color:#976318;border-radius:20px;padding:5px 11px;font-weight:680;}
.eyebrow {color:var(--teal);margin-bottom:8px;}
.page-heading {margin:4px 0 8px;}
.page-heading h1 {font-size:26px;font-weight:750;letter-spacing:-.04em;line-height:1.2;color:var(--navy);margin:0;}
.page-heading p {color:var(--muted);font-size:13px;line-height:1.6;margin:10px 0 8px;max-width:800px;}
h1,h2,h3,h4,h5 {color:var(--navy);letter-spacing:-.02em;}
[data-testid="stMarkdownContainer"] h3 {font-size:16px;}
[data-testid="stMarkdownContainer"] h4,[data-testid="stMarkdownContainer"] h5 {font-size:14px;}
[data-testid="stMarkdownContainer"] p {font-size:13px;line-height:1.6;}
.section-head h3 {font-size:14px;font-weight:750;color:var(--navy);margin:0;}
.section-head p {font-size:11.5px;color:var(--muted);margin:5px 0 0;}
.minori-card {background:white;border:1px solid var(--border);border-radius:12px;padding:20px 22px;box-shadow:0 2px 8px rgba(24,42,68,.025);}
[data-testid="stVerticalBlockBorderWrapper"] {border-color:var(--border)!important;border-radius:12px!important;background:#fff;}
.metric-grid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;}
.minori-metric {background:#fff;border:1px solid var(--border);border-radius:12px;padding:19px 20px;min-height:119px;}
.minori-metric-label {font-size:10px;text-transform:uppercase;letter-spacing:.075em;font-weight:750;color:var(--muted);}
.minori-metric-value {font-size:31px;font-weight:790;letter-spacing:-.06em;line-height:1.15;color:var(--navy);margin:14px 0 7px;}
.minori-metric-subtext {font-size:11px;color:#6c7d91;}
.status-pill {display:inline-flex;border-radius:5px;padding:4px 8px;font-size:10.5px;font-weight:720;line-height:1.4;white-space:nowrap;border:0;}
.detail-grid {display:grid;grid-template-columns:1fr 1fr;gap:17px 20px;}
.detail-label {font-size:11px;color:#7e8a9b;margin-bottom:4px;font-weight:650;}
.detail-value {font-size:12px;color:var(--navy);font-weight:650;overflow-wrap:anywhere;}
.profile-head {display:flex;gap:12px;align-items:center;margin-bottom:18px;}
.avatar {height:40px;width:40px;border-radius:10px;background:#eaf1f7;color:#3f6284;font-size:13px;font-weight:780;display:grid;place-items:center;flex:none;}
.profile-head h3 {margin:0;font-size:16px;color:var(--navy);}
.profile-head p {font-size:11px;color:var(--muted);margin:3px 0 0;}
.chips {display:flex;flex-wrap:wrap;gap:7px;}
.chip {font-size:10.5px;border:1px solid #e0e7ee;background:#f7f9fb;color:#59697e;padding:5px 8px;border-radius:5px;}
.bars {display:flex;flex-direction:column;gap:17px;padding:6px 0;}
.bar-head {display:flex;justify-content:space-between;font-size:12px;color:#45536a;margin-bottom:7px;gap:12px;}
.bar-head strong {color:var(--navy);}
.bar-track {height:9px;background:#eff2f6;border-radius:99px;overflow:hidden;}
.bar-fill {height:100%;border-radius:99px;background:var(--teal);}
.bar-fill.navy {background:var(--navy);}.bar-fill.amber {background:#d79b42;}
.event-row {display:flex;justify-content:space-between;gap:15px;align-items:flex-start;padding:13px 0;border-bottom:1px solid #eef1f5;}
.event-row:last-child {border-bottom:0;}
.event-row strong {color:var(--navy);font-size:12px;}
.event-row p,.event-row small {font-size:11px;color:var(--muted);margin:4px 0 0;}
.event-row .event-date {font-size:11px;color:var(--muted);white-space:nowrap;}
.score-value {font-size:33px;font-weight:820;letter-spacing:-.05em;color:var(--navy);}
.score-value small {font-size:13px;color:#8492a3;font-weight:500;}
.timeline {display:flex;gap:0;position:relative;margin:12px 0 20px;overflow-x:auto;}
.timeline:before {content:"";height:2px;background:#e4ebf0;position:absolute;left:10%;right:10%;top:18px;}
.timeline-step {flex:1;min-width:90px;text-align:center;position:relative;z-index:1;}
.step-circle {width:38px;height:38px;border:2px solid #e0e7ee;border-radius:50%;background:#fff;color:#8190a2;margin:0 auto 9px;display:grid;place-items:center;font-size:12px;font-weight:800;}
.timeline-step.done .step-circle {background:var(--teal);border-color:var(--teal);color:white;}
.timeline-step.current .step-circle {border-color:var(--teal);color:var(--teal);background:#eef8f5;}
.step-title {font-size:11.5px;font-weight:740;color:var(--navy);}.step-sub {font-size:10px;color:#8593a2;margin-top:3px;}
button[kind="primary"],button[data-testid="stBaseButton-primaryFormSubmit"] {background:var(--teal)!important;border-color:var(--teal)!important;color:#fff!important;}
button[kind="primary"]:hover {background:var(--teal-dark)!important;}
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button,[data-testid="stFormSubmitButton"] button {border-radius:8px;font-weight:650;min-height:36px;}
[data-testid="stButton"] p,[data-testid="stDownloadButton"] p,[data-testid="stFormSubmitButton"] p {font-size:12px;}
[data-testid="stWidgetLabel"] p {font-size:11.5px;font-weight:650;color:#495b70;}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"] {background:#fff;border-radius:8px;border-color:var(--border);}
[data-baseweb="input"] input,[data-baseweb="select"],[data-baseweb="textarea"] textarea {font-size:12px;color:var(--navy);}
[data-testid="stForm"] {background:white;border-color:var(--border);border-radius:12px;}
[data-testid="stDataFrame"] {border:1px solid var(--border);border-radius:10px;overflow:hidden;}
[data-testid="stExpander"] {background:white;border-color:var(--border);border-radius:10px;}
[data-baseweb="tab-list"] {gap:24px;overflow-x:auto;}
[data-baseweb="tab"] {font-size:12px;white-space:nowrap;}
[data-baseweb="tab-highlight"] {background:var(--teal);}
[data-testid="stAlert"] {border-radius:9px;font-size:12px;}
[data-testid="stCaptionContainer"] p {font-size:11px;color:var(--muted);}
:focus-visible {outline:3px solid rgba(15,118,110,.3);outline-offset:2px;}
@media (max-width:1180px) {
 [data-testid="stMainBlockContainer"] {padding:24px 26px 55px;}
 .metric-grid {grid-template-columns:repeat(2,minmax(0,1fr));}
 [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
 [data-testid="stColumn"] {min-width:min(310px,100%)!important;}
}
@media (max-width:760px) {
 .st-key-mobile_nav {display:block;position:fixed;top:5px;left:12px;width:108px;z-index:1000;}
 [data-testid="stMainBlockContainer"] {padding:40px 16px 48px;}
 [data-testid="stHorizontalBlock"] {flex-direction:column;gap:16px;}
 [data-testid="stColumn"] {width:100%!important;flex:1 1 100%!important;min-width:0!important;}
 .topbar {padding-bottom:14px;font-size:11px;}.top-date {display:none;}
 .topbar-right {gap:6px;}.demo-pill {font-size:10px;padding:4px 8px;}
 .page-heading h1 {font-size:23px;}.page-heading p {font-size:12px;}
 .metric-grid {gap:10px;}.minori-metric {padding:16px;min-height:104px;}
 .minori-metric-value {font-size:27px;margin:12px 0 6px;}
 .minori-card {padding:17px;}.event-row {flex-wrap:wrap;gap:6px;}
 .detail-grid {gap:15px 12px;}
}
</style>
"""


def apply_theme() -> None:
    st.html(ENTERPRISE_CSS)
