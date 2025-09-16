import os
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv
import joblib
import time

# === SETUP ===
load_dotenv()
API_KEY = os.getenv("Coingecko_Api_Key")
headers = {"x-cg-pro-api-key": API_KEY}

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Helper: save/load cache
def load_cache(filename, max_age=600):  # 600s = 10 minutes
    path = os.path.join(CACHE_DIR, filename)
    if os.path.exists(path):
        saved_time, data = joblib.load(path)
        if time.time() - saved_time < max_age:
            return data
    return None

def save_cache(filename, data):
    path = os.path.join(CACHE_DIR, filename)
    joblib.dump((time.time(), data), path)


# === FUNCTION 1: Gainers/Losers Data ===
def df_all_durations(durations=["1h", "24h", "7d"], top_coins=1000):
    cache_key = f"gainers_losers_{top_coins}.pkl"
    cached_data = load_cache(cache_key)

    if cached_data is not None:
        return cached_data

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

    final_df = pd.concat(all_data, ignore_index=True)
    save_cache(cache_key, final_df)
    return final_df


# === FUNCTION 2: Search Token Data ===
def get_token_data(token_id):
    cache_key = f"token_{token_id}.pkl"
    cached_data = load_cache(cache_key)

    if cached_data is not None:
        return cached_data

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
    df = pd.DataFrame(data)

    save_cache(cache_key, df)
    return df


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

    st.sidebar.markdown("## 🎛️ Filters (Gainers/Losers)")
    duration = st.sidebar.selectbox("⏳ Select Duration", ["1h", "24h", "7d"])
    coin_type = st.sidebar.radio("📈 Select Type", ["gainer", "loser"], horizontal=True)
    top_n = st.sidebar.slider("🔝 Number of Coins to Display", 5, 20, 10)

    filtered_df = df[(df["duration"] == duration) & (df["type"] == coin_type)]
    st.subheader(f"Top {coin_type.capitalize()}s ({duration})")
    st.dataframe(filtered_df, use_container_width=True)

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
        st.plotly_chart(fig, use_container_width=True)


# === Tab 2: Token Search ===
with tab2:
    st.subheader("🔍 Search Any Token")
    tokens_df = get_all_tokens()

    query = st.text_input("Type a token name or symbol (e.g. Bitcoin, ETH, Solana):", "Bitcoin")
    if query:
        matches = tokens_df[tokens_df["search_name"].str.contains(query, case=False, na=False)]
        if not matches.empty:
            token_choice = st.selectbox("Select a token:", matches["search_name"])
            token_id = matches[matches["search_name"] == token_choice]["id"].iloc[0]

            token_df = get_token_data(token_id)
            if not token_df.empty:
                st.write("### Token Market Data")
                st.dataframe(token_df[[  
                    "id", "symbol", "current_price", "market_cap",
                    "total_volume", "price_change_percentage_1h_in_currency",
                    "price_change_percentage_24h_in_currency",
                    "price_change_percentage_7d_in_currency"
                ]])