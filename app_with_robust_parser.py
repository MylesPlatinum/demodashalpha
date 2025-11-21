"""
Configurable Analytics Dashboard with Robust Excel Parsing
Integrates with robust_excel_parser.py for intelligent data loading
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import yaml
from datetime import datetime
import glob

# Import the robust parser and PDF generator
from robust_excel_parser import load_excel_data, RobustExcelParser
from pdf_generator import export_pdf


# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

@st.cache_data
def load_config():
    """Load configuration from config.yaml"""
    config_path = Path("config.yaml")
    if not config_path.exists():
        st.error("⚠️ config.yaml not found! Please create configuration file.")
        st.stop()
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


# ============================================================================
# DATA LOADING WITH ROBUST PARSER
# ============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data_robust(config):
    """
    Load Excel data using the robust parser
    Returns parsed data and validation information
    """
    
    # Get file patterns from config
    revenue_pattern = config.get('data', {}).get('revenue_file_pattern', '*Revenue*.xlsx')
    costs_pattern = config.get('data', {}).get('costs_file_pattern', '*Costs*.xlsx')
    
    # Find latest files
    revenue_files = sorted(glob.glob(revenue_pattern), reverse=True)
    costs_files = sorted(glob.glob(costs_pattern), reverse=True)
    
    if not revenue_files:
        st.error(f"⚠️ No revenue files found matching pattern: {revenue_pattern}")
        return None
    
    if not costs_files:
        st.error(f"⚠️ No costs files found matching pattern: {costs_pattern}")
        return None
    
    revenue_file = revenue_files[0]
    costs_file = costs_files[0]
    
    # Check if debug mode is enabled
    debug_mode = config.get('features', {}).get('debug_mode', False)
    
    # Load revenue data with robust parser
    with st.spinner("🔍 Intelligently parsing revenue data..."):
        revenue_data = load_excel_data(revenue_file, config, debug=debug_mode)
    
    # Load costs data with robust parser  
    with st.spinner("🔍 Intelligently parsing costs data..."):
        costs_data = load_excel_data(costs_file, config, debug=debug_mode)
    
    # Extract DataFrames
    revenue_df = revenue_data['revenue']
    costs_df = costs_data['costs']
    hours_df = revenue_data.get('hours')  # May be None
    
    # Combine validation reports
    validation_info = {
        'revenue_report': revenue_data['validation_report'],
        'costs_report': costs_data['validation_report'],
        'revenue_warnings': revenue_data['warnings'],
        'costs_warnings': costs_data['warnings'],
        'revenue_file': revenue_file,
        'costs_file': costs_file
    }
    
    return {
        'revenue': revenue_df,
        'costs': costs_df,
        'hours': hours_df,
        'validation': validation_info
    }


def show_validation_warnings(validation_info):
    """
    Display validation warnings and parsing information
    """
    total_warnings = len(validation_info.get('revenue_warnings', [])) + \
                    len(validation_info.get('costs_warnings', []))
    
    if total_warnings == 0:
        st.success("✅ All data validations passed - files parsed successfully!")
        return
    
    # Show expandable warning section
    with st.expander(f"⚠️ Data Quality Warnings ({total_warnings})", expanded=False):
        
        # Revenue warnings
        revenue_warnings = validation_info.get('revenue_warnings', [])
        if revenue_warnings:
            st.markdown("**Revenue File Issues:**")
            for warning in revenue_warnings:
                st.warning(warning)
        
        # Costs warnings
        costs_warnings = validation_info.get('costs_warnings', [])
        if costs_warnings:
            st.markdown("**Costs File Issues:**")
            for warning in costs_warnings:
                st.warning(warning)
        
        st.info("💡 The dashboard has automatically corrected these issues where possible. "
               "Review your source Excel files to improve data quality.")


def show_parsing_details(validation_info):
    """
    Show detailed parsing information (when debug mode is enabled)
    """
    with st.expander("🔍 Detailed Parsing Information", expanded=False):
        
        st.markdown("**Files Processed:**")
        st.text(f"Revenue: {validation_info.get('revenue_file', 'Unknown')}")
        st.text(f"Costs: {validation_info.get('costs_file', 'Unknown')}")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Revenue Parsing Report:**")
            st.code(validation_info.get('revenue_report', 'No report available'), 
                   language='text')
        
        with col2:
            st.markdown("**Costs Parsing Report:**")
            st.code(validation_info.get('costs_report', 'No report available'), 
                   language='text')


# ============================================================================
# DATA PROCESSING
# ============================================================================

def prepare_analysis_data(revenue_df, costs_df, hours_df, branches):
    """
    Prepare data for analysis by ensuring proper structure
    """
    
    # Ensure we have a Period column
    if 'Period' not in revenue_df.columns:
        revenue_df.insert(0, 'Period', range(1, len(revenue_df) + 1))
    
    if 'Period' not in costs_df.columns:
        costs_df.insert(0, 'Period', range(1, len(costs_df) + 1))
    
    # Calculate totals
    revenue_df['Total'] = revenue_df[branches].sum(axis=1)
    costs_df['Total'] = costs_df[branches].sum(axis=1)
    
    # Calculate profit and margin
    profit_data = []
    
    for idx, period in enumerate(revenue_df['Period']):
        period_profit = {}
        period_profit['Period'] = period
        
        for branch in branches:
            revenue = revenue_df.loc[idx, branch] if branch in revenue_df.columns else 0
            cost = costs_df.loc[idx, branch] if branch in costs_df.columns else 0
            
            profit = revenue - cost
            margin = (profit / revenue * 100) if revenue > 0 else 0
            
            period_profit[f'{branch}_Profit'] = profit
            period_profit[f'{branch}_Margin'] = margin
        
        # Calculate totals
        total_revenue = revenue_df.loc[idx, 'Total']
        total_cost = costs_df.loc[idx, 'Total']
        period_profit['Total_Profit'] = total_revenue - total_cost
        period_profit['Total_Margin'] = (period_profit['Total_Profit'] / total_revenue * 100) \
                                       if total_revenue > 0 else 0
        
        profit_data.append(period_profit)
    
    profit_df = pd.DataFrame(profit_data)
    
    return revenue_df, costs_df, profit_df


# ============================================================================
# AUTHENTICATION
# ============================================================================

def check_password(config):
    """Password protection for dashboard"""
    
    password = config.get('dashboard', {}).get('password', 'admin')
    
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        
        # Show company branding
        client_name = config.get('client', {}).get('name', 'Analytics Dashboard')
        subtitle = config.get('dashboard', {}).get('subtitle', 'Business Intelligence')
        logo_file = config.get('branding', {}).get('logo_file', '')
        
        # Display logo if available
        if logo_file and Path(logo_file).exists():
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(logo_file, use_container_width=True)
                st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style='text-align: center; padding: 2rem;'>
            <h1 style='color: {config.get('branding', {}).get('primary_color', '#3498db')};'>
                {client_name}
            </h1>
            <h3 style='color: #666;'>{subtitle}</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Password input
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            user_password = st.text_input("Enter Password", type="password", key="password_input")
            
            if st.button("Login", use_container_width=True):
                if user_password == password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ Incorrect password")
        
        # Show company values if configured
        if config.get('company_values', {}).get('show_on_login', False):
            values = config.get('company_values', {}).get('values', [])
            if values:
                st.markdown("---")
                st.markdown("### Our Values")
                cols = st.columns(len(values))
                for idx, value in enumerate(values):
                    with cols[idx]:
                        st.markdown(f"**{value}**")
        
        st.stop()


# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

def create_revenue_trends_chart(revenue_df, branches, colors):
    """Create revenue trends line chart"""
    
    fig = go.Figure()
    
    for idx, branch in enumerate(branches):
        if branch in revenue_df.columns:
            fig.add_trace(go.Scatter(
                x=revenue_df['Period'],
                y=revenue_df[branch],
                name=branch,
                mode='lines+markers',
                line=dict(width=3),
                marker=dict(size=8)
            ))
    
    fig.update_layout(
        title="Revenue Trends by Branch",
        xaxis_title="Period",
        yaxis_title="Revenue (£)",
        height=450,
        hovermode='x unified',
        template='plotly_white'
    )
    
    return fig


def create_branch_comparison_chart(revenue_df, costs_df, profit_df, branches, colors):
    """Create branch comparison horizontal bar chart"""
    
    # Calculate totals for each branch
    branch_totals = []
    
    for branch in branches:
        total_revenue = revenue_df[branch].sum() if branch in revenue_df.columns else 0
        total_cost = costs_df[branch].sum() if branch in costs_df.columns else 0
        total_profit = total_revenue - total_cost
        
        branch_totals.append({
            'Branch': branch,
            'Revenue': total_revenue,
            'Costs': total_cost,
            'Profit': total_profit
        })
    
    df_totals = pd.DataFrame(branch_totals)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=df_totals['Branch'],
        x=df_totals['Revenue'],
        name='Revenue',
        orientation='h',
        marker=dict(color=colors.get('primary_color', '#3498db'))
    ))
    
    fig.add_trace(go.Bar(
        y=df_totals['Branch'],
        x=df_totals['Costs'],
        name='Costs',
        orientation='h',
        marker=dict(color=colors.get('warning_color', '#e74c3c'))
    ))
    
    fig.add_trace(go.Bar(
        y=df_totals['Branch'],
        x=df_totals['Profit'],
        name='Profit',
        orientation='h',
        marker=dict(color=colors.get('success_color', '#27ae60'))
    ))
    
    fig.update_layout(
        title="Branch Performance Comparison",
        xaxis_title="Amount (£)",
        yaxis_title="Branch",
        height=400,
        barmode='group',
        template='plotly_white'
    )
    
    return fig


def create_profitability_chart(profit_df, branches, colors):
    """Create profitability trends chart"""
    
    fig = go.Figure()
    
    for branch in branches:
        margin_col = f'{branch}_Margin'
        if margin_col in profit_df.columns:
            fig.add_trace(go.Scatter(
                x=profit_df['Period'],
                y=profit_df[margin_col],
                name=branch,
                mode='lines+markers',
                line=dict(width=3),
                marker=dict(size=8)
            ))
    
    fig.update_layout(
        title="Profit Margin Trends by Branch",
        xaxis_title="Period",
        yaxis_title="Profit Margin (%)",
        height=450,
        hovermode='x unified',
        template='plotly_white'
    )
    
    return fig


def create_performance_heatmap(revenue_df, branches):
    """Create revenue heatmap"""
    
    # Prepare data for heatmap
    heatmap_data = revenue_df[branches].T
    
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=revenue_df['Period'],
        y=branches,
        colorscale='Blues',
        text=heatmap_data.values,
        texttemplate='£%{text:,.0f}',
        textfont={"size": 10},
        colorbar=dict(title="Revenue (£)")
    ))
    
    fig.update_layout(
        title="Revenue Heatmap by Branch and Period",
        xaxis_title="Period",
        yaxis_title="Branch",
        height=400,
        template='plotly_white'
    )
    
    return fig


# ============================================================================
# PDF EXPORT FUNCTIONS
# ============================================================================

def prepare_pdf_data(revenue_df, costs_df, hours_df, branches):
    """
    Prepare data in the format required by pdf_generator module
    
    Returns tuple of (filtered_df, branch_totals, care_type_df)
    """
    
    # Create a flattened dataframe for PDF export
    pdf_data = []
    
    for idx, row in revenue_df.iterrows():
        period = row['Period']
        
        for branch in branches:
            if branch in revenue_df.columns:
                revenue = row[branch] if pd.notna(row[branch]) else 0
                cost = costs_df.iloc[idx][branch] if branch in costs_df.columns else 0
                hours_val = hours_df.iloc[idx][branch] if hours_df is not None and branch in hours_df.columns else 0
                
                profit = revenue - cost
                margin = (profit / revenue * 100) if revenue > 0 else 0
                rev_per_hour = revenue / hours_val if hours_val > 0 else 0
                
                pdf_data.append({
                    'Period_Int': idx + 1,
                    'Period': f"Period {period}",
                    'Branch': branch,
                    'Revenue': revenue,
                    'Cost': cost,
                    'Hours': hours_val,
                    'Profit': profit,
                    'Margin': margin,
                    'Revenue_per_Hour': rev_per_hour
                })
    
    filtered_df = pd.DataFrame(pdf_data)
    
    # Create branch totals
    branch_totals = filtered_df.groupby('Branch').agg({
        'Revenue': 'sum',
        'Cost': 'sum',
        'Hours': 'sum',
        'Profit': 'sum'
    }).reset_index()
    
    branch_totals['Margin'] = (branch_totals['Profit'] / branch_totals['Revenue'] * 100).fillna(0)
    branch_totals['Revenue_per_Hour'] = (branch_totals['Revenue'] / branch_totals['Hours']).fillna(0)
    
    # Create care type dataframe (placeholder if not available)
    care_type_df = pd.DataFrame({
        'Care Type': ['Private', 'Local Authority', 'Live-In'],
        'Revenue': [0, 0, 0],
        'Hours': [0, 0, 0]
    })
    
    return filtered_df, branch_totals, care_type_df


# ============================================================================
# MAIN DASHBOARD
# ============================================================================

def main():
    """Main dashboard function"""
    
    # Load configuration
    config = load_config()
    
    # Apply custom styling
    primary_color = config.get('branding', {}).get('primary_color', '#3498db')
    
    st.markdown(f"""
    <style>
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {{
            font-size: 1.1rem;
        }}
        .metric-card {{
            background: linear-gradient(135deg, {primary_color}22 0%, {primary_color}11 100%);
            padding: 1.5rem;
            border-radius: 10px;
            border-left: 4px solid {primary_color};
        }}
    </style>
    """, unsafe_allow_html=True)
    
    # Check authentication
    check_password(config)
    
    # Dashboard header
    client_name = config.get('client', {}).get('name', 'Analytics Dashboard')
    subtitle = config.get('dashboard', {}).get('subtitle', 'Business Intelligence')
    logo_file = config.get('branding', {}).get('logo_file', '')
    
    # Display logo and title
    if logo_file and Path(logo_file).exists():
        col1, col2 = st.columns([1, 5])
        with col1:
            st.image(logo_file, width=100)
        with col2:
            st.title(f"📊 {client_name}")
            st.markdown(f"*{subtitle}*")
    else:
        st.title(f"📊 {client_name}")
        st.markdown(f"*{subtitle}*")
    
    st.markdown("---")
    
    # Load data with robust parser
    try:
        data = load_data_robust(config)
        
        if data is None:
            st.error("Failed to load data. Check your Excel files.")
            st.stop()
        
        revenue_df = data['revenue']
        costs_df = data['costs']
        hours_df = data['hours']
        validation_info = data['validation']
        
        # Show validation warnings
        show_validation_warnings(validation_info)
        
        # Show detailed parsing info if debug mode enabled
        if config.get('features', {}).get('debug_mode', False):
            show_parsing_details(validation_info)
        
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        if config.get('features', {}).get('debug_mode', False):
            st.exception(e)
        st.stop()
    
    # Get branches from config
    branches = config.get('data', {}).get('branches', [])
    
    # Prepare analysis data
    revenue_df, costs_df, profit_df = prepare_analysis_data(
        revenue_df, costs_df, hours_df, branches
    )
    
    # Sidebar filters
    st.sidebar.title("🔧 Filters")
    
    # Period filter
    all_periods = sorted(revenue_df['Period'].unique())
    selected_periods = st.sidebar.multiselect(
        "Select Periods",
        options=all_periods,
        default=all_periods
    )
    
    # Branch filter
    selected_branches = st.sidebar.multiselect(
        "Select Branches",
        options=branches,
        default=branches
    )
    
    if not selected_periods or not selected_branches:
        st.warning("⚠️ Please select at least one period and one branch")
        st.stop()
    
    # PDF Export Button
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📄 Export Report")
    
    if st.sidebar.button("📊 Generate PDF Report", use_container_width=True):
        with st.spinner("🔄 Generating comprehensive PDF report..."):
            try:
                # Prepare data for PDF
                pdf_filtered_df, pdf_branch_totals, pdf_care_type_df = prepare_pdf_data(
                    revenue_filtered, costs_filtered, hours_df, selected_branches
                )
                
                # Calculate metrics
                total_revenue = revenue_filtered[selected_branches].sum().sum()
                total_costs = costs_filtered[selected_branches].sum().sum()
                total_profit = total_revenue - total_costs
                avg_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
                
                # Calculate total hours (if available)
                if hours_df is not None:
                    hours_filtered = hours_df[hours_df['Period'].isin(selected_periods)]
                    total_hours = hours_filtered[selected_branches].sum().sum()
                else:
                    total_hours = 0
                
                metrics = {
                    'total_revenue': total_revenue,
                    'total_hours': total_hours,
                    'total_cost': total_costs,
                    'total_profit': total_profit,
                    'avg_margin': avg_margin
                }
                
                filters = {
                    'sel_periods': selected_periods,
                    'sel_branches': selected_branches
                }
                
                # Get company name from config
                company_name = config.get('client', {}).get('name', 'Analytics Dashboard')
                
                # Generate PDF
                pdf_buffer = export_pdf(
                    filtered_df=pdf_filtered_df,
                    branch_totals=pdf_branch_totals,
                    care_type_df=pdf_care_type_df,
                    metrics=metrics,
                    filters=filters,
                    company_name=company_name
                )
                
                # Create download button
                st.sidebar.download_button(
                    label="⬇️ Download PDF Report",
                    data=pdf_buffer,
                    file_name=f"{company_name.replace(' ', '_')}_Report_{datetime.now():%Y%m%d_%H%M}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                
                st.sidebar.success("✅ PDF report generated successfully!")
                
            except Exception as e:
                st.sidebar.error(f"❌ Error generating PDF: {str(e)}")
                if config.get('features', {}).get('debug_mode', False):
                    st.sidebar.exception(e)
    
    # Filter data
    revenue_filtered = revenue_df[revenue_df['Period'].isin(selected_periods)].copy()
    costs_filtered = costs_df[costs_df['Period'].isin(selected_periods)].copy()
    profit_filtered = profit_df[profit_df['Period'].isin(selected_periods)].copy()
    
    # Calculate KPIs
    total_revenue = revenue_filtered[selected_branches].sum().sum()
    total_costs = costs_filtered[selected_branches].sum().sum()
    total_profit = total_revenue - total_costs
    avg_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    # Display KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    
    colors = config.get('branding', {})
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("💰 Total Revenue", f"£{total_revenue:,.0f}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("💸 Total Costs", f"£{total_costs:,.0f}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("📈 Gross Profit", f"£{total_profit:,.0f}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        margin_color = colors.get('success_color', '#27ae60') if avg_margin > 20 else \
                      colors.get('warning_color', '#e74c3c') if avg_margin < 10 else \
                      colors.get('secondary_color', '#2ecc71')
        st.metric("📊 Margin %", f"{avg_margin:.1f}%")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col5:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("📅 Periods", len(selected_periods))
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Revenue Trends",
        "🏢 Branch Comparison", 
        "💹 Profitability Analysis",
        "🔥 Performance Heatmap"
    ])
    
    with tab1:
        st.plotly_chart(
            create_revenue_trends_chart(revenue_filtered, selected_branches, colors),
            use_container_width=True
        )
        
        with st.expander("📊 View Revenue Data Table"):
            st.dataframe(revenue_filtered[['Period'] + selected_branches], 
                        use_container_width=True)
    
    with tab2:
        st.plotly_chart(
            create_branch_comparison_chart(revenue_filtered, costs_filtered, 
                                          profit_filtered, selected_branches, colors),
            use_container_width=True
        )
        
        # Summary table
        branch_summary = []
        for branch in selected_branches:
            rev = revenue_filtered[branch].sum() if branch in revenue_filtered.columns else 0
            cost = costs_filtered[branch].sum() if branch in costs_filtered.columns else 0
            profit = rev - cost
            margin = (profit / rev * 100) if rev > 0 else 0
            
            branch_summary.append({
                'Branch': branch,
                'Revenue': f"£{rev:,.0f}",
                'Costs': f"£{cost:,.0f}",
                'Profit': f"£{profit:,.0f}",
                'Margin %': f"{margin:.1f}%"
            })
        
        st.dataframe(pd.DataFrame(branch_summary), use_container_width=True)
    
    with tab3:
        st.plotly_chart(
            create_profitability_chart(profit_filtered, selected_branches, colors),
            use_container_width=True
        )
        
        # Margin insights
        st.markdown("### 💡 Margin Insights")
        
        for branch in selected_branches:
            margin_col = f'{branch}_Margin'
            if margin_col in profit_filtered.columns:
                avg_margin_branch = profit_filtered[margin_col].mean()
                
                if avg_margin_branch > 20:
                    emoji = "🟢"
                    status = "Excellent"
                elif avg_margin_branch > 10:
                    emoji = "🟡"
                    status = "Good"
                else:
                    emoji = "🔴"
                    status = "Needs Attention"
                
                st.markdown(f"{emoji} **{branch}**: {avg_margin_branch:.1f}% - *{status}*")
    
    with tab4:
        st.plotly_chart(
            create_performance_heatmap(revenue_filtered, selected_branches),
            use_container_width=True
        )
        
        st.info("💡 Darker colors indicate higher revenue. Use this to identify "
               "top-performing branches and periods at a glance.")
    
    # Footer
    st.markdown("---")
    st.markdown(f"""
    <div style='text-align: center; color: #666; padding: 1rem;'>
        <small>
            Powered by Robust Analytics Engine | 
            Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} |
            Client: {config.get('client', {}).get('id', 'unknown')}
        </small>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
