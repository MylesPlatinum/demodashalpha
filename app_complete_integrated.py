import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib import colors as pdf_colors
from io import BytesIO
import numpy as np
from datetime import datetime
import yaml

# Import robust parser module
from robust_excel_parser import load_excel_data

# === LOAD CLIENT CONFIGURATION ===
@st.cache_resource
def load_config():
    """Load client configuration from config.yaml"""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        st.error("⚠️ Configuration file not found! Please ensure config.yaml exists.")
        st.stop()
    except yaml.YAMLError as e:
        st.error(f"⚠️ Error reading configuration: {e}")
        st.stop()

config = load_config()

# === PAGE CONFIG ===
st.set_page_config(
    page_title=config['dashboard']['title'], 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# === PASSWORD PROTECTION ===
PASSWORD = config['dashboard']['password']

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Try to load logo - centered
        logo_loaded = False
        try:
            from PIL import Image
            logo_path = config['branding']['logo_file']
            if Path(logo_path).exists():
                logo = Image.open(logo_path)
                col_a, col_b, col_c = st.columns([1, 2, 1])
                with col_b:
                    st.image(logo, width=150)
                logo_loaded = True
        except:
            pass
        
        if not logo_loaded:
            st.markdown(
                f"<div style='text-align: center; font-size: 60px; margin: 20px; color: {config['branding']['primary_color']};'>🏢</div>", 
                unsafe_allow_html=True
            )
        
        st.markdown(f"<h1 style='text-align: center;'>{config['client']['name']}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: #888;'>{config['dashboard']['subtitle']}</p>", unsafe_allow_html=True)
        
        pwd = st.text_input("Enter Password", type="password")
        if pwd == PASSWORD:
            st.session_state.auth = True
            st.rerun()
        elif pwd:
            st.error("Wrong password")
        
        # Values and Mission Statement
        if config.get('company_values', {}).get('show_on_login', False):
            st.divider()
            
            with st.expander("📖 Our Values & Mission", expanded=False):
                st.markdown("### Our Values")
                
                values = config.get('company_values', {}).get('values', [])
                if isinstance(values, list):
                    for value in values:
                        if isinstance(value, dict):
                            st.markdown(f"**{value.get('title', '')}** - *{value.get('tagline', '')}*")
                            st.markdown(value.get('description', ''))
                        else:
                            st.markdown(f"**{value}**")
                        st.markdown("")
                
                mission = config.get('company_values', {}).get('mission', {})
                if mission:
                    st.markdown("---")
                    st.markdown("### Mission Statement")
                    st.markdown(f"#### *\"{mission.get('title', '')}\"*")
                    st.markdown(mission.get('description', ''))
                    
                    for point in mission.get('points', []):
                        st.markdown(f"**{point.get('title', '')}** - {point.get('text', '')}")
    
    st.stop()

# === DEBUG MODE ===
debug_mode = st.sidebar.checkbox("Debug Mode", value=config['features']['debug_mode'], help="Show detailed data loading info")

# === AUTO-DETECT LATEST FILES ===
@st.cache_data(ttl=60)
def get_latest_files():
    data_dir = Path("data")
    
    if not data_dir.exists():
        st.error("'data' folder not found! Please create it and add your Excel files.")
        st.stop()
    
    # Use patterns from config
    revenue_pattern = config['data']['revenue_file_pattern']
    costs_pattern = config['data']['costs_file_pattern']
    
    revenue_files = list(data_dir.glob(revenue_pattern))
    costs_files = list(data_dir.glob(costs_pattern))
    
    if not revenue_files:
        st.error(f"No revenue files found matching pattern: {revenue_pattern}")
        st.stop()
    if not costs_files:
        st.error(f"No costs files found matching pattern: {costs_pattern}")
        st.stop()
    
    latest_revenue = max(revenue_files, key=lambda f: f.stat().st_mtime)
    latest_costs = max(costs_files, key=lambda f: f.stat().st_mtime)
    
    return latest_revenue, latest_costs

# === LOAD DATA WITH ROBUST PARSER ===
@st.cache_data(ttl=60)
def load_data():
    revenue_path, costs_path = get_latest_files()
    
    if debug_mode:
        st.sidebar.info(f"Loading:\n- {revenue_path.name}\n- {costs_path.name}")
    
    try:
        # Get branches from config
        branches = config['data']['branches']
        
        # Use robust parser to load revenue data
        revenue_data = load_excel_data(str(revenue_path), config, debug=debug_mode)
        revenue_df = revenue_data['revenue']
        hours_df = revenue_data.get('hours')
        
        if debug_mode:
            st.write("### Debug: Parsed Revenue Data")
            st.dataframe(revenue_df)
            if hours_df is not None:
                st.write("### Debug: Parsed Hours Data")
                st.dataframe(hours_df)
            st.code(revenue_data['validation_report'])
        
        # Show warnings if any
        if revenue_data['warnings']:
            with st.expander("⚠️ Data Quality Warnings", expanded=False):
                for warning in revenue_data['warnings']:
                    st.warning(warning)
        
        # Use robust parser to load costs data
        costs_data = load_excel_data(str(costs_path), config, debug=debug_mode)
        costs_df = costs_data['costs']
        
        if debug_mode:
            st.write("### Debug: Parsed Costs Data")
            st.dataframe(costs_df)
            st.code(costs_data['validation_report'])
        
        # Transform to the format expected by downstream code
        data_list = []
        
        for idx, row in revenue_df.iterrows():
            period = row.get('Period', idx + 1)
            
            for branch in branches:
                if branch in revenue_df.columns:
                    rev_val = row[branch]
                    hrs_val = hours_df.iloc[idx][branch] if hours_df is not None and branch in hours_df.columns else 0
                    cost_val = costs_df.iloc[idx][branch] if idx < len(costs_df) and branch in costs_df.columns else 0
                    
                    # Skip if no revenue
                    if pd.notna(rev_val) and rev_val > 0:
                        data_list.append({
                            'Period': str(int(period)) if pd.notna(period) else str(idx + 1),
                            'Date Range': '',  # Not available in parsed data
                            'Branch': branch,
                            'Revenue': float(rev_val),
                            'Hours': float(hrs_val) if pd.notna(hrs_val) else 0,
                            'Cost': float(cost_val) if pd.notna(cost_val) else 0
                        })
        
        df = pd.DataFrame(data_list)
        
        # Calculate derived metrics
        df['Gross Profit'] = df['Revenue'] - df['Cost']
        df['Margin %'] = df.apply(lambda r: round(r['Gross Profit'] / r['Revenue'] * 100, 1) if r['Revenue'] > 0 else 0, axis=1)
        df['Rev per Hour'] = df.apply(lambda r: round(r['Revenue'] / r['Hours'], 2) if r['Hours'] > 0 else 0, axis=1)
        df['Period_Int'] = df['Period'].astype(int)
        df = df.sort_values(['Period_Int', 'Branch'])
        
        # Care type breakdown (if enabled)
        care_f = pd.DataFrame()
        care_hours = pd.DataFrame()
        
        if config.get('care_types', {}).get('enabled', False):
            try:
                # Placeholder for care type data - customize per client
                care_categories = [cat['name'] if isinstance(cat, dict) else cat for cat in config['care_types']['categories']]
                care_f = pd.DataFrame({
                    'Branch': branches,
                    care_categories[0]: [35267.04, 10357.48, 7207.35, 30076.49, 58688.48][:len(branches)],
                    care_categories[1]: [38815.12, 452.80, 11231.75, 80001.18, 38110.58][:len(branches)],
                    care_categories[2]: [2475.00, 0.00, 3847.00, 4500.00, 6300.00][:len(branches)]
                }).melt(id_vars='Branch', var_name='Care Type', value_name='Revenue')
                
                care_hours = pd.DataFrame({
                    'Branch': branches,
                    care_categories[0]: [2556.5, 309, 3931.60, 4283.5, 3557.25][:len(branches)],
                    care_categories[1]: [2410.5, 295.5, 12306.50, 4309.92, 3451.47][:len(branches)],
                    care_categories[2]: [168, 0, 6048.00, 120, 168][:len(branches)]
                }).melt(id_vars='Branch', var_name='Care Type', value_name='Hours')
            except:
                pass

        return df, care_f, care_hours, branches, revenue_path.name, costs_path.name
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        st.stop()

df, care_f, care_hours, branches, rev_file, cost_file = load_data()

# === HEADER ===
col1, col2 = st.columns([1, 5])
with col1:
    try:
        from PIL import Image
        logo_path = config['branding']['logo_file']
        if Path(logo_path).exists():
            logo = Image.open(logo_path)
            st.image(logo, width=80)
    except:
        pass

with col2:
    st.title(f"{config['client']['name']} – Interactive Dashboard")
    st.markdown(f"**Data Sources:** `{rev_file}` | `{cost_file}` | **Last Updated:** {datetime.now():%d %b %Y, %H:%M}")

st.divider()

# === SIDEBAR FILTERS ===
try:
    from PIL import Image
    logo_path = config['branding']['logo_file']
    if Path(logo_path).exists():
        logo = Image.open(logo_path)
        st.sidebar.image(logo, width=100)
except:
    pass

st.sidebar.header("Filters & Controls")

if st.sidebar.button("Refresh Data Now"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()

all_periods = sorted(df["Period"].unique(), key=lambda x: int(x))
st.sidebar.info(f"**Available Periods:** {', '.join(all_periods)}")

period_option = st.sidebar.radio(
    "Period Selection",
    ["All Periods", "Select Specific", "Latest Only", "Latest 3", "Compare Two"]
)

if period_option == "All Periods":
    sel_periods = all_periods
elif period_option == "Latest Only":
    sel_periods = [all_periods[-1]]
elif period_option == "Latest 3":
    sel_periods = all_periods[-3:]
elif period_option == "Compare Two":
    col1, col2 = st.sidebar.columns(2)
    p1 = col1.selectbox("Period 1", all_periods, index=max(0, len(all_periods)-2))
    p2 = col2.selectbox("Period 2", all_periods, index=len(all_periods)-1)
    sel_periods = [p1, p2]
else:
    sel_periods = st.sidebar.multiselect("Select Periods", all_periods, default=all_periods)
    if not sel_periods:
        sel_periods = all_periods

st.sidebar.markdown("### Branches")
select_all_branches = st.sidebar.checkbox("Select All Branches", value=True)
if select_all_branches:
    sel_branches = branches
else:
    sel_branches = st.sidebar.multiselect("Choose Branches", branches, default=branches)
    if not sel_branches:
        sel_branches = branches

st.sidebar.divider()

st.sidebar.markdown("### Chart Options")
chart_height = st.sidebar.slider("Chart Height", 300, 800, 450)
show_markers = st.sidebar.checkbox("Show Data Points on Lines", value=True)
color_scheme_option = st.sidebar.selectbox("Color Scheme", ["Viridis", "Blues", "Reds", "Greens", "Rainbow"])

color_scheme_map = {
    "Viridis": "Viridis",
    "Blues": "Blues",
    "Reds": "Reds", 
    "Greens": "Greens",
    "Rainbow": "Rainbow"
}
color_scheme = color_scheme_map.get(color_scheme_option, "Viridis")

filtered_df = df[df['Period'].isin(sel_periods) & df['Branch'].isin(sel_branches)].copy()
filtered_care = care_f[care_f['Branch'].isin(sel_branches)].copy() if not care_f.empty else pd.DataFrame()
filtered_care_hours = care_hours[care_hours['Branch'].isin(sel_branches)].copy() if not care_hours.empty else pd.DataFrame()

branch_totals = filtered_df.groupby('Branch').agg({
    'Revenue': 'sum',
    'Hours': 'sum',
    'Cost': 'sum',
    'Gross Profit': 'sum'
}).reset_index()
branch_totals['Margin %'] = (branch_totals['Gross Profit'] / branch_totals['Revenue'] * 100).round(1)

st.sidebar.success(f"Showing: {len(sel_periods)} periods × {len(sel_branches)} branches = {len(filtered_df)} rows")

if len(filtered_df) == 0:
    st.error("No data matches your filters!")
    st.stop()

# === KPI METRICS ===
st.header("Key Performance Indicators")
col1, col2, col3, col4, col5 = st.columns(5)

total_revenue = filtered_df['Revenue'].sum()
total_hours = filtered_df['Hours'].sum()
total_cost = filtered_df['Cost'].sum()
total_profit = filtered_df['Gross Profit'].sum()
avg_margin = filtered_df['Margin %'].mean() if len(filtered_df) > 0 else 0

col1.metric("Total Revenue", f"£{total_revenue:,.0f}")
col2.metric("Total Hours", f"{total_hours:,.0f}")
col3.metric("Total Costs", f"£{total_cost:,.0f}")
col4.metric("Gross Profit", f"£{total_profit:,.0f}")
col5.metric("Avg Margin", f"{avg_margin:.1f}%")

st.divider()

# === PDF EXPORT (if enabled) ===
if config['features']['pdf_export']:
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("📊 Export PDF Report", use_container_width=True):
            import plotly.io as pio
            from reportlab.lib.utils import ImageReader
            from PIL import Image as PILImage
            
            with st.spinner("Generating comprehensive PDF report with graphs..."):
                buffer = BytesIO()
                c = pdf_canvas.Canvas(buffer, pagesize=A4)
                width, height = A4
                
                def add_footer(canvas, page_num):
                    canvas.setFont("Helvetica", 7)
                    canvas.setFillColor(pdf_colors.grey)
                    canvas.drawString(50, 30, f"{config['client']['name']} - Confidential")
                    canvas.drawRightString(width - 50, 30, f"Page {page_num} - {datetime.now():%d/%m/%Y}")
                
                def add_plotly_chart(canvas, fig, x, y, img_width, img_height):
                    img_bytes = pio.to_image(fig, format='png', width=int(img_width*2), height=int(img_height*2), scale=2)
                    img = PILImage.open(BytesIO(img_bytes))
                    img_reader = ImageReader(img)
                    canvas.drawImage(img_reader, x, y, width=img_width, height=img_height)
                
                page_num = 1
                
                # Cover page
                c.setFont("Helvetica-Bold", 28)
                c.drawString(50, height - 80, config['client']['name'])
                c.setFont("Helvetica-Bold", 16)
                c.drawString(50, height - 110, "Executive Dashboard Report")
                c.setFont("Helvetica", 11)
                c.drawString(50, height - 135, f"Generated: {datetime.now():%d %B %Y, %H:%M}")
                
                c.setStrokeColor(pdf_colors.HexColor(config['branding']['primary_color']))
                c.setLineWidth(3)
                c.line(50, height - 165, width - 50, height - 165)
                
                # KPIs
                y_pos = height - 210
                c.setFont("Helvetica-Bold", 14)
                c.drawString(50, y_pos, "Key Performance Indicators")
                
                y_pos -= 30
                
                kpi_data = [
                    ("Total Revenue", f"£{total_revenue:,.0f}", pdf_colors.HexColor(config['branding']['secondary_color'])),
                    ("Total Hours", f"{total_hours:,.0f}", pdf_colors.HexColor(config['branding']['success_color'])),
                    ("Total Costs", f"£{total_cost:,.0f}", pdf_colors.HexColor(config['branding']['warning_color'])),
                    ("Gross Profit", f"£{total_profit:,.0f}", pdf_colors.HexColor('#5B9BD5')),
                    ("Average Margin", f"{avg_margin:.1f}%", pdf_colors.HexColor('#C55A11'))
                ]
                
                box_width = 90
                box_height = 55
                x_start = 50
                y_box = y_pos - 10
                
                for i, (label, value, color) in enumerate(kpi_data):
                    x_pos = x_start + (i * (box_width + 10))
                    c.setFillColor(color)
                    c.setStrokeColor(color)
                    c.rect(x_pos, y_box, box_width, box_height, fill=1, stroke=0)
                    c.setFillColor(pdf_colors.white)
                    c.setFont("Helvetica", 8)
                    c.drawCentredString(x_pos + box_width/2, y_box + box_height - 15, label)
                    c.setFont("Helvetica-Bold", 12)
                    c.drawCentredString(x_pos + box_width/2, y_box + 20, value)
                
                y_pos = y_box - 30
                c.setFillColor(pdf_colors.black)
                
                # Branch table
                y_pos -= 20
                c.setFont("Helvetica-Bold", 12)
                c.drawString(50, y_pos, "Branch Performance Summary")
                
                y_pos -= 25
                c.setFont("Helvetica-Bold", 8)
                c.setFillColor(pdf_colors.HexColor(config['branding']['secondary_color']))
                c.drawString(55, y_pos, "Branch")
                c.drawString(170, y_pos, "Revenue")
                c.drawString(240, y_pos, "Hours")
                c.drawString(300, y_pos, "Cost")
                c.drawString(360, y_pos, "Profit")
                c.drawString(425, y_pos, "Margin")
                
                c.setStrokeColor(pdf_colors.HexColor(config['branding']['secondary_color']))
                c.setLineWidth(1.5)
                c.line(50, y_pos - 3, width - 50, y_pos - 3)
                
                y_pos -= 15
                c.setFont("Helvetica", 7.5)
                c.setFillColor(pdf_colors.black)
                
                for idx, row in branch_totals.iterrows():
                    if y_pos < 100:
                        add_footer(c, page_num)
                        c.showPage()
                        page_num += 1
                        y_pos = height - 50
                    
                    if idx % 2 == 0:
                        c.setFillColor(pdf_colors.HexColor('#F0F0F0'))
                        c.rect(50, y_pos - 3, width - 100, 12, fill=1, stroke=0)
                    
                    c.setFillColor(pdf_colors.black)
                    c.drawString(55, y_pos, row['Branch'][:22])
                    c.drawString(170, y_pos, f"£{row['Revenue']:,.0f}")
                    c.drawString(240, y_pos, f"{row['Hours']:,.0f}")
                    c.drawString(300, y_pos, f"£{row['Cost']:,.0f}")
                    c.drawString(360, y_pos, f"£{row['Gross Profit']:,.0f}")
                    
                    margin_color = pdf_colors.green if row['Margin %'] >= 20 else (pdf_colors.orange if row['Margin %'] >= 10 else pdf_colors.red)
                    c.setFillColor(margin_color)
                    c.drawString(425, y_pos, f"{row['Margin %']:.1f}%")
                    c.setFillColor(pdf_colors.black)
                    
                    y_pos -= 13
                
                add_footer(c, page_num)
                c.showPage()
                
                # Save PDF
                c.save()
                buffer.seek(0)
                
                st.success("✅ PDF Report Generated Successfully!")
                st.download_button(
                    label="⬇️ Download PDF Report",
                    data=buffer,
                    file_name=f"{config['client']['id']}_Report_{datetime.now():%Y%m%d_%H%M}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

st.divider()

# === VISUALIZATION TABS ===
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Trends Over Time", 
    "🏢 Branch Comparison", 
    "💰 Profitability Analysis",
    "🔍 Care Type Breakdown" if config['care_types']['enabled'] else "📊 Data Table",
    "📊 Data Table"
])

# === TAB 1: TRENDS OVER TIME ===
with tab1:
    st.subheader("Revenue & Hours Trends")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Revenue Over Time by Branch")
        fig_rev = px.line(
            filtered_df, 
            x='Period_Int', 
            y='Revenue', 
            color='Branch',
            markers=show_markers,
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig_rev.update_layout(
            height=chart_height,
            xaxis_title="Period",
            yaxis_title="Revenue (£)",
            hovermode='x unified'
        )
        st.plotly_chart(fig_rev, use_container_width=True)
    
    with col2:
        st.markdown("#### Hours Over Time by Branch")
        fig_hrs = px.line(
            filtered_df,
            x='Period_Int',
            y='Hours',
            color='Branch',
            markers=show_markers,
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig_hrs.update_layout(
            height=chart_height,
            xaxis_title="Period",
            yaxis_title="Hours",
            hovermode='x unified'
        )
        st.plotly_chart(fig_hrs, use_container_width=True)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Margin % Trend by Branch")
        fig_margin = px.line(
            filtered_df,
            x='Period_Int',
            y='Margin %',
            color='Branch',
            markers=show_markers,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_margin.update_layout(
            height=chart_height,
            xaxis_title="Period",
            yaxis_title="Margin %",
            hovermode='x unified'
        )
        st.plotly_chart(fig_margin, use_container_width=True)
    
    with col2:
        st.markdown("#### Revenue per Hour Trend")
        fig_rph = px.line(
            filtered_df,
            x='Period_Int',
            y='Rev per Hour',
            color='Branch',
            markers=show_markers,
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_rph.update_layout(
            height=chart_height,
            xaxis_title="Period",
            yaxis_title="Revenue per Hour (£)",
            hovermode='x unified'
        )
        st.plotly_chart(fig_rph, use_container_width=True)

# === TAB 2: BRANCH COMPARISON ===
with tab2:
    st.subheader("Branch Performance Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Total Revenue by Branch")
        fig_branch_rev = px.bar(
            branch_totals.sort_values('Revenue', ascending=True),
            y='Branch',
            x='Revenue',
            orientation='h',
            color='Revenue',
            color_continuous_scale=color_scheme
        )
        fig_branch_rev.update_layout(height=chart_height, showlegend=False)
        st.plotly_chart(fig_branch_rev, use_container_width=True)
    
    with col2:
        st.markdown("#### Total Hours by Branch")
        fig_branch_hrs = px.bar(
            branch_totals.sort_values('Hours', ascending=True),
            y='Branch',
            x='Hours',
            orientation='h',
            color='Hours',
            color_continuous_scale=color_scheme
        )
        fig_branch_hrs.update_layout(height=chart_height, showlegend=False)
        st.plotly_chart(fig_branch_hrs, use_container_width=True)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Gross Profit by Branch")
        fig_branch_profit = px.bar(
            branch_totals.sort_values('Gross Profit', ascending=True),
            y='Branch',
            x='Gross Profit',
            orientation='h',
            color='Gross Profit',
            color_continuous_scale='RdYlGn'
        )
        fig_branch_profit.update_layout(height=chart_height, showlegend=False)
        st.plotly_chart(fig_branch_profit, use_container_width=True)
    
    with col2:
        st.markdown("#### Average Margin % by Branch")
        fig_branch_margin = px.bar(
            branch_totals.sort_values('Margin %', ascending=True),
            y='Branch',
            x='Margin %',
            orientation='h',
            color='Margin %',
            color_continuous_scale='RdYlGn'
        )
        fig_branch_margin.update_layout(height=chart_height, showlegend=False)
        st.plotly_chart(fig_branch_margin, use_container_width=True)
    
    st.divider()
    st.markdown("#### Branch Performance Summary Table")
    st.dataframe(
        branch_totals.style.format({
            'Revenue': '£{:,.0f}',
            'Hours': '{:,.0f}',
            'Cost': '£{:,.0f}',
            'Gross Profit': '£{:,.0f}',
            'Margin %': '{:.1f}%'
        }).background_gradient(subset=['Margin %'], cmap='RdYlGn'),
        use_container_width=True
    )

# === TAB 3: PROFITABILITY ANALYSIS ===
with tab3:
    st.subheader("Profitability Deep Dive")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Revenue vs Cost Comparison")
        
        rev_cost_df = filtered_df.groupby('Branch').agg({
            'Revenue': 'sum',
            'Cost': 'sum'
        }).reset_index()
        
        fig_rev_cost = go.Figure()
        fig_rev_cost.add_trace(go.Bar(
            name='Revenue',
            x=rev_cost_df['Branch'],
            y=rev_cost_df['Revenue'],
            marker_color=config['branding']['primary_color']
        ))
        fig_rev_cost.add_trace(go.Bar(
            name='Cost',
            x=rev_cost_df['Branch'],
            y=rev_cost_df['Cost'],
            marker_color=config['branding']['warning_color']
        ))
        fig_rev_cost.update_layout(
            barmode='group',
            height=chart_height,
            xaxis_title="Branch",
            yaxis_title="Amount (£)"
        )
        st.plotly_chart(fig_rev_cost, use_container_width=True)
    
    with col2:
        st.markdown("#### Profit Margin Distribution")
        fig_margin_dist = px.box(
            filtered_df,
            x='Branch',
            y='Margin %',
            color='Branch',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_margin_dist.update_layout(
            height=chart_height,
            showlegend=False,
            xaxis_title="Branch",
            yaxis_title="Margin %"
        )
        st.plotly_chart(fig_margin_dist, use_container_width=True)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Profitability Heatmap")
        
        pivot_margin = filtered_df.pivot_table(
            values='Margin %',
            index='Branch',
            columns='Period',
            aggfunc='mean'
        )
        
        fig_heatmap = px.imshow(
            pivot_margin,
            labels=dict(x="Period", y="Branch", color="Margin %"),
            color_continuous_scale='RdYlGn',
            aspect='auto'
        )
        fig_heatmap.update_layout(height=chart_height)
        st.plotly_chart(fig_heatmap, use_container_width=True)
    
    with col2:
        st.markdown("#### Revenue vs Margin Scatter")
        scatter_df = filtered_df.groupby('Branch').agg({
            'Revenue': 'sum',
            'Margin %': 'mean',
            'Hours': 'sum'
        }).reset_index()
        
        fig_scatter = px.scatter(
            scatter_df,
            x='Revenue',
            y='Margin %',
            size='Hours',
            color='Branch',
            hover_data=['Branch', 'Revenue', 'Margin %', 'Hours'],
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_scatter.update_layout(
            height=chart_height,
            xaxis_title="Total Revenue (£)",
            yaxis_title="Average Margin %"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

# === TAB 4: CARE TYPE BREAKDOWN (or Data Table) ===
with tab4:
    if config['care_types']['enabled'] and not filtered_care.empty:
        st.subheader("Care Type Breakdown")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Revenue by Care Type")
            fig_care_rev = px.bar(
                filtered_care,
                x='Branch',
                y='Revenue',
                color='Care Type',
                barmode='stack',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_care_rev.update_layout(
                height=chart_height,
                xaxis_title="Branch",
                yaxis_title="Revenue (£)"
            )
            st.plotly_chart(fig_care_rev, use_container_width=True)
        
        with col2:
            st.markdown("#### Hours by Care Type")
            fig_care_hrs = px.bar(
                filtered_care_hours,
                x='Branch',
                y='Hours',
                color='Care Type',
                barmode='stack',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_care_hrs.update_layout(
                height=chart_height,
                xaxis_title="Branch",
                yaxis_title="Hours"
            )
            st.plotly_chart(fig_care_hrs, use_container_width=True)
        
        st.divider()
        
        st.markdown("#### Care Type Distribution by Branch")
        fig_care_pie = px.sunburst(
            filtered_care,
            path=['Branch', 'Care Type'],
            values='Revenue',
            color='Care Type',
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_care_pie.update_layout(height=500)
        st.plotly_chart(fig_care_pie, use_container_width=True)
    else:
        st.subheader("Detailed Data View")
        st.markdown("#### All Data Records")
        st.dataframe(
            filtered_df.style.format({
                'Revenue': '£{:,.0f}',
                'Hours': '{:,.0f}',
                'Cost': '£{:,.0f}',
                'Gross Profit': '£{:,.0f}',
                'Margin %': '{:.1f}%',
                'Rev per Hour': '£{:.2f}'
            }),
            use_container_width=True,
            height=600
        )

# === TAB 5: DATA TABLE ===
with tab5:
    st.subheader("Complete Dataset")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Records", len(filtered_df))
    with col2:
        st.metric("Date Range", f"{filtered_df['Period'].min()} - {filtered_df['Period'].max()}")
    with col3:
        st.metric("Branches", len(sel_branches))
    
    st.divider()
    
    # Download CSV button
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        label="⬇️ Download Data as CSV",
        data=csv,
        file_name=f"{config['client']['id']}_data_{datetime.now():%Y%m%d}.csv",
        mime="text/csv"
    )
    
    st.markdown("#### Filtered Dataset")
    st.dataframe(
        filtered_df.style.format({
            'Revenue': '£{:,.0f}',
            'Hours': '{:,.0f}',
            'Cost': '£{:,.0f}',
            'Gross Profit': '£{:,.0f}',
            'Margin %': '{:.1f}%',
            'Rev per Hour': '£{:.2f}'
        }).background_gradient(subset=['Margin %'], cmap='RdYlGn'),
        use_container_width=True,
        height=600
    )
    
    st.divider()
    
    st.markdown("#### Summary Statistics")
    summary_stats = filtered_df[['Revenue', 'Hours', 'Cost', 'Gross Profit', 'Margin %']].describe()
    st.dataframe(summary_stats.style.format("{:.2f}"), use_container_width=True)

# === FOOTER ===
st.divider()
st.markdown(f"""
<div style='text-align: center; color: #888; padding: 20px;'>
    <p><strong>{config['client']['name']}</strong> | Dashboard v2.0 | Subscription: {config['subscription']['tier']}</p>
    <p>For support, contact: {config['client'].get('contact_email', 'support@example.com')}</p>
</div>
""", unsafe_allow_html=True)
