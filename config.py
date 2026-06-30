"""
config.py — Central configuration and CSS for Study Buddy AI
"""
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Page config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Study Buddy",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Environment variables ──────────────────────────────────────────────
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
TAVILY_API_KEY  = os.getenv("TAVILY_API_KEY", "")
MISTRAL_MODEL   = os.getenv("MISTRAL_MODEL", "mistral-medium-latest")

CHROMA_DB_PATH  = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "study_notes"
UPLOAD_DIR      = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_HISTORY_TURNS = 5
MAX_RETRIES       = 2
QUIZ_PASS_SCORE   = 0.6

# ── CSS injection ──────────────────────────────────────────────────────
def local_css():
    """
    Injects a Split-Theme CSS:
    - The Main Content reacts dynamically to Light/Dark mode.
    - The Sidebar is locked into a premium, distinct dark navy color.
    - ALL buttons aggressively overridden to Vibrant Azure (#2D68F2).
    """
    st.markdown(
        """
        <style>
        /* ===================================================================
           1. MAIN CONTENT (Reactive to Light/Dark Mode)
           =================================================================== */
        
        /* Base Canvas */
        .main, .stApp {
            background-color: var(--background-color) !important;
        }

        /* Main Content Widget Labels */
        .main div[data-testid="stWidgetLabel"] p,
        .main .stTextInput label p,
        .main .stNumberInput label p,
        .main .stSlider label p,
        .main .stSelectbox label p {
            color: var(--text-color) !important;
            font-weight: 600 !important;
        }

        /* ===================================================================
           2. SIDEBAR (Persistent Premium Dark Theme)
           =================================================================== */
        
        /* Sidebar Canvas */
        [data-testid="stSidebar"] {
            background-color: #0A0F1C !important; 
            border-right: 1px solid #1E293B !important;
        }

        /* Force all text in the sidebar to be light */
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] div[data-testid="stWidgetLabel"] p {
            color: #F8FAFC !important;
        }

        /* Sidebar Buttons */
        [data-testid="stSidebar"] .stButton > button {
            background-color: rgba(255, 255, 255, 0.05) !important;
            color: #F8FAFC !important;
            border: 1px solid transparent !important;
            text-align: left !important;
            padding: 0.6rem 1rem !important;
            font-weight: 500 !important;
            border-radius: 8px !important;
            transition: all 0.2s !important;
        }
        
        [data-testid="stSidebar"] .stButton > button:hover {
            background-color: #2D68F2 !important; /* Vibrant Azure Hover */
            border: 1px solid #1F51C8 !important;
            color: white !important;
        }

        [data-testid="stSidebar"] .stButton > button * {
            color: inherit !important;
        }

        /* ===================================================================
           3. BRANDING & CUSTOM COMPONENTS
           =================================================================== */

        /* Corporate logo rectangle with dynamic glow */
        .sb-logo-rect {
            padding: 1.5rem;
            width: 44px;
            height: 44px;
            border-radius: 8px;
            background: linear-gradient(135deg, #2D68F2, #497DF5);
            color: white !important;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.3rem;
            margin-right: 12px;
            flex-shrink: 0;
            box-shadow: 0 0 12px rgba(45, 104, 242, 0.5);
            animation: logoGlow 2.5s ease-in-out infinite alternate;
        }

        @keyframes logoGlow {
            0% { box-shadow: 0 0 12px rgba(45, 104, 242, 0.4); background: linear-gradient(135deg, #2D68F2, #497DF5); }
            50% { box-shadow: 0 0 22px rgba(45, 104, 242, 0.8); background: linear-gradient(135deg, #497DF5, #6792F7); }
            100% { box-shadow: 0 0 16px rgba(45, 104, 242, 0.6); background: linear-gradient(135deg, #1F51C8, #2D68F2); }
        }

        /* Sidebar branding row */
        .sidebar-branding { display: flex; align-items: center; margin-bottom: 1rem; }
        .sidebar-branding .branding-text { line-height: 1.2; }
        .sidebar-branding h2 { margin: 0; color: white !important; font-size: 1.3rem; }
        .sidebar-branding p { margin: 0; font-size: 0.8rem; color: #9CA3AF !important; }

        /* Trash can alignment */
        .chat-row-container { display: flex !important; align-items: center !important; justify-content: space-between !important; width: 100% !important; gap: 0.5rem; }
        .chat-row-container .chat-name-btn { flex: 1; min-width: 0; }
        .chat-row-container .chat-name-btn button { width: 100%; background: transparent !important; }
        .chat-row-container .delete-btn { flex-shrink: 0; display: flex; align-items: center; margin-left: auto; }
        .chat-row-container .delete-btn button {
            background: transparent !important;
            border: none !important;
            color: #EF4444 !important;
            font-size: 1.2rem;
            padding: 0.2rem 0.5rem;
            line-height: 1;
        }
        .chat-row-container .delete-btn button:hover {
            color: #DC2626 !important;
            background: rgba(239,68,68,0.1) !important;
            border-radius: 4px;
        }

        /* ===================================================================
           4. EYE-CATCHING GLOBAL BUTTONS (Nuclear Override for Main Area)
           =================================================================== */
        
        /* Ultra-specific targeting for all main area buttons */
        section.main .stButton button,
        section.main .stFormSubmitButton button,
        section.main .stDownloadButton button {
            background-color: #2D68F2 !important; 
            border-color: #2D68F2 !important;
            color: #FFFFFF !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            box-shadow: 0 2px 4px rgba(45, 104, 242, 0.15) !important;
            transition: all 0.3s ease-in-out !important;
        }

        /* Force inner text and icons to be white */
        section.main .stButton button *,
        section.main .stFormSubmitButton button *,
        section.main .stDownloadButton button * {
            color: #FFFFFF !important;
        }

        /* Interactive Hover State */
        section.main .stButton button:hover,
        section.main .stFormSubmitButton button:hover,
        section.main .stDownloadButton button:hover {
            background-color: #1F51C8 !important; 
            border-color: #1F51C8 !important;
            box-shadow: 0 4px 12px rgba(45, 104, 242, 0.4) !important; 
            transform: translateY(-1px) !important; 
        }

        /* ===================================================================
           5. DASHBOARD & UI ELEMENTS
           =================================================================== */

        /* Dashboard enclosure card */
        .dashboard-card-box {
            background: var(--secondary-background-color);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border: 1px solid var(--text-color);
            border-color: rgba(150, 150, 150, 0.2);
            margin-bottom: 1.5rem;
            margin-top: 1rem;
        }
        .dashboard-card-box > :first-child { margin-top: 0; }
        .dashboard-card-box h1, .dashboard-card-box h2, .dashboard-card-box h3 { font-weight: 700; color: var(--text-color) !important; margin: 0 0 0.2rem 0; }
        .dashboard-card-box p, .dashboard-card-box .stCaption { font-size: 0.9rem; color: var(--text-color) !important; opacity: 0.8; margin: 0 0 1rem 0; }

        /* Snapshot cards */
        .snapshot-card { text-align: center; }
        .snapshot-card .snapshot-number { font-size: 2rem; font-weight: 600; margin: 0; color: var(--text-color) !important; }
        .snapshot-card .snapshot-label { margin: 0; color: var(--text-color) !important; opacity: 0.8; font-size: 0.9rem; }

        /* Info callout */
        .info-callout {
            background-color: var(--secondary-background-color) !important;
            border-radius: 10px;
            padding: 1rem;
            border-left: 4px solid #2D68F2 !important; 
            color: var(--text-color) !important;
            margin: 1rem 0;
        }

        /* Banner card */
        .banner-card {
            background: var(--secondary-background-color);
            border-radius: 16px;
            padding: 1.8rem 2rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06);
            border: 1px solid rgba(150, 150, 150, 0.2);
            margin-bottom: 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .banner-text h2 { font-size: 1.8rem; font-weight: 700; color: var(--text-color) !important; margin: 0 0 0.25rem 0; }
        .banner-text p { font-size: 1rem; color: var(--text-color) !important; opacity: 0.8; margin: 0; }

        /* Robot avatar */
        .robot-avatar {
            display: flex; align-items: center; justify-content: center;
            width: 80px; height: 80px; border-radius: 50%;
            background: linear-gradient(135deg, #2D68F2, #497DF5);
            box-shadow: 0 0 30px rgba(45, 104, 242, 0.4);
            animation: robotPulse 3s ease-in-out infinite alternate; margin-left: auto;
        }
        .robot-avatar svg { width: 50px; height: 50px; fill: white; }
        
        /* User profile box (Sidebar) */
        .user-profile-box { background: #1E293B; border-radius: 12px; padding: 1rem; margin-top: 1rem; }
        .user-profile-box .user-name { margin: 0; font-weight: 600; color: white !important; }
        .user-profile-box .user-plan { margin: 0; font-size: 0.8rem; color: #9CA3AF !important; }

        /* Main Area Inputs & Placeholders */
        .main ::placeholder,
        .main .stTextInput input::placeholder,
        .main .stNumberInput input::placeholder,
        .main .stTextArea textarea::placeholder { color: var(--text-color) !important; opacity: 0.5 !important; }

        /* Main Area Slider */
        .main .stSlider .stSliderTrack { background-color: var(--secondary-background-color) !important; }
        .main .stSlider .stSliderThumb { background-color: #2D68F2 !important; border: 2px solid var(--background-color) !important; }
        .main .stSlider .stSliderValue { color: var(--text-color) !important; }

        </style>
        """,
        unsafe_allow_html=True,
    )