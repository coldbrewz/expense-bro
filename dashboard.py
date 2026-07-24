import os
import sqlite3
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Set page config
st.set_page_config(
    page_title="Expense Bro Dashboard",
    page_icon="📊",
    layout="wide"
)

# 🔒 Simple Password Protection
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "").strip()

if DASHBOARD_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
        
    if not st.session_state["authenticated"]:
        # Custom CSS Injection for a premium glassmorphic dark-theme look
        st.markdown("""
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&display=swap" rel="stylesheet">
            <style>
                /* Hide sidebar, footer and headers on login page */
                [data-testid="stSidebar"] { display: none !important; }
                [data-testid="stHeader"] { display: none !important; }
                footer { visibility: hidden !important; }
                
                /* Radial background gradient - Darker Shade of Blue */
                .stApp {
                    background: radial-gradient(circle at 50% 10%, #0b1a30 0%, #050b14 100%) !important;
                    font-family: 'Outfit', sans-serif !important;
                }
                
                /* Login Card container */
                .login-card {
                    max-width: 440px;
                    margin: 60px auto 10px auto;
                    padding: 40px 30px;
                    background: rgba(255, 255, 255, 0.02) !important;
                    border: 1px solid rgba(255, 255, 255, 0.05) !important;
                    border-radius: 24px !important;
                    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7) !important;
                    backdrop-filter: blur(25px) !important;
                    -webkit-backdrop-filter: blur(25px) !important;
                    text-align: center;
                    color: white;
                }
                
                /* Floating glowing credit card icon */
                .icon-glow {
                    font-size: 4rem;
                    display: inline-block;
                    margin-bottom: 20px;
                    filter: drop-shadow(0 0 15px rgba(29, 78, 216, 0.5));
                    animation: float 3s ease-in-out infinite;
                }
                
                @keyframes float {
                    0% { transform: translateY(0px); }
                    50% { transform: translateY(-10px); }
                    100% { transform: translateY(0px); }
                }
                
                .title-text {
                    font-size: 2.2rem;
                    font-weight: 800;
                    margin-bottom: 8px;
                    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }
                
                .sub-text {
                    color: #8a9ca8;
                    font-size: 0.95rem;
                    margin-bottom: 30px;
                    line-height: 1.5;
                }
                
                /* Custom styling for Streamlit's text input container */
                div[data-baseweb="input"] {
                    background-color: rgba(255, 255, 255, 0.03) !important;
                    border: 1px solid rgba(255, 255, 255, 0.08) !important;
                    border-radius: 12px !important;
                    color: white !important;
                    height: 50px !important;
                }
                
                div[data-baseweb="input"]:focus-within {
                    border-color: #2563eb !important;
                    box-shadow: 0 0 12px rgba(37, 99, 235, 0.3) !important;
                }
                
                input {
                    color: white !important;
                    text-align: center !important;
                    font-size: 1.1rem !important;
                }
                
                /* Custom styling for Streamlit button */
                button[kind="secondary"] {
                    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
                    color: white !important;
                    border: none !important;
                    border-radius: 12px !important;
                    padding: 12px 24px !important;
                    font-weight: 700 !important;
                    font-size: 1rem !important;
                    width: 100% !important;
                    transition: all 0.3s ease !important;
                    box-shadow: 0 4px 15px rgba(29, 78, 216, 0.3) !important;
                    margin-top: 15px !important;
                    cursor: pointer !important;
                }
                
                button[kind="secondary"]:hover {
                    transform: translateY(-2px) !important;
                    box-shadow: 0 6px 20px rgba(29, 78, 216, 0.5) !important;
                    color: white !important;
                }
                
                button[kind="secondary"]:active {
                    transform: translateY(0px) !important;
                }
                
                .footer-info {
                    margin-top: 25px;
                    font-size: 0.75rem;
                    color: #718096;
                    line-height: 1.4;
                }
            </style>
        """, unsafe_allow_html=True)
        
        # Render custom glassmorphic Card
        st.markdown("""
            <div class="login-card">
                <div class="icon-glow">💳</div>
                <div class="title-text">Expense Tracker</div>
                <div class="sub-text">Private Budget Dashboard & CC Optimizer.<br>Enter password to unlock.</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Display the input form centered nicely
        col_space1, col_form, col_space2 = st.columns([1, 4, 1])
        with col_form:
            password_input = st.text_input("", type="password", placeholder="••••••••")
            if st.button("Unlock Dashboard") or (password_input and len(password_input) > 0):
                if password_input == DASHBOARD_PASSWORD:
                    st.session_state["authenticated"] = True
                    st.rerun()
                elif password_input:
                    st.error("Incorrect password.")
                    
            st.markdown('<div class="footer-info">Securely isolated on private VM.<br>Managed via Cloudflare Zero Trust.</div>', unsafe_allow_html=True)
            
        st.stop()

# --- DATABASE LOAD ---
DB_PATH = os.path.join("data", "expenses.db")

def load_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT id, timestamp, merchant, amount, category, billing_cycle, account, expense_category FROM transactions"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

df = load_data()

# Helper formatting function
def format_rupiah(value):
    return f"Rp {value:,.0f}".replace(",", ".")

# --- GLOBAL STYLING OVERRIDES ---
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        /* Main background & Typography */
        .stApp {
            background-color: #08090d !important;
            color: #ffffff !important;
            font-family: 'Outfit', sans-serif !important;
        }
        
        /* Headers */
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Outfit', sans-serif !important;
            font-weight: 700 !important;
            color: white !important;
        }
        
        /* Selectbox styling */
        div[data-baseweb="select"] {
            background-color: #12141c !important;
            border: 1px solid #1f232e !important;
            border-radius: 12px !important;
        }
        div[data-baseweb="select"] * {
            color: white !important;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #0b0c10 !important;
            border-right: 1px solid #151821 !important;
        }
        
        /* Card Wrapper styling */
        .dashboard-card {
            background: #111219;
            border: 1px solid #1c1e28;
            border-radius: 18px;
            padding: 24px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
            margin-bottom: 20px;
        }
        
        .card-header {
            font-size: 1rem;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            letter-spacing: 0.5px;
        }
        
        /* Custom progress bar */
        .progress-container {
            margin-bottom: 18px;
        }
        .progress-label-row {
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
            color: #8a9ca8;
            margin-bottom: 6px;
            font-weight: 600;
        }
        .progress-bar-bg {
            background: #191b24;
            border-radius: 10px;
            height: 8px;
            width: 100%;
            overflow: hidden;
        }
        .progress-bar-fill {
            height: 100%;
            border-radius: 10px;
            transition: width 0.5s ease-in-out;
        }
    </style>
""", unsafe_allow_html=True)

# Custom KPI Card Renderer
def render_kpi_card(title, value, subtitle, icon, delta=None, delta_color="green"):
    delta_html = ""
    if delta:
        color = "#10b981" if delta_color == "green" else "#ef4444"
        arrow = "↑" if delta_color == "green" else "↓"
        delta_html = f'<div style="color: {color}; font-size: 0.8rem; margin-top: 4px; font-weight: 700;">{arrow} {delta}</div>'
        
    return f"""
    <div style="
        background: #111219;
        border: 1px solid #1c1e28;
        border-radius: 18px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        justify-content: space-between;
    ">
        <div>
            <div style="color: #8a9ca8; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">{title}</div>
            <div style="color: #ffffff; font-size: 1.55rem; font-weight: 800; font-family: 'Outfit', sans-serif;">{value}</div>
            <div style="color: #4a5568; font-size: 0.75rem; margin-top: 2px;">{subtitle}</div>
            {delta_html}
        </div>
        <div style="
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 12px;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4rem;
        ">
            {icon}
        </div>
    </div>
    """

# --- HERO HEADER ---
st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 30px; flex-wrap: wrap; gap: 15px;">
        <div>
            <h1 style="margin:0; font-weight:800; font-size:2rem; background: linear-gradient(135deg, #ffffff 0%, #a0aec0 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">Good evening, Najih 👋</h1>
            <p style="margin:5px 0 0 0; color:#8a9ca8; font-size:0.95rem;">Here's what's happening with your finances today.</p>
        </div>
        <div style="background: #111219; border: 1px solid #1c1e28; border-radius: 12px; padding: 8px 16px; font-weight: 600; font-size: 0.9rem; color:#8a9ca8; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            📅 Billing Cycle: <span style="color:#3b82f6;">{selected_cycle}</span>
        </div>
    </div>
""", unsafe_allow_html=True)

# --- CALCULATIONS ---
cc_df = cycle_df[cycle_df['account'] == 'permata_cc']
online_spend = cc_df[cc_df['category'] == 'ONLINE']['amount'].sum()
offline_spend = cc_df[cc_df['category'] == 'OFFLINE']['amount'].sum()
unmapped_spend = cc_df[~cc_df['category'].isin(['ONLINE', 'OFFLINE'])]['amount'].sum()
total_cc_spend = online_spend + offline_spend + unmapped_spend

all_total = cycle_df['amount'].sum()

activation_gate = 5000000
gate_delta = activation_gate - total_cc_spend

# --- TOP METRICS CARDS ROW ---
kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

with kpi_col1:
    st.markdown(render_kpi_card(
        title="Total Monthly Spend",
        value=format_rupiah(all_total),
        subtitle="Across all active accounts",
        icon="💰"
    ), unsafe_allow_html=True)

with kpi_col2:
    st.markdown(render_kpi_card(
        title="Permata CC Spend",
        value=format_rupiah(total_cc_spend),
        subtitle="Counting toward 5M gate",
        icon="💳"
    ), unsafe_allow_html=True)

with kpi_col3:
    if gate_delta <= 0:
        st.markdown(render_kpi_card(
            title="Cashback Progress",
            value="Target Met!",
            subtitle="5M spend gate cleared",
            icon="🎯",
            delta="100% Completed",
            delta_color="green"
        ), unsafe_allow_html=True)
    else:
        pct_gate = int((total_cc_spend / activation_gate) * 100)
        st.markdown(render_kpi_card(
            title="Cashback Progress",
            value=format_rupiah(gate_delta),
            subtitle="Remaining to 5M gate",
            icon="🎯",
            delta=f"{pct_gate}% completed",
            delta_color="green"
        ), unsafe_allow_html=True)

with kpi_col4:
    if gate_delta <= 0:
        st.markdown(render_kpi_card(
            title="Cashback Status",
            value="✅ ACTIVE",
            subtitle="Promo yields are live",
            icon="🔥"
        ), unsafe_allow_html=True)
    else:
        st.markdown(render_kpi_card(
            title="Cashback Status",
            value="❌ INACTIVE",
            subtitle="5M gate not reached yet",
            icon="❄️"
        ), unsafe_allow_html=True)


# --- MAIN CHARTS ROW (2 Columns) ---
chart_col1, chart_col2 = st.columns([5, 4])

with chart_col1:
    st.subheader("📈 Cash Flow Overview")
    
    # Process daily spending trend
    daily_df = cycle_df.groupby('date')['amount'].sum().reset_index()
    daily_df = daily_df.sort_values(by='date')
    
    if not daily_df.empty:
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=daily_df['date'],
            y=daily_df['amount'],
            mode='lines+markers',
            name='Daily Spend',
            line=dict(color='#3b82f6', width=3.5),
            marker=dict(size=7, color='#1d4ed8', borderwidth=1, bordercolor='white'),
            fill='tozeroy',
            fillcolor='rgba(59, 130, 246, 0.06)'
        ))
        fig_trend.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#8a9ca8',
            font_family='Outfit',
            xaxis=dict(
                showgrid=False,
                linecolor='#1c1e28',
                tickfont=dict(size=10, color='#8a9ca8')
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='#161720',
                linecolor='#1c1e28',
                tickfont=dict(size=10, color='#8a9ca8')
            ),
            margin=dict(t=20, b=20, l=10, r=10),
            height=320,
            showlegend=False
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No daily data available for this cycle.")

with chart_col2:
    st.subheader("🍩 Spending by Category")
    
    cat_spend = cycle_df.groupby('expense_category')['amount'].sum().reset_index().sort_values(by='amount', ascending=False)
    
    if not cat_spend.empty:
        # Custom color sequence for categories to look premium
        cat_colors_seq = ['#3b82f6', '#10b981', '#a855f7', '#f59e0b', '#ec4899', '#14b8a6', '#ef4444', '#6b7280']
        
        fig_cat = px.pie(
            cat_spend,
            values='amount',
            names='expense_category',
            hole=0.62,
            color='expense_category',
            color_discrete_sequence=cat_colors_seq
        )
        fig_cat.update_traces(textinfo='percent', hovertemplate="%{label}: Rp %{value:,.0f}")
        fig_cat.add_annotation(
            text=f"<span style='color:#8a9ca8; font-size:0.8rem; font-weight:600;'>TOTAL</span><br><b style='color:white; font-size:1.2rem; font-family:Outfit;'>{format_rupiah(all_total)}</b>",
            showarrow=False,
            align="center"
        )
        fig_cat.update_layout(
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_family='Outfit',
            margin=dict(t=10, b=10, l=10, r=10),
            height=320
        )
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("No category data available.")


# --- WARNING TRIGGERS (If applicable) ---
if online_spend > 4000000:
    st.warning(f"⚠️ **Online Cap Exceeded:** You spent {format_rupiah(online_spend - 4000000)} over the optimal 4jt online CC cashback cap.")
if offline_spend > 2000000:
    st.warning(f"⚠️ **Offline Cap Exceeded:** You spent {format_rupiah(offline_spend - 2000000)} over the optimal 2jt offline CC cashback cap.")


# --- THREE BOTTOM WIDGETS ROW ---
st.write("---")
bottom_col1, bottom_col2, bottom_col3 = st.columns(3)

# Shared icons and colors
cat_icons = {
    "food": "🍔",
    "groceries": "🛒",
    "transport": "🚗",
    "entertainment": "🎬",
    "shopping": "🛍️",
    "bills": "📄",
    "investment": "📈",
    "family": "❤️",
    "misc": "📦"
}

cat_colors = {
    "food": "#ef4444",      # red
    "groceries": "#10b981", # emerald
    "transport": "#3b82f6", # blue
    "entertainment": "#a855f7", # purple
    "shopping": "#ec4899",  # pink
    "bills": "#f59e0b",     # amber
    "investment": "#14b8a6", # teal
    "family": "#f43f5e",    # rose
    "misc": "#6b7280"       # grey
}

with bottom_col1:
    # 📋 Recent Transactions List
    recent_txs = cycle_df.sort_values(by='id', ascending=False).head(5)
    
    recent_html = []
    recent_html.append('<div class="dashboard-card" style="height: 480px; overflow-y: auto;">')
    recent_html.append('<div class="card-header"><span>📋 Recent Transactions</span><span style="font-size:0.75rem; color:#8a9ca8;">Latest 5</span></div>')
    
    if not recent_txs.empty:
        for _, row in recent_txs.iterrows():
            icon = cat_icons.get(row['expense_category'], "📦")
            color = cat_colors.get(row['expense_category'], "#6b7280")
            formatted_amt = f"-{format_rupiah(row['amount'])}"
            
            # Map accounts to clean badges
            acc_labels = {
                "permata_cc": "💳 CC",
                "bank_saqu": "🐷 Saqu",
                "bca": "🏦 BCA",
                "line_bank": "📱 Line",
                "general": "💰 Cash"
            }
            acc_badge = acc_labels.get(row['account'], row['account'].upper())
            
            recent_html.append(f"""
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #1c1e28;">
                <div style="display: flex; align-items: center;">
                    <div style="
                        background: rgba(255,255,255,0.01);
                        border: 1px solid #1c1e28;
                        border-radius: 12px;
                        width: 42px;
                        height: 42px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 1.25rem;
                        margin-right: 12px;
                    ">{icon}</div>
                    <div>
                        <div style="color: #ffffff; font-size: 0.9rem; font-weight: 600; font-family: 'Outfit';">{row['merchant']}</div>
                        <div style="color: #4a5568; font-size: 0.75rem; margin-top: 2px;">{row['date']} • <span style="color: {color}; font-weight: 600; font-size: 0.7rem; text-transform: uppercase;">{row['expense_category']}</span> • <span style="color: #a0aec0; font-size: 0.7rem;">{acc_badge}</span></div>
                    </div>
                </div>
                <div style="color: #ef4444; font-size: 0.95rem; font-weight: 700; font-family: 'Outfit';">{formatted_amt}</div>
            </div>
            """)
    else:
        recent_html.append('<div style="color:#718096; text-align:center; padding: 40px 0;">No transactions recorded this cycle.</div>')
        
    recent_html.append('</div>')
    st.markdown("\n".join(recent_html), unsafe_allow_html=True)

with bottom_col2:
    # 🎯 Budget Overview Progress Bars
    budget_limits = {
        "food": 2000000,
        "groceries": 1500000,
        "transport": 1000000,
        "shopping": 2000000,
        "bills": 1500000,
        "entertainment": 1000000,
        "investment": 3000000,
        "family": 3000000,
        "misc": 1000000
    }
    
    budget_html = []
    budget_html.append('<div class="dashboard-card" style="height: 480px; overflow-y: auto;">')
    budget_html.append('<div class="card-header"><span>🎯 Budget Overview</span><span style="font-size:0.75rem; color:#8a9ca8;">Limits</span></div>')
    
    # Calculate spends per category
    cat_spends_dict = cycle_df.groupby('expense_category')['amount'].sum().to_dict()
    
    for cat_name, limit in budget_limits.items():
        spent = cat_spends_dict.get(cat_name, 0)
        pct = min(1.0, spent / limit) if limit > 0 else 0
        pct_display = int(pct * 100)
        color = cat_colors.get(cat_name, "#3b82f6")
        
        spent_str = format_rupiah(spent)
        limit_str = format_rupiah(limit)
        icon = cat_icons.get(cat_name, "📦")
        
        budget_html.append(f"""
        <div class="progress-container">
            <div class="progress-label-row">
                <span>{icon} {cat_name.capitalize()}</span>
                <span>{spent_str} / {limit_str} <span style="color: {color}; font-weight: 700; margin-left: 2px;">{pct_display}%</span></span>
            </div>
            <div class="progress-bar-bg">
                <div class="progress-bar-fill" style="width: {pct_display}%; background: {color};"></div>
            </div>
        </div>
        """)
        
    budget_html.append('</div>')
    st.markdown("\n".join(budget_html), unsafe_allow_html=True)

with bottom_col3:
    # ✨ AI Insights & Cloud Mesh Layout
    insights_html = []
    insights_html.append(f"""
    <div class="dashboard-card" style="
        height: 480px; 
        background: radial-gradient(circle at 100% 100%, #0c1020 0%, #0d0e12 100%);
        border: 1px solid #1c2236;
        position: relative;
        overflow: hidden;
    ">
        <!-- Style Inspo Grid Mesh Overlay -->
        <div style="
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background-image: linear-gradient(rgba(255, 255, 255, 0.007) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(255, 255, 255, 0.007) 1px, transparent 1px);
            background-size: 24px 24px;
            pointer-events: none;
        "></div>
        
        <div style="position: relative; z-index: 1;">
            <div class="card-header">
                <span>✨ AI Insights & Tips</span>
                <span style="
                    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
                    color: white;
                    font-size: 0.65rem;
                    padding: 3px 8px;
                    border-radius: 20px;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">Smart Hub</span>
            </div>
    """)
    
    # Generate dynamic lists of insights
    bullets = []
    
    # 1. Gate analysis
    if gate_delta > 0:
        bullets.append(f"🔴 <b>Cashback Alert:</b> Spend <b>{format_rupiah(gate_delta)}</b> more on your Permata CC to trigger the 5jt cashback gate. Try routing offline spends here.")
    else:
        bullets.append("🟢 <b>Target Cleared:</b> You've unlocked the CC cashback gate! Remaining spends now generate optimal promo yields.")
        
    # 2. Optimal caps
    if online_spend > 4000000:
        bullets.append(f"⚠️ <b>Online Cap Warning:</b> You've exceeded the 4M online cap by <b>{format_rupiah(online_spend - 4000000)}</b>. Offline is currently the higher yielding channel.")
    else:
        bullets.append(f"🌐 <b>Online CC Buffer:</b> You have <b>{format_rupiah(4000000 - online_spend)}</b> left under your optimal 4jt online cap.")
        
    # 3. Top spend
    if not cat_spend.empty:
        top_c = cat_spend.iloc[0]['expense_category']
        top_a = cat_spend.iloc[0]['amount']
        bullets.append(f"📈 <b>Top Expense:</b> <b>{top_c.capitalize()}</b> is your highest spending category this month, totaling <b>{format_rupiah(top_a)}</b>.")
        
    # 4. Bank Saqu advice
    bullets.append("💡 <b>Pockets Yield:</b> Hold your main payroll savings inside Bank Saqu high-yield pockets to earn interest, only drawing via BCA/Line as needed.")
    
    for bullet in bullets:
        insights_html.append(f"""
        <div style="
            display: flex;
            align-items: flex-start;
            margin-bottom: 16px;
            background: rgba(255, 255, 255, 0.015);
            border: 1px solid rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 12px;
        ">
            <div style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.45;">{bullet}</div>
        </div>
        """)
        
    insights_html.append("""
        </div>
    </div>
    """)
    st.markdown("\n".join(insights_html), unsafe_allow_html=True)


# Data List view with interactive editor
st.write("---")
st.subheader("📋 Transactions Manager")
st.markdown("💡 *Double-click any cell to edit. Select a row and press Delete/Backspace on your keyboard to remove. Click the **+** button at the bottom of the table to add a new transaction. Save your changes using the button below.*")

show_cols = ['id', 'date', 'merchant', 'amount', 'account', 'expense_category', 'category']
# Make sure amount is numeric and date is a datetime.date object
display_df = cycle_df[show_cols].copy()
display_df['amount'] = display_df['amount'].astype(int)
display_df['date'] = pd.to_datetime(display_df['date']).dt.date

# Sort display_df descending by ID so newest is on top
display_df = display_df.sort_values(by='id', ascending=False)

if "editor_key" not in st.session_state:
    st.session_state.editor_key = 0

state_key = f"editor_{st.session_state.editor_key}"

edited_df = st.data_editor(
    display_df,
    key=state_key,
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True, help="Database Primary Key (ReadOnly)"),
        "date": st.column_config.DateColumn("Date", required=True),
        "merchant": st.column_config.TextColumn("Merchant", required=True),
        "amount": st.column_config.NumberColumn("Amount (IDR)", required=True, min_value=0, format="%d"),
        "account": st.column_config.SelectboxColumn("Account", options=["permata_cc", "bank_saqu", "bca", "line_bank", "general"], required=True),
        "expense_category": st.column_config.SelectboxColumn("Budget Category", options=["food", "groceries", "transport", "entertainment", "shopping", "bills", "investment", "family", "misc"], required=True),
        "category": st.column_config.SelectboxColumn("CC Category", options=["ONLINE", "OFFLINE", "Non-CC"], required=True)
    },
    hide_index=True,
    use_container_width=True,
    num_rows="dynamic"
)

# Check if there are unsaved changes
has_changes = False
changes = st.session_state.get(state_key, {})
if changes:
    edited = changes.get("edited_rows", {})
    added = changes.get("added_rows", [])
    deleted = changes.get("deleted_rows", [])
    if edited or added or deleted:
        has_changes = True

if has_changes:
    st.info("⚠️ You have unsaved changes in the transaction table!")
    if st.button("💾 Save Database Changes", type="primary", use_container_width=True):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 1. Process edited rows
            for row_idx, row_changes in edited.items():
                tx_id = int(display_df.iloc[row_idx]['id'])
                for field, new_value in row_changes.items():
                    if field == 'amount':
                        new_value = int(new_value)
                    elif field == 'expense_category':
                        new_value = new_value.lower()
                    
                    cursor.execute(f"UPDATE transactions SET {field} = ? WHERE id = ?", (new_value, tx_id))
            
            # 2. Process deleted rows
            for row_idx in deleted:
                tx_id = int(display_df.iloc[row_idx]['id'])
                cursor.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
                
            # 3. Process added rows
            for new_row in added:
                merchant = new_row.get("merchant", "New Transaction")
                amount = int(new_row.get("amount", 0))
                account = new_row.get("account", "general")
                expense_category = new_row.get("expense_category", "misc")
                category = new_row.get("category", "Non-CC")
                
                date_val = new_row.get("date", datetime.now().date())
                
                # Convert date object or string to format YYYY-MM-DD
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                    date_obj = date_val
                else:
                    date_str = str(date_val)
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    except:
                        date_obj = datetime.now()
                        date_str = date_obj.strftime("%Y-%m-%d")
                    
                year = date_obj.year
                month = date_obj.month
                day = date_obj.day
                
                if start_day > 1:
                    if day >= start_day:
                        month += 1
                        if month > 12:
                            month = 1
                            year += 1
                    cycle_label = f"{year}-{month:02d}"
                else:
                    cycle_label = f"{year}-{month:02d}"
                    
                cursor.execute("""
                    INSERT INTO transactions (timestamp, merchant, amount, category, billing_cycle, account, expense_category)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, merchant, amount, category, cycle_label, account, expense_category))
                
            conn.commit()
            conn.close()
            
            # Reset editor state and trigger reload
            st.session_state.editor_key += 1
            st.success("✅ Changes saved successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Failed to save changes: {e}")
