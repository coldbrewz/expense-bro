import os
import sqlite3
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
                
                /* Radial background gradient */
                .stApp {
                    background: radial-gradient(circle at 50% 10%, #1e3c72 0%, #111a2e 100%) !important;
                    font-family: 'Outfit', sans-serif !important;
                }
                
                /* Login Card container */
                .login-card {
                    max-width: 440px;
                    margin: 60px auto 10px auto;
                    padding: 40px 30px;
                    background: rgba(255, 255, 255, 0.03) !important;
                    border: 1px solid rgba(255, 255, 255, 0.08) !important;
                    border-radius: 24px !important;
                    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6) !important;
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
                    filter: drop-shadow(0 0 15px rgba(0, 198, 255, 0.6));
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
                    background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }
                
                .sub-text {
                    color: #a0aec0;
                    font-size: 0.95rem;
                    margin-bottom: 30px;
                    line-height: 1.5;
                }
                
                /* Custom styling for Streamlit's text input container */
                div[data-baseweb="input"] {
                    background-color: rgba(255, 255, 255, 0.04) !important;
                    border: 1px solid rgba(255, 255, 255, 0.1) !important;
                    border-radius: 12px !important;
                    color: white !important;
                    height: 50px !important;
                }
                
                div[data-baseweb="input"]:focus-within {
                    border-color: #00c6ff !important;
                    box-shadow: 0 0 12px rgba(0, 198, 255, 0.3) !important;
                }
                
                input {
                    color: white !important;
                    text-align: center !important;
                    font-size: 1.1rem !important;
                }
                
                /* Custom styling for Streamlit button */
                button[kind="secondary"] {
                    background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%) !important;
                    color: white !important;
                    border: none !important;
                    border-radius: 12px !important;
                    padding: 12px 24px !important;
                    font-weight: 700 !important;
                    font-size: 1rem !important;
                    width: 100% !important;
                    transition: all 0.3s ease !important;
                    box-shadow: 0 4px 15px rgba(0, 114, 255, 0.4) !important;
                    margin-top: 15px !important;
                    cursor: pointer !important;
                }
                
                button[kind="secondary"]:hover {
                    transform: translateY(-2px) !important;
                    box-shadow: 0 6px 20px rgba(0, 114, 255, 0.6) !important;
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

st.title("📊 Expense Bro Personal Dashboard")
st.markdown("Real-time visual insights for your credit card optimization and budgets.")

if df.empty:
    st.info("No transaction data found. Start logging transactions via your Telegram bot to populate this dashboard.")
    st.stop()

# --- DATA PRE-PROCESSING ---
df['amount'] = df['amount'].astype(float)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['date'] = df['timestamp'].dt.date

# Sidebar filter - Billing Cycle
cycles = sorted(df['billing_cycle'].unique(), reverse=True)
selected_cycle = st.sidebar.selectbox("Select Billing Cycle:", cycles)

# Filter dataframe for selected cycle
cycle_df = df[df['billing_cycle'] == selected_cycle]

# --- RENDER DASHBOARD ---

# Col 1: Permata CC Cashback Tracker
st.header("💳 Permata CC Cashback Optimizer")
cc_df = cycle_df[cycle_df['account'] == 'permata_cc']

online_spend = cc_df[cc_df['category'] == 'ONLINE']['amount'].sum()
offline_spend = cc_df[cc_df['category'] == 'OFFLINE']['amount'].sum()
unmapped_spend = cc_df[cc_df['category'] == 'UNMAPPED']['amount'].sum()
total_cc_spend = online_spend + offline_spend + unmapped_spend

# Display metrics
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Total CC Spend", f"Rp {total_cc_spend:,.0f}".replace(",", "."))
kpi2.metric("Online Spend", f"Rp {online_spend:,.0f}".replace(",", "."), "Max cap: 4jt")
kpi3.metric("Offline Spend", f"Rp {offline_spend:,.0f}".replace(",", "."), "Max cap: 2jt")

gate_delta = 5000000 - total_cc_spend
if gate_delta <= 0:
    kpi4.metric("Cashback Status", "✅ ACTIVE", delta="Target Met")
else:
    kpi4.metric("Cashback Status", "❌ INACTIVE", delta=f"-Rp {gate_delta:,.0f}".replace(",", "."), delta_color="inverse")

# Target vs Current Progress Bar Chart
categories = ['ONLINE (Cap 4jt)', 'OFFLINE (Cap 2jt)', 'TOTAL (Gate 5jt)']
current_values = [online_spend, offline_spend, total_cc_spend]
target_values = [4000000, 2000000, 5000000]

fig_progress = go.Figure(data=[
    go.Bar(name='Current Spend', x=categories, y=current_values, marker_color='#2c3e50'),
    go.Bar(name='Target/Cap Limit', x=categories, y=target_values, marker_color='#bdc3c7', opacity=0.4)
])
fig_progress.update_layout(
    barmode='group',
    title="Spend Progress vs. Cashback Targets",
    yaxis_title="Amount (IDR)",
    height=350,
    margin=dict(t=50, b=30, l=40, r=40)
)
st.plotly_chart(fig_progress, use_container_width=True)

# Warning triggers
if online_spend > 4000000:
    st.warning(f"⚠️ **Online Cap Exceeded:** You spent Rp {online_spend - 4000000:,.0f} over the optimal 4jt online cashback cap.")
if offline_spend > 2000000:
    st.warning(f"⚠️ **Offline Cap Exceeded:** You spent Rp {offline_spend - 2000000:,.0f} over the optimal 2jt offline cashback cap.")


# Col 2: Multi-Account Overview & Budget Categories
st.write("---")
col_acc, col_cat = st.columns(2)

with col_acc:
    st.subheader("💼 Spending by Bank Account")
    acc_spend = cycle_df.groupby('account')['amount'].sum().reset_index()
    acc_spend['formatted_amount'] = acc_spend['amount'].apply(lambda x: f"Rp {x:,.0f}".replace(",", "."))
    
    # Custom colors for accounts
    acc_colors = {
        'permata_cc': '#3498db',
        'bank_saqu': '#e67e22',
        'bca': '#2ecc71',
        'line_bank': '#9b59b6',
        'general': '#95a5a6'
    }
    
    fig_acc = px.pie(
        acc_spend, 
        values='amount', 
        names='account',
        color='account',
        color_discrete_map=acc_colors,
        hole=0.4,
        title="Account Allocation"
    )
    fig_acc.update_layout(height=350, margin=dict(t=50, b=30, l=40, r=40))
    st.plotly_chart(fig_acc, use_container_width=True)

with col_cat:
    st.subheader("📈 Detailed Expense Categories")
    cat_spend = cycle_df.groupby('expense_category')['amount'].sum().reset_index().sort_values(by='amount', ascending=False)
    
    fig_cat = px.bar(
        cat_spend,
        x='amount',
        y='expense_category',
        orientation='h',
        color='expense_category',
        color_discrete_sequence=px.colors.qualitative.Pastel,
        labels={'amount':'Total Spend (IDR)', 'expense_category':'Category'},
        title="Where Your Money Goes"
    )
    fig_cat.update_layout(height=350, showlegend=False, margin=dict(t=50, b=30, l=40, r=40))
    st.plotly_chart(fig_cat, use_container_width=True)


# Data List view
st.write("---")
st.subheader("📋 Transactions List")
show_cols = ['id', 'date', 'merchant', 'amount', 'account', 'expense_category', 'category']
display_df = cycle_df[show_cols].copy()
display_df['amount'] = display_df['amount'].apply(lambda x: f"Rp {x:,.0f}".replace(",", "."))

st.dataframe(
    display_df.sort_values(by='id', ascending=False),
    column_config={
        "id": "ID",
        "date": "Date",
        "merchant": "Merchant",
        "amount": "Amount",
        "account": "Account",
        "expense_category": "Budget Category",
        "category": "CC Category"
    },
    hide_index=True,
    use_container_width=True
)
