import os
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv

# Load API key
load_dotenv()
API_KEY = os.getenv("Coingecko_Api_Key")
headers = {"x-cg-pro-api-key": API_KEY}


# === FUNCTION 1: Gainers/Losers Data ===
def df_all_durations(durations=["1h", "24h", "7d"], top_coins=1000):
    url = "https://pro-api.coingecko.com/api/v3/coins/top_gainers_losers"
    all_data = []
    for duration in durations:
        params = {"duration": duration, "vs_currency": "usd", "top_coins": top_coins}
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        if isinstance(data, dict) and "top_gainers" in data and "top_losers" in data:
            gainers_df = pd.DataFrame(data["top_gainers"])
            gainers_df["type"] = "gainer"
            gainers_df["duration"] = duration
            losers_df = pd.DataFrame(data["top_losers"])
            losers_df["type"] = "loser"
            losers_df["duration"] = duration
            all_data.append(gainers_df)
            all_data.append(losers_df)
        else:
            raise ValueError(f"Unexpected response format for {duration}: {data}")
    return pd.concat(all_data, ignore_index=True)


# === FUNCTION 2: Search Token Data ===
def get_token_data(token_id):
    url = "https://pro-api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": token_id,
        "order": "market_cap_desc",
        "sparkline": False,
        "price_change_percentage": "1h,24h,7d"
    }
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    return pd.DataFrame(data)


# === FUNCTION 3: Get all tokens for autocomplete ===
@st.cache_data
def get_all_tokens():
    url = "https://pro-api.coingecko.com/api/v3/coins/list"
    response = requests.get(url, headers=headers)
    data = response.json()
    tokens_df = pd.DataFrame(data)
    tokens_df["search_name"] = tokens_df["name"] + " (" + tokens_df["symbol"].str.upper() + ")"
    return tokens_df


# === STREAMLIT APP ===
st.set_page_config(page_title="Crypto Dashboard", layout="wide")

st.title("📊 Crypto Dashboard")
st.markdown("Track **Top Gainers/Losers** and **Any Token** from CoinGecko.")

# Tabs
tab1, tab2 = st.tabs(["🔥 Top Gainers & Losers", "🔍 Token Search"])


# === Tab 1: Gainers & Losers ===
with tab1:
    df = df_all_durations()

    # Sidebar styling with HTML/CSS
    st.sidebar.markdown(
        """
        <style>
        .sidebar .sidebar-content {
            background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
            padding: 15px;
            border-radius: 12px;
            color: #f8f9fa;
        }
        .sidebar .sidebar-content h2, .sidebar .sidebar-content h3 {
            color: #f8f9fa;
            text-align: center;
        }
        .sidebar .sidebar-content label {
            color: #dcdcdc;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Sidebar header
    st.sidebar.markdown("## 🎛️ Filters (Gainers/Losers)")

    # Sidebar widgets
    duration = st.sidebar.selectbox("⏳ Select Duration", ["1h", "24h", "7d"])
    coin_type = st.sidebar.radio("📈 Select Type", ["gainer", "loser"], horizontal=True)
    top_n = st.sidebar.slider("🔝 Number of Coins to Display", 5, 20, 10)

    # Main display
    filtered_df = df[(df["duration"] == duration) & (df["type"] == coin_type)]
    st.subheader(f"Top {coin_type.capitalize()}s ({duration})")
    st.dataframe(filtered_df, use_container_width=True)

    # Chart
    change_col = {"1h": "usd_1h_change", "24h": "usd_24h_change", "7d": "usd_7d_change"}[duration]
    if change_col in filtered_df.columns:
        top_coins = filtered_df.nlargest(top_n, change_col)
        fig = px.bar(
            top_coins,
            x="name",
            y=change_col,
            color="name",
            title=f"Top {top_n} {coin_type.capitalize()}s by {duration} Change"
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            title_font=dict(size=20, color="white")
        )
        st.plotly_chart(fig, use_container_width=True)


# === Tab 2: Token Search with Type-Ahead ===
with tab2:
    st.subheader("🔍 Search Any Token")
    tokens_df = get_all_tokens()

    # User types a token name or symbol
    query = st.text_input(
        "Type a token name or symbol (e.g. Bitcoin, ETH, Solana):",
        "Bitcoin",
        key="token_search_input"
    )

    # Filter matches
    if query:
        matches = tokens_df[tokens_df["search_name"].str.contains(query, case=False, na=False)]

        if not matches.empty:
            # If multiple matches, show as a selectbox
            token_choice = st.selectbox("Select a token:", matches["search_name"], key="token_search_select")
            token_id = matches[matches["search_name"] == token_choice]["id"].iloc[0]

            # Fetch token data
            token_df = get_token_data(token_id)

            if not token_df.empty:
                st.write("### Token Market Data")
                st.dataframe(token_df[[  
                    "id", "symbol", "current_price", "market_cap",
                    "total_volume", "price_change_percentage_1h_in_currency",
                    "price_change_percentage_24h_in_currency",
                    "price_change_percentage_7d_in_currency"
                ]])

                # # ✅ Check if it's a top gainer/loser
                # df_all = df_all_durations()
                # token_check = df_all[df_all["id"] == token_id]

                # for d in ["1h", "24h", "7d"]:
                #     row = token_check[token_check["duration"] == d]
                #     if not row.empty:
                #         status = row.iloc[0]["type"]
                #         st.success(f"✅ {token_id.capitalize()} is a **Top {status}** in the last {d}")
                #     else:
                #         st.info(
                #             f"ℹ️ {token_id.capitalize()} is NOT among the top gainers/losers for {d}, "
                #             f"but its price change is {token_df[f'price_change_percentage_{d}_in_currency'].iloc[0]:.2f}%."
                #         )

                # === Bar chart for price changes ===
                price_changes = {
                    "1h": token_df["price_change_percentage_1h_in_currency"].iloc[0],
                    "24h": token_df["price_change_percentage_24h_in_currency"].iloc[0],
                    "7d": token_df["price_change_percentage_7d_in_currency"].iloc[0],
                }

                price_df = pd.DataFrame(
                    {"Duration": list(price_changes.keys()), "Price Change (%)": list(price_changes.values())}
                )

                fig3 = px.bar(
                    price_df,
                    x="Duration",
                    y="Price Change (%)",
                    color="Duration",
                    title=f"{token_id.capitalize()} Price Change (%) Over Different Durations",
                    text="Price Change (%)"
                )
                fig3.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
                fig3.update_layout(yaxis_title="Price Change (%)", xaxis_title="Duration")

                st.plotly_chart(fig3, use_container_width=True)




    