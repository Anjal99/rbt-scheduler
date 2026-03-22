"""
Shared CSS styles for the app.
"""

import streamlit as st

GLOBAL_CSS = """
<style>
/* ── Hide default Streamlit chrome ── */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header[data-testid="stHeader"] {visibility: hidden;}

/* ── Hide the auto-generated page navigation at top of sidebar ── */
[data-testid="stSidebarNav"],
nav[data-testid="stSidebarNav"],
div[data-testid="stSidebarNavItems"],
ul[data-testid="stSidebarNavItems"] {
    display: none !important;
}

/* ── Sidebar dark theme ── */
section[data-testid="stSidebar"] > div:first-child {
    background-color: #1E293B !important;
}
section[data-testid="stSidebar"] {
    background-color: #1E293B !important;
}

/* All sidebar text white */
section[data-testid="stSidebar"] * {
    color: #CBD5E1 !important;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4 {
    color: #F1F5F9 !important;
}

/* Sidebar metric labels */
section[data-testid="stSidebar"] [data-testid="stMetric"] {
    background: #334155 !important;
    border: 1px solid #475569 !important;
    border-radius: 8px !important;
    padding: 0.75rem !important;
}
section[data-testid="stSidebar"] [data-testid="stMetric"] label {
    color: #94A3B8 !important;
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
section[data-testid="stSidebar"] [data-testid="stMetricValue"] {
    color: #F8FAFC !important;
    font-size: 1.3rem !important;
    font-weight: 700 !important;
}

/* Sidebar dividers */
section[data-testid="stSidebar"] hr {
    border-color: #334155 !important;
    margin: 0.75rem 0 !important;
}

/* Sidebar page links */
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"],
section[data-testid="stSidebar"] .stPageLink a {
    color: #E2E8F0 !important;
    background: #334155 !important;
    border-radius: 8px !important;
    padding: 0.5rem 0.75rem !important;
    margin-bottom: 4px !important;
    border: none !important;
    text-decoration: none !important;
}
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover,
section[data-testid="stSidebar"] .stPageLink a:hover {
    background: #475569 !important;
}

/* ── Card style ── */
.card {
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: box-shadow 0.2s, transform 0.2s;
}
.card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    transform: translateY(-2px);
}
.card h3 {
    margin-top: 0;
    color: #1E293B;
    font-size: 1.05rem;
    font-weight: 600;
}
.card p {
    color: #64748B;
    font-size: 0.88rem;
    line-height: 1.5;
    margin-bottom: 0;
}
.card-icon {
    font-size: 1.75rem;
    margin-bottom: 0.5rem;
    display: block;
}

/* ── Page header ── */
.page-header {
    padding: 0.5rem 0 0.75rem 0;
    margin-bottom: 1.25rem;
    border-bottom: 2px solid #E2E8F0;
}
.page-header h1 {
    font-size: 1.6rem;
    font-weight: 700;
    color: #1E293B;
    margin: 0;
}
.page-header p {
    color: #64748B;
    font-size: 0.9rem;
    margin: 0.2rem 0 0 0;
}

/* ── Metric cards in main area ── */
[data-testid="stMetric"] {
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 0.85rem 1rem;
}
[data-testid="stMetric"] label {
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #64748B !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.4rem !important;
    font-weight: 700 !important;
    color: #1E293B !important;
}

/* ── Buttons ── */
.stButton > button[kind="primary"],
button[kind="primary"] {
    background-color: #2563EB !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover,
button[kind="primary"]:hover {
    background-color: #1D4ED8 !important;
}
.stButton > button {
    border-radius: 8px !important;
}

/* ── Data tables ── */
[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
}

/* ── Alerts ── */
.stAlert {
    border-radius: 8px !important;
}

/* ── Forms ── */
[data-testid="stForm"] {
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    padding: 1.25rem !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 6px 6px 0 0;
    padding: 8px 20px;
    font-weight: 500;
}

/* ── Download buttons ── */
.stDownloadButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
}

/* ══════════════════════════════════════════════════════════
   MOBILE RESPONSIVE
   ══════════════════════════════════════════════════════════ */

/* Mobile: stack columns, smaller text, tighter spacing */
@media (max-width: 768px) {
    /* Tighter main padding */
    .main .block-container {
        padding: 1rem 0.75rem !important;
        max-width: 100% !important;
    }

    /* Page header smaller */
    .page-header h1 {
        font-size: 1.25rem;
    }
    .page-header p {
        font-size: 0.8rem;
    }

    /* Cards: less padding on mobile */
    .card {
        padding: 1rem;
    }
    .card h3 {
        font-size: 0.95rem;
    }
    .card p {
        font-size: 0.82rem;
    }
    .card-icon {
        font-size: 1.4rem;
        margin-bottom: 0.3rem;
    }

    /* Metrics: smaller on mobile */
    [data-testid="stMetric"] {
        padding: 0.6rem 0.75rem;
    }
    [data-testid="stMetric"] label {
        font-size: 0.6rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.1rem !important;
    }

    /* Tables: horizontal scroll */
    [data-testid="stDataFrame"] {
        overflow-x: auto !important;
    }

    /* Plotly charts: allow horizontal scroll */
    .stPlotlyChart {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
    }

    /* Tabs: scrollable on mobile */
    .stTabs [data-baseweb="tab-list"] {
        overflow-x: auto;
        flex-wrap: nowrap;
        -webkit-overflow-scrolling: touch;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 6px 12px;
        font-size: 0.85rem;
        white-space: nowrap;
    }

    /* Sidebar: narrower on mobile */
    section[data-testid="stSidebar"] {
        width: 240px !important;
        min-width: 240px !important;
    }

    /* Buttons: full width on mobile */
    .stButton > button,
    .stDownloadButton > button {
        width: 100% !important;
    }

    /* Forms: tighter */
    [data-testid="stForm"] {
        padding: 0.75rem !important;
    }

    /* By-therapist/client detail lines */
    .main .stMarkdown p {
        font-size: 0.88rem;
    }
}

/* Small phones */
@media (max-width: 480px) {
    .main .block-container {
        padding: 0.5rem 0.5rem !important;
    }

    .page-header h1 {
        font-size: 1.1rem;
    }

    .card {
        padding: 0.75rem;
    }

    [data-testid="stMetricValue"] {
        font-size: 1rem !important;
    }

    /* Stack sidebar metrics */
    section[data-testid="stSidebar"] [data-testid="stMetric"] {
        padding: 0.5rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMetricValue"] {
        font-size: 1rem !important;
    }
}

/* Ensure Plotly charts have min height on mobile for readability */
@media (max-width: 768px) {
    .js-plotly-plot {
        min-height: 300px;
    }
}
</style>
"""


def apply_global_styles():
    """Call this at the top of every page."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def sidebar_nav():
    """Render the custom sidebar navigation."""
    with st.sidebar:
        st.markdown("### Therapy Scheduler Pro")
        st.markdown("---")
        st.page_link("app.py", label="Home", icon="🏠")
        st.page_link("pages/1_therapists.py", label="Therapists", icon="👥")
        st.page_link("pages/2_upload_clients.py", label="Upload Clients", icon="📄")
        st.page_link("pages/3_schedule.py", label="Schedule", icon="📅")
        st.page_link("pages/4_validation.py", label="Validation", icon="✅")
        st.markdown("---")

        from utils.database import therapist_count
        t_count = therapist_count()
        c_count = len(st.session_state.get('clients_df', []))

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Therapists", t_count)
        with col2:
            st.metric("Clients", c_count)

        if st.session_state.get('schedule_generated'):
            stats = st.session_state.get('schedule_stats', {})
            col3, col4 = st.columns(2)
            with col3:
                st.metric("Coverage", f"{stats.get('coverage_pct', 0):.0f}%")
            with col4:
                st.metric("Warnings", stats.get('warnings_count', 0))


def page_header(title: str, subtitle: str = ""):
    """Render a styled page header."""
    html = f'<div class="page-header"><h1>{title}</h1>'
    if subtitle:
        html += f'<p>{subtitle}</p>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def stat_card(value, label, color_class=""):
    """Render a styled stat card."""
    cls = f"stat-value {color_class}" if color_class else "stat-value"
    st.markdown(
        f'<div class="stat-card">'
        f'<div class="{cls}">{value}</div>'
        f'<div class="stat-label">{label}</div>'
        f'</div>',
        unsafe_allow_html=True
    )


def info_card(icon: str, title: str, description: str):
    """Render a styled info card."""
    st.markdown(
        f'<div class="card">'
        f'<span class="card-icon">{icon}</span>'
        f'<h3>{title}</h3>'
        f'<p>{description}</p>'
        f'</div>',
        unsafe_allow_html=True
    )
