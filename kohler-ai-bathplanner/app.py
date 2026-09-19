import json
import os
import streamlit as st
import streamlit.components.v1 as components

from src import llm_service
from src.requirement_extractor import extract_requirements, validate_and_normalize
from src.recommendation_engine import build_design
from src.layout_generator import generate_layout_png
from src.layout_3d_generator import generate_3d_html

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "data", "kohler_products.json")

STYLE_OPTIONS = ["japanese_zen", "minimalist", "modern", "luxury", "classic"]
CATEGORY_OPTIONS = ["smart_toilet", "shower", "faucet", "vanity"]

@st.cache_data
def load_catalog():
    with open(CATALOG_PATH, "r") as f:
        data = json.load(f)
    return data["products"], data.get("_meta", {})

def init_session_state():
    defaults = {
        "requirements": None,
        "design_result": None,
        "history": [],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

def apply_custom_css():
    st.markdown("""
    <style>
    /* Dark Theme High-Contrast Metric Cards */
    div[data-testid="stMetric"] {
        background-color: #1a1c23 !important;
        border: 1px solid #2d3139 !important;
        padding: 16px 20px !important;
        border-radius: 8px !important;
        border-top: 3px solid #C5A059 !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4) !important;
    }
    
    /* Ensure metric label & value are bright and legible */
    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
        color: #A0A5B5 !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }

    /* Product Card Styling */
    div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"] {
        border-color: #2d3139 !important;
    }

    /* Primary Gold & Charcoal Button */
    .stButton > button[kind="primary"] {
        background-color: #C5A059 !important;
        color: #111111 !important;
        font-weight: 700 !important;
        letter-spacing: 1px !important;
        text-transform: uppercase !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.75rem 1rem !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #dfb96c !important;
        color: #000000 !important;
    }
    </style>
    """, unsafe_allow_html=True)

def render_header():
    st.set_page_config(page_title="KOHLER AI BathPlanner", page_icon="🛁", layout="wide")
    apply_custom_css()
    st.title("KOHLER AI BathPlanner")
    st.caption("Automated spatial design balancing aesthetic intent with deterministic budgetary constraints.")
    st.write("---")

def render_input_form():
    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        st.subheader("Describe your ideal bathroom")
        nl_text = st.text_area(
            "Natural-language requirements",
            placeholder="e.g. My bathroom is 8 x 6 feet. My budget is Rs 3 lakh. I want a minimalist Japanese Zen bathroom with a smart toilet, shower, faucet and vanity...",
            height=130,
            label_visibility="collapsed"
        )
    with col2:
        st.subheader("Or Set Variables Manually")
        with st.expander("Open Manual Constraints"):
            c1, c2, c3 = st.columns(3)
            with c1: length_ft = st.number_input("Length (ft)", min_value=0.0, step=0.5)
            with c2: width_ft = st.number_input("Width (ft)", min_value=0.0, step=0.5)
            with c3: budget = st.number_input("Budget (INR)", min_value=0.0, step=5000.0)
            c4, c5 = st.columns(2)
            with c4: style = st.selectbox("Style", ["(none)"] + STYLE_OPTIONS)
            with c5: categories = st.multiselect("Products", CATEGORY_OPTIONS)

    st.write("")
    generate = st.button("Generate My Bathroom", type="primary", use_container_width=True)

    overrides = {
        "length_ft": length_ft or None, "width_ft": width_ft or None,
        "budget": budget or None, "style": None if style == "(none)" else style,
        "categories": categories
    }
    return nl_text.strip(), overrides, generate

def render_results(design_result, requirements):
    if design_result["status"] == "infeasible":
        st.warning(design_result["message"])
        return

    st.success("Design successfully generated.")
    
    col_visual, col_data = st.columns([1.5, 1], gap="large")

    with col_visual:
        # Integrated Tabs for 2D Layout and the New 3D Engine
        tab_3d, tab_2d = st.tabs(["🧊 Interactive 3D Render", "🗺️ 2D Blueprint"])
        
        with tab_3d:
            st.info("Left-Click to Orbit | Right-Click to Pan | Scroll to Zoom")
            html_3d = generate_3d_html(requirements, design_result)
            components.html(html_3d, height=550)
            
        with tab_2d:
            bathroom = requirements.get("bathroom", {})
            L = bathroom.get("length_ft") or bathroom.get("length")
            W = bathroom.get("width_ft") or bathroom.get("width")
            png_bytes = generate_layout_png(design_result["selected_products"], L, W)
            if png_bytes:
                st.image(png_bytes, use_container_width=True)

    with col_data:
        st.subheader("🧾 Selected Fixtures")
        for p in design_result["selected_products"]:
            with st.container(border=True):
                st.markdown(f"**{p['category'].replace('_', ' ').title()}**")
                st.markdown(f"{p['name']} — **₹{p['price_inr']:,}**")

        st.metric("Estimated Total", f"₹{design_result['total_cost']:,.0f}")
        
        st.write("---")
        st.subheader("💡 Design Rationale")
        st.write(design_result["explanation"])

    st.write("---")
    st.subheader("📊 System Compatibility Metrics")
    scores = design_result["scores"]["components"]
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Space Fit", f"{scores['space_compatibility']:.0f}%")
    m2.metric("Style Match", f"{scores['style_match']:.0f}%")
    m3.metric("Budget Fit", f"{scores['budget_fit']:.0f}%")
    m4.metric("Features", f"{scores['feature_match']:.0f}%")
    m5.metric("Efficiency", f"{scores['sustainability_score']:.0f}%")

def render_redesign_box():
    st.write("---")
    st.subheader("🔄 Refine Your Design")
    col1, col2 = st.columns([4, 1])
    with col1:
        modification = st.text_input("Request an adjustment", placeholder='e.g. "Change the finish to matte black"', label_visibility="collapsed")
    with col2:
        btn = st.button("Apply Changes", use_container_width=True)
    return btn, modification

def main():
    render_header()
    catalog, catalog_meta = load_catalog()
    init_session_state()

    nl_text, overrides, generate_clicked = render_input_form()

    if generate_clicked:
        requirements = extract_requirements(nl_text) if nl_text else validate_and_normalize({})
        
        # Force the manual UI overrides to update the requirements dictionary
        if overrides["length_ft"]: requirements["bathroom"]["length_ft"] = overrides["length_ft"]
        if overrides["width_ft"]: requirements["bathroom"]["width_ft"] = overrides["width_ft"]
        if overrides["budget"]: requirements["budget"]["amount"] = overrides["budget"]
        if overrides["style"]: requirements["style"] = overrides["style"]
        if overrides["categories"]: requirements["required_categories"] = overrides["categories"]
        
        st.session_state.requirements = requirements
        st.session_state.design_result = build_design(catalog, requirements)
        st.session_state.history = [f"Initial request: {nl_text or '(manual)'}"]

    if st.session_state.requirements is not None:
        render_results(st.session_state.design_result, st.session_state.requirements)

        redesign_clicked, modification_text = render_redesign_box()
        if redesign_clicked and modification_text.strip():
            st.session_state.design_result = build_design(catalog, st.session_state.requirements)
            st.session_state.history.append(f"Redesign: {modification_text}")
            st.rerun()

if __name__ == "__main__":
    main()