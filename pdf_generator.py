"""
PDF Report Generator for Care Home Dashboard
Generates professional multi-page PDF reports with embedded Plotly charts
"""

import plotly.io as pio
import plotly.express as px
import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib import colors as pdf_colors
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage
from io import BytesIO
from datetime import datetime
import pandas as pd

# Configure plotly for better compatibility
pio.kaleido.scope.mathjax = None


def add_plotly_chart(canvas, fig, x, y, img_width, img_height):
    """
    Convert Plotly figure to image and add to PDF canvas
    
    Args:
        canvas: ReportLab canvas object
        fig: Plotly figure object
        x, y: Position coordinates
        img_width, img_height: Size of image in points
    """
    try:
        # Convert Plotly figure to PNG bytes
        img_bytes = pio.to_image(
            fig, 
            format='png', 
            width=int(img_width*2),  # 2x for better resolution
            height=int(img_height*2), 
            scale=2
        )
        img = PILImage.open(BytesIO(img_bytes))
        img_reader = ImageReader(img)
        canvas.drawImage(img_reader, x, y, width=img_width, height=img_height)
        return True
    except Exception as e:
        print(f"Error adding chart: {e}")
        # Add error placeholder
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(pdf_colors.red)
        canvas.drawString(x, y + img_height/2, f"[Chart rendering error: {str(e)[:50]}]")
        canvas.setFillColor(pdf_colors.black)
        return False


def add_footer(canvas, page_num, company_name="Platinum Care Group"):
    """Add footer with page number and company name"""
    width, height = A4
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(pdf_colors.grey)
    canvas.drawString(50, 30, f"{company_name} - Confidential")
    canvas.drawRightString(width - 50, 30, f"Page {page_num} - {datetime.now():%d/%m/%Y}")
    canvas.setFillColor(pdf_colors.black)


def generate_revenue_trend_chart(filtered_df):
    """Generate revenue trend line chart by branch"""
    period_branch = filtered_df.groupby(['Period_Int', 'Period', 'Branch'])['Revenue'].sum().reset_index()
    
    fig = px.line(
        period_branch, 
        x='Period', 
        y='Revenue', 
        color='Branch',
        title="Revenue Trend by Branch",
        markers=True,
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig.update_layout(
        height=350,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
        xaxis_title="Period",
        yaxis_title="Revenue (£)",
        font=dict(size=10)
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=8))
    return fig


def generate_care_type_pie_charts(filtered_df, care_type_df):
    """Generate pie charts for revenue and hours by care type"""
    care_type_colors = {
        'Private': '#FDB462',
        'Local Authority': '#80B1D3', 
        'Live-In': '#FB8072'
    }
    
    # Revenue pie chart
    care_totals_rev = care_type_df.groupby('Care Type')['Revenue'].sum().reset_index()
    fig_rev = px.pie(
        care_totals_rev, 
        values='Revenue', 
        names='Care Type',
        hole=0.5,
        title="Revenue by Care Type",
        color='Care Type',
        color_discrete_map=care_type_colors
    )
    fig_rev.update_traces(textposition='outside', textinfo='percent+label')
    fig_rev.update_layout(height=300, showlegend=False, font=dict(size=9))
    
    # Hours pie chart
    care_totals_hrs = care_type_df.groupby('Care Type')['Hours'].sum().reset_index()
    fig_hrs = px.pie(
        care_totals_hrs,
        values='Hours',
        names='Care Type', 
        hole=0.5,
        title="Hours by Care Type",
        color='Care Type',
        color_discrete_map=care_type_colors
    )
    fig_hrs.update_traces(textposition='outside', textinfo='percent+label')
    fig_hrs.update_layout(height=300, showlegend=False, font=dict(size=9))
    
    return fig_rev, fig_hrs


def generate_branch_comparison_charts(branch_totals):
    """Generate branch comparison bar charts"""
    # Revenue by branch
    fig_revenue = px.bar(
        branch_totals,
        x='Branch',
        y='Revenue',
        title="Revenue by Branch",
        color='Revenue',
        color_continuous_scale='Blues',
        text='Revenue'
    )
    fig_revenue.update_traces(texttemplate='£%{text:,.0f}', textposition='outside')
    fig_revenue.update_layout(
        height=300,
        showlegend=False,
        xaxis_title="",
        yaxis_title="Revenue (£)",
        font=dict(size=9)
    )
    
    # Margin by branch
    fig_margin = px.bar(
        branch_totals,
        x='Branch',
        y='Margin %',
        title="Margin % by Branch",
        color='Margin %',
        color_continuous_scale='Viridis',
        text='Margin %'
    )
    fig_margin.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig_margin.update_layout(
        height=300,
        showlegend=False,
        xaxis_title="",
        yaxis_title="Margin %",
        font=dict(size=9)
    )
    
    return fig_revenue, fig_margin


def generate_profit_chart(branch_totals):
    """Generate gross profit bar chart"""
    fig_profit = px.bar(
        branch_totals,
        x='Branch',
        y='Gross Profit',
        title="Gross Profit by Branch",
        color='Gross Profit',
        color_continuous_scale='RdYlGn',
        text='Gross Profit'
    )
    fig_profit.update_traces(texttemplate='£%{text:,.0f}', textposition='outside')
    fig_profit.update_layout(
        height=300,
        showlegend=False,
        xaxis_title="",
        yaxis_title="Gross Profit (£)",
        font=dict(size=9)
    )
    return fig_profit


def generate_hours_trend_chart(filtered_df):
    """Generate hours trend line chart by branch"""
    period_branch = filtered_df.groupby(['Period_Int', 'Period', 'Branch'])['Hours'].sum().reset_index()
    
    fig = px.line(
        period_branch,
        x='Period',
        y='Hours',
        color='Branch',
        title="Hours Trend by Branch",
        markers=True,
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig.update_layout(
        height=300,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
        xaxis_title="Period",
        yaxis_title="Hours",
        font=dict(size=9)
    )
    fig.update_traces(line=dict(width=2), marker=dict(size=6))
    return fig


def generate_margin_trend_chart(filtered_df):
    """Generate margin % trend line chart by branch"""
    period_branch = filtered_df.groupby(['Period_Int', 'Period', 'Branch'])['Margin %'].mean().reset_index()
    
    fig = px.line(
        period_branch,
        x='Period',
        y='Margin %',
        color='Branch',
        title="Margin % Trend by Branch",
        markers=True,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig.update_layout(
        height=300,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
        xaxis_title="Period",
        yaxis_title="Margin %",
        font=dict(size=9)
    )
    fig.update_traces(line=dict(width=2), marker=dict(size=6))
    return fig


def generate_scatter_analysis(filtered_df):
    """Generate revenue vs hours scatter plot"""
    fig = px.scatter(
        filtered_df,
        x='Hours',
        y='Revenue',
        color='Branch',
        size='Revenue',
        hover_data=['Period', 'Margin %', 'Gross Profit'],
        title="Revenue vs Hours Analysis",
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    fig.update_layout(
        height=300,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
        font=dict(size=9)
    )
    
    return fig


def generate_comprehensive_pdf(filtered_df, branch_totals, care_type_df, 
                               total_revenue, total_hours, total_cost, 
                               total_profit, avg_margin, sel_periods, sel_branches,
                               company_name="Platinum Care Group"):
    """
    Generate a comprehensive multi-page PDF report with all visualizations
    
    Args:
        filtered_df: Main dataframe with all data
        branch_totals: Aggregated branch totals
        care_type_df: Care type breakdown dataframe
        total_revenue, total_hours, total_cost, total_profit, avg_margin: KPI values
        sel_periods: List of selected periods
        sel_branches: List of selected branches
        company_name: Name of the company for branding
        
    Returns:
        BytesIO buffer containing the PDF
    """
    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    page_num = 1
    
    # ===== PAGE 1: COVER & EXECUTIVE SUMMARY =====
    c.setFont("Helvetica-Bold", 28)
    c.drawString(50, height - 80, company_name)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 110, "Executive Dashboard Report")
    c.setFont("Helvetica", 11)
    c.drawString(50, height - 135, f"Generated: {datetime.now():%d %B %Y, %H:%M}")
    c.setFont("Helvetica", 9)
    c.drawString(50, height - 150, f"Period(s): {', '.join(sel_periods)}")
    c.drawString(50, height - 165, f"Branches: {', '.join(sel_branches)}")
    
    # Decorative line
    c.setStrokeColor(pdf_colors.HexColor('#667eea'))
    c.setLineWidth(3)
    c.line(50, height - 180, width - 50, height - 180)
    c.setStrokeColor(pdf_colors.black)
    c.setLineWidth(1)
    
    # KPI Section
    y_pos = height - 220
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y_pos, "Key Performance Indicators")
    
    y_pos -= 30
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(pdf_colors.HexColor('#667eea'))
    
    # KPIs in a grid
    kpis = [
        ("Total Revenue", f"£{total_revenue:,.0f}"),
        ("Total Hours", f"{total_hours:,.0f}"),
        ("Total Costs", f"£{total_cost:,.0f}"),
        ("Gross Profit", f"£{total_profit:,.0f}"),
        ("Average Margin", f"{avg_margin:.1f}%")
    ]
    
    x_positions = [50, 180, 310, 440]
    for i, (label, value) in enumerate(kpis[:4]):
        x_pos = x_positions[i % 4]
        if i == 4:
            y_pos -= 60
            x_pos = x_positions[0]
        
        c.setFillColor(pdf_colors.HexColor('#667eea'))
        c.setFont("Helvetica", 8)
        c.drawString(x_pos, y_pos, label)
        c.setFillColor(pdf_colors.black)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x_pos, y_pos - 18, value)
    
    # Executive Summary Text
    y_pos -= 80
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(pdf_colors.black)
    c.drawString(50, y_pos, "Executive Summary")
    
    y_pos -= 20
    c.setFont("Helvetica", 9)
    summary_text = [
        f"This report covers {len(sel_periods)} period(s) across {len(sel_branches)} branch(es).",
        f"Total revenue generated: £{total_revenue:,.0f} from {total_hours:,.0f} hours of care.",
        f"Operating margin achieved: {avg_margin:.1f}% with gross profit of £{total_profit:,.0f}.",
        "",
        "Key Insights:",
        f"• Average revenue per hour: £{(total_revenue/total_hours if total_hours > 0 else 0):.2f}",
        f"• Cost efficiency ratio: {(total_cost/total_revenue*100 if total_revenue > 0 else 0):.1f}%",
        f"• Most profitable branch: {branch_totals.nlargest(1, 'Gross Profit')['Branch'].values[0] if not branch_totals.empty else 'N/A'}"
    ]
    
    for line in summary_text:
        c.drawString(50, y_pos, line)
        y_pos -= 15
    
    add_footer(c, page_num, company_name)
    c.showPage()
    page_num += 1
    
    # ===== PAGE 2: REVENUE & HOURS TRENDS =====
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "Revenue & Hours Trends")
    
    # Revenue trend chart
    try:
        fig_trend = generate_revenue_trend_chart(filtered_df)
        add_plotly_chart(c, fig_trend, 50, height - 400, 495, 280)
    except Exception as e:
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 200, f"[Chart error: {str(e)[:80]}]")
    
    # Hours trend chart
    try:
        fig_hours = generate_hours_trend_chart(filtered_df)
        add_plotly_chart(c, fig_hours, 50, height - 720, 495, 280)
    except Exception as e:
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 520, f"[Chart error: {str(e)[:80]}]")
    
    add_footer(c, page_num, company_name)
    c.showPage()
    page_num += 1
    
    # ===== PAGE 3: PROFITABILITY ANALYSIS =====
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "Profitability Analysis")
    
    # Margin trend chart
    try:
        fig_margin = generate_margin_trend_chart(filtered_df)
        add_plotly_chart(c, fig_margin, 50, height - 400, 495, 280)
    except Exception as e:
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 200, f"[Chart error: {str(e)[:80]}]")
    
    # Branch detailed table
    y_pos = height - 440
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y_pos, "Branch Performance Metrics")
    
    y_pos -= 25
    c.setFont("Helvetica-Bold", 8)
    c.drawString(50, y_pos, "Branch")
    c.drawString(180, y_pos, "Revenue")
    c.drawString(260, y_pos, "Hours")
    c.drawString(330, y_pos, "Costs")
    c.drawString(400, y_pos, "Profit")
    c.drawString(475, y_pos, "Margin %")
    
    c.line(50, y_pos - 3, 530, y_pos - 3)
    
    y_pos -= 15
    c.setFont("Helvetica", 8)
    c.setFillColor(pdf_colors.black)
    
    for _, row in branch_totals.iterrows():
        c.drawString(50, y_pos, str(row['Branch'])[:20])
        c.drawString(180, y_pos, f"£{row['Revenue']:,.0f}")
        c.drawString(260, y_pos, f"{row['Hours']:,.0f}")
        c.drawString(330, y_pos, f"£{row['Cost']:,.0f}")
        c.drawString(400, y_pos, f"£{row['Gross Profit']:,.0f}")
        
        # Color code the margin
        if row['Margin %'] >= avg_margin:
            c.setFillColor(pdf_colors.green)
        else:
            c.setFillColor(pdf_colors.red)
        c.drawString(475, y_pos, f"{row['Margin %']:.1f}%")
        c.setFillColor(pdf_colors.black)
        
        y_pos -= 15
    
    add_footer(c, page_num, company_name)
    c.showPage()
    page_num += 1
    
    # ===== PAGE 4: BRANCH COMPARISONS =====
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "Branch Performance Comparison")
    
    # Branch comparison charts
    try:
        fig_branch_rev, fig_branch_margin = generate_branch_comparison_charts(branch_totals)
        add_plotly_chart(c, fig_branch_rev, 50, height - 380, 240, 250)
        add_plotly_chart(c, fig_branch_margin, 305, height - 380, 240, 250)
    except Exception as e:
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 200, f"[Chart error: {str(e)[:80]}]")
    
    # Profit chart
    try:
        fig_profit = generate_profit_chart(branch_totals)
        add_plotly_chart(c, fig_profit, 50, height - 680, 495, 250)
    except Exception as e:
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 450, f"[Chart error: {str(e)[:80]}]")
    
    add_footer(c, page_num, company_name)
    c.showPage()
    page_num += 1
    
    # ===== PAGE 5: CARE TYPE ANALYSIS =====
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "Care Type Analysis")
    
    # Pie charts side by side
    try:
        fig_care_rev, fig_care_hrs = generate_care_type_pie_charts(filtered_df, care_type_df)
        add_plotly_chart(c, fig_care_rev, 50, height - 380, 240, 250)
        add_plotly_chart(c, fig_care_hrs, 305, height - 380, 240, 250)
    except Exception as e:
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 200, f"[Chart error: {str(e)[:80]}]")
    
    # Care type breakdown table
    y_pos = height - 420
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y_pos, "Care Type Breakdown by Branch")
    
    y_pos -= 25
    c.setFont("Helvetica-Bold", 8)
    c.drawString(50, y_pos, "Branch")
    c.drawString(180, y_pos, "Care Type")
    c.drawString(280, y_pos, "Revenue")
    c.drawString(370, y_pos, "Hours")
    c.drawString(450, y_pos, "% of Total")
    
    c.line(50, y_pos - 3, 530, y_pos - 3)
    
    y_pos -= 15
    c.setFont("Helvetica", 7)
    
    care_breakdown = care_type_df.groupby(['Branch', 'Care Type']).agg({
        'Revenue': 'sum',
        'Hours': 'sum'
    }).reset_index()
    care_breakdown['% of Total'] = (care_breakdown['Revenue'] / care_breakdown['Revenue'].sum() * 100)
    
    for _, row in care_breakdown.head(20).iterrows():
        branch_short = str(row['Branch'])[:20]
        care_short = str(row['Care Type'])[:15]
        c.drawString(50, y_pos, branch_short)
        c.drawString(180, y_pos, care_short)
        c.drawString(280, y_pos, f"£{row['Revenue']:,.0f}")
        c.drawString(370, y_pos, f"{row['Hours']:,.0f}")
        c.drawString(450, y_pos, f"{row['% of Total']:.1f}%")
        y_pos -= 11
        if y_pos < 100:
            break
    
    add_footer(c, page_num, company_name)
    c.showPage()
    page_num += 1
    
    # ===== PAGE 6: SCATTER ANALYSIS =====
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "Advanced Analytics")
    
    # Scatter analysis
    try:
        fig_scatter = generate_scatter_analysis(filtered_df)
        add_plotly_chart(c, fig_scatter, 50, height - 400, 495, 280)
    except Exception as e:
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 200, f"[Chart error: {str(e)[:80]}]")
    
    # Period summary table
    y_pos = height - 440
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y_pos, "Period Summary")
    
    period_summary = filtered_df.groupby('Period').agg({
        'Revenue': 'sum',
        'Hours': 'sum',
        'Cost': 'sum',
        'Gross Profit': 'sum'
    }).reset_index()
    period_summary['Margin %'] = (period_summary['Gross Profit'] / period_summary['Revenue'] * 100).round(1)
    
    y_pos -= 25
    c.setFont("Helvetica-Bold", 8)
    c.drawString(50, y_pos, "Period")
    c.drawString(150, y_pos, "Revenue")
    c.drawString(250, y_pos, "Hours")
    c.drawString(350, y_pos, "Profit")
    c.drawString(450, y_pos, "Margin %")
    
    c.setLineWidth(0.5)
    c.line(50, y_pos - 3, 530, y_pos - 3)
    
    y_pos -= 15
    c.setFont("Helvetica", 8)
    
    for _, row in period_summary.head(10).iterrows():
        margin = (row['Gross Profit'] / row['Revenue'] * 100) if row['Revenue'] > 0 else 0
        c.drawString(50, y_pos, str(row['Period'])[:15])
        c.drawString(150, y_pos, f"£{row['Revenue']:,.0f}")
        c.drawString(250, y_pos, f"{row['Hours']:,.0f}")
        c.drawString(350, y_pos, f"£{row['Gross Profit']:,.0f}")
        c.drawString(450, y_pos, f"{margin:.1f}%")
        y_pos -= 12
        if y_pos < 100:
            break
    
    add_footer(c, page_num, company_name)
    c.showPage()
    page_num += 1
    
    # ===== FINAL PAGE: SUMMARY & RECOMMENDATIONS =====
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "Summary & Recommendations")
    
    y_pos = height - 90
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(pdf_colors.HexColor('#667eea'))
    c.drawString(50, y_pos, "Key Findings:")
    c.setFillColor(pdf_colors.black)
    
    y_pos -= 25
    c.setFont("Helvetica", 10)
    
    # Calculate some insights
    best_branch = branch_totals.nlargest(1, 'Revenue')['Branch'].values[0] if not branch_totals.empty else "N/A"
    best_margin_branch = branch_totals.nlargest(1, 'Margin %')['Branch'].values[0] if not branch_totals.empty else "N/A"
    
    findings = [
        f"1. Highest revenue branch: {best_branch}",
        f"2. Best margin performance: {best_margin_branch}",
        f"3. Overall margin: {avg_margin:.1f}%",
        f"4. Total hours delivered: {total_hours:,.0f}",
        f"5. Average revenue per hour: £{(total_revenue/total_hours if total_hours > 0 else 0):.2f}",
    ]
    
    for finding in findings:
        c.drawString(50, y_pos, finding)
        y_pos -= 20
    
    y_pos -= 20
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(pdf_colors.HexColor('#667eea'))
    c.drawString(50, y_pos, "Strategic Recommendations:")
    c.setFillColor(pdf_colors.black)
    
    y_pos -= 25
    c.setFont("Helvetica", 10)
    
    recommendations = [
        "1. Focus on scaling operations in highest-margin branches",
        "2. Review cost structures in underperforming locations",
        "3. Analyze care type mix for optimization opportunities",
        "4. Consider staff allocation based on revenue per hour metrics",
        "5. Implement monthly review cycles for continuous improvement",
    ]
    
    for rec in recommendations:
        c.drawString(50, y_pos, rec)
        y_pos -= 20
    
    y_pos -= 40
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(pdf_colors.grey)
    c.drawString(50, y_pos, "This report is confidential and intended for management use only.")
    c.drawString(50, y_pos - 15, f"Generated by {company_name} Management Dashboard on {datetime.now():%d %B %Y}")
    
    add_footer(c, page_num, company_name)
    
    # Finalize PDF
    c.save()
    buffer.seek(0)
    
    return buffer


# Simple export function for easy integration
def export_pdf(filtered_df, branch_totals, care_type_df, metrics, filters, company_name="Platinum Care Group"):
    """
    Simplified export function
    
    Args:
        filtered_df: Main filtered dataframe
        branch_totals: Branch aggregation dataframe
        care_type_df: Care type dataframe
        metrics: Dict with keys: total_revenue, total_hours, total_cost, total_profit, avg_margin
        filters: Dict with keys: sel_periods, sel_branches
        company_name: Company name for branding
        
    Returns:
        BytesIO buffer containing the PDF
    """
    return generate_comprehensive_pdf(
        filtered_df=filtered_df,
        branch_totals=branch_totals,
        care_type_df=care_type_df,
        total_revenue=metrics['total_revenue'],
        total_hours=metrics['total_hours'],
        total_cost=metrics['total_cost'],
        total_profit=metrics['total_profit'],
        avg_margin=metrics['avg_margin'],
        sel_periods=filters['sel_periods'],
        sel_branches=filters['sel_branches'],
        company_name=company_name
    )