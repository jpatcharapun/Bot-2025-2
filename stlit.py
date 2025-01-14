from datetime import datetime
import concurrent.futures
import threading
import asyncio

import sqlite3
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder
import subprocess
from multi_short import get_open_orders , get_wallet_balance , get_market_ticker , get_latest_buy_order
import time
import psutil
import plotly.express as px

import pytz

st.set_page_config(page_title="Bot", page_icon="🦈", layout="wide", initial_sidebar_state="expanded", menu_items=None)

# ตรวจสอบว่ามี session_state สำหรับบอทหรือไม่
if "bot_process" not in st.session_state:
    st.session_state.bot_process = None
    st.session_state.bot_status = "Stopped"

# ฟังก์ชันตรวจสอบสถานะบอท
def check_bot_status():
    if st.session_state.bot_process and psutil.pid_exists(st.session_state.bot_process.pid):
        return "Running"
    return "Stopped"

# ฟังก์ชันเริ่มบอท
def start_bot():
    if st.session_state.bot_process is None or st.session_state.bot_status == "Stopped":
        st.session_state.bot_process = subprocess.Popen(["python", "multi_short.py"])
        # st.session_state.bot_process = run_parallel(symbols, budget, profit_percent, cut_loss_percent, trading_fee_percent)
        st.session_state.bot_status = "Running"
        st.success("Bot started successfully!")
    else:
        st.warning("Bot is already running!")

# ฟังก์ชันหยุดบอท
def stop_bot():
    if st.session_state.bot_process and st.session_state.bot_status == "Running":
        st.session_state.bot_process.terminate()
        st.session_state.bot_process.wait()
        st.session_state.bot_status = "Stopped"
        st.session_state.bot_process = None
        st.success("Bot stopped successfully!")
    else:
        st.warning("Bot is not running!")
        
# ฟังก์ชันรีสตาร์ทบอท
def restart_bot():
    stop_bot()
    start_bot()      

# st.subheader("Trading Bot Configuration")

# # รับค่าพารามิเตอร์จากผู้ใช้
# symbols = st.multiselect("Select Symbols", ["BTC_THB", "ETH_THB", "ADA_THB"])
# budget = st.number_input("Budget (THB)", min_value=10, value=50)
# profit_percent = st.number_input("Profit Percent (%)", min_value=0.1, value=2.0)
# cut_loss_percent = st.number_input("Cut Loss Percent (%)", min_value=0.1, value=3.0)
# trading_fee_percent = st.number_input("Trading Fee Percent (%)", min_value=0.0, value=0.25)

def calculate_overall_profit_loss():
    """
    คำนวณกำไร/ขาดทุนรวมจากตาราง trade_records
    """
    conn = sqlite3.connect("trade_logs.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(profit_loss) FROM trade_records
    """)
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] is not None else 0.0

def get_trade_records():
    """
    ดึงประวัติการบันทึกกำไร/ขาดทุนจาก trade_records
    """
    conn = sqlite3.connect("trade_logs.db")
    df_records = pd.read_sql_query("SELECT * FROM trade_records ORDER BY timestamp DESC", conn)
    conn.close()
    return df_records

def calculate_profit(asset, balance, current_price, buy_price):
    """คำนวณกำไรที่เป็นไปได้"""
    profit = (current_price - buy_price) * balance
    return profit
        
def fetch_assets_with_profit():
    """ดึงข้อมูลทรัพย์สินพร้อมกำไรที่คาดการณ์ (แบบขนาน)"""
    wallet = get_wallet_balance()
    data = []

    def process_asset(asset, balance):
        """ประมวลผลสินทรัพย์แต่ละรายการ"""
        ass = f"{asset}_THB"
        if balance > 0 and asset.upper() != "THB":
            buy_order = get_latest_buy_order(ass)  # ฟังก์ชันที่คุณใช้ดึงราคาซื้อ
            if buy_order:
                buy_price = buy_order.get("buy_price", 0)
                market_data = get_market_ticker(ass)  # ใช้ API ดึงข้อมูลราคาล่าสุด
                current_price = float(market_data.get("last", 0))
                profit = (current_price - buy_price) * balance
                if buy_price > 0:
                    percent_profit = ((current_price - buy_price) / buy_price) * 100
                else:
                    percent_profit = 0

                # คำนวณมูลค่ารวมของสินทรัพย์
                total_value = balance * current_price

                return {
                    "Asset": asset,
                    "Balance": balance,
                    "Buy Price": buy_price,
                    "Current Price": current_price,
                    "Potential Profit": profit,
                    "% Profit": percent_profit,
                    "Total Value (THB)": total_value
                }
        return None

    # ใช้ ThreadPoolExecutor เพื่อรันคำขอแบบขนาน
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(process_asset, asset, balance)
            for asset, balance in wallet.items()
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                data.append(result)

    # คำนวณมูลค่ารวมของพอร์ต
    total_portfolio_value = sum(item["Total Value (THB)"] for item in data if item)

    return pd.DataFrame(data), total_portfolio_value

        
def fetch_open_orders():
    """ดึงข้อมูลคำสั่งซื้อขายค้าง"""
    symbols_to_trade = ["BTC_THB", "ETH_THB", "XRP_THB" , "ADA_THB"]
    all_open_orders = []  # ใช้เก็บคำสั่งซื้อขายค้างทั้งหมด

    for stt in symbols_to_trade:
        open_orders = get_open_orders(stt)
        if open_orders:  # ตรวจสอบว่ามีคำสั่งซื้อขายค้างหรือไม่
            all_open_orders.extend(open_orders)  # เพิ่มรายการลงใน list รวม

    if all_open_orders:
        # แปลงข้อมูลคำสั่งซื้อขายค้างทั้งหมดเป็น DataFrame
        df = pd.DataFrame(all_open_orders)
        return df
    else:
        # ถ้าไม่มีคำสั่งซื้อขายค้าง ให้คืน DataFrame ว่าง
        return pd.DataFrame(columns=["id", "symbol", "side", "price", "amount", "timestamp"])
    
        
# ฟังก์ชันดึงข้อมูลจาก SQLite
def fetch_trading_logs():
    conn = sqlite3.connect("trade_logs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, symbol, message, timestamp FROM logs ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=["ID", "Symbol", "Message", "Timestamp"])

def fetch_order_logs():
    conn = sqlite3.connect("trade_logs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, symbol, order_type, amount, rate, status, timestamp FROM order_logs ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=["ID", "Symbol", "Order Type", "Amount", "Rate", "Status", "Timestamp"])

def fetch_cancel_order_logs():
    conn = sqlite3.connect("trade_logs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, symbol, order_id, side, status, timestamp FROM cancel_order_logs ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=["ID", "Symbol", "Order ID", "Side", "Status", "Timestamp"])

# ฟังก์ชันดึงข้อมูลทรัพย์สินจาก get_wallet_balance
def fetch_assets():
    """ดึงข้อมูลทรัพย์สินที่ถืออยู่"""
    wallet = get_wallet_balance()  # เรียกใช้ฟังก์ชัน get_wallet_balance
    if wallet:
        # แปลงข้อมูลกระเป๋าเงินเป็น DataFrame
        data = [{"Asset": asset, "Balance": balance} for asset, balance in wallet.items()]
        df = pd.DataFrame(data)
        df = df[df["Balance"] > 0]
        return df
    else:
        return pd.DataFrame(columns=["Asset", "Balance"])
    
# ฟังก์ชันแสดงรายการทรัพย์สิน
def display_assets_with_profit():
    st.subheader("Asset and Profit Overview")
    assets_with_profit, total_portfolio_value = fetch_assets_with_profit()
    if assets_with_profit.empty:
        st.write("No found.")
    else:
        st.dataframe(assets_with_profit, use_container_width=True)
        


# ฟังก์ชันแสดงรายการทรัพย์สิน
def display_assets():
    st.subheader("Assets Overview")
    assets_df = fetch_assets()
    if assets_df.empty:
        st.write("No assets found.")
    else:
        st.dataframe(assets_df, use_container_width=True)
        
# ฟังก์ชันสำหรับแสดงตารางข้อมูล
def display_logs(title, df):
    st.subheader(title)
    if df.empty:
        st.write(f"No {title.lower()} available.")
    else:
        st.dataframe(df, use_container_width=True)
        
# เพิ่มส่วนใน Streamlit สำหรับแสดงผลคำสั่งซื้อขายค้าง
def display_open_orders():
    if st.session_state.bot_status == "Stopped":
        return
    st.subheader("Open Orders")
    open_orders_df = fetch_open_orders()
    if open_orders_df.empty:
        st.write("No open orders available.")
    else:
        st.dataframe(open_orders_df, use_container_width=True)
        
def display_asset_chart(asset, key):
    """แสดงกราฟราคาของสินทรัพย์"""
    market_data = get_market_ticker(asset)  # เรียกข้อมูลตลาด
    if market_data:
        # ใช้ข้อมูลราคาจาก market_data แทน price_data
        data = {
            "Timestamp": ["Last Price", "High 24hr", "Low 24hr"],
            "Price": [
                float(market_data.get("last", 0)),
                float(market_data.get("high_24_hr", 0)),
                float(market_data.get("low_24_hr", 0)),
            ]
        }
        df = pd.DataFrame(data)
        
        # สร้างกราฟจากข้อมูลที่จัดรูปแบบแล้ว
        fig = px.bar(df, x="Timestamp", y="Price", title=f"Price Overview for {asset}")
        st.plotly_chart(fig, use_container_width=True, key=key)
    else:
        st.write(f"Unable to fetch price data for {asset}.")

def display_portfolio_chart():
    """แสดงกราฟ Donut Chart สำหรับพอร์ต"""
    assets_with_profit, total_portfolio_value = fetch_assets_with_profit()
    st.subheader(f"Portfolio (Total: {total_portfolio_value:,.2f} THB)")
    if assets_with_profit.empty:
        st.write("No assets found.")
    else:
        # สร้าง Donut Chart
        fig = px.pie(
            assets_with_profit,
            values="Total Value (THB)",
            names="Asset",
            title=f"Portfolio Distribution (Total: {total_portfolio_value:,.2f} THB)",
            hole=0.4  # ทำให้กราฟเป็น Donut
        )
        st.plotly_chart(fig, use_container_width=True)

def display_overall():
    # แสดงประวัติการบันทึกกำไร/ขาดทุน
    st.subheader("Profit/Loss Records")
    df_records = get_trade_records()
    if not df_records.empty:
        st.dataframe(df_records, use_container_width=True)
    else:
        st.write("ยังไม่มีบันทึกกำไร/ขาดทุน")
    # แสดงผลกำไร/ขาดทุนรวม
    st.subheader("Overall Profit/Loss")
    overall_profit_loss = calculate_overall_profit_loss()
    st.write(f"### รวมกำไร/ขาดทุนทั้งหมด: {overall_profit_loss:,.2f} THB")


        
# Streamlit App
# st.title("Trading, Order, and Cancel Order Logs with Drag-and-Drop")
# แสดง UI สำหรับควบคุมบอท
st.title("Bot Control Panel")
refresh_auto = st.checkbox("Auto-refresh Open Orders")
# แสดงสถานะปัจจุบันของบอท
st.session_state.bot_status = check_bot_status()
st.write(f"**Bot Status:** {st.session_state.bot_status}")

col1, col2, col3 , col4  = st.columns(4)

with col1:
    if st.button("Start Bot"):
        start_bot()

with col2:
    if st.button("Stop Bot"):
        stop_bot()

with col3:
    if st.button("Restart Bot"):
        restart_bot()
with col4:
    if st.button("Cancel All Orders"):
        stop_bot()
        subprocess.Popen(["python", "multi_short.py", "--cancel-all"])
        st.success("Command to cancel all orders sent!")
        start_bot()
        

# เพิ่ม placeholder สำหรับรีเฟรชข้อมูล
refresh_placeholder = st.empty()

# symbols = ["BTC_THB", "ETH_THB", "XRP_THB", "ADA_THB"]
# selected_symbol = st.selectbox("Select Symbol", symbols)

  
# รายการ Symbol ที่รองรับ
symbols = {
    "BTC_THB": "BTCTHB",
    "ETH_THB": "ETHTHB",
    "XRP_THB": "XRPTHB",
    "ADA_THB": "ADATHB"
}

# ให้ผู้ใช้เลือก Symbol


# TradingView Widget Template
def tradingview_widget(symbol: str, width: str = "100%", height: int = 500) -> str:
    """
    สร้าง HTML สำหรับ TradingView Widget
    """
    return f"""
    <div class="tradingview-widget-container">
        <div id="tradingview_{symbol}"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
            new TradingView.widget({{
                "width": "{width}",
                "height": {height},
                "symbol": "{symbols[symbol]}",
                "interval": "30",
                "timezone": "Asia/Bangkok",
                "theme": "light",
                "style": "1",
                "locale": "th",
                "toolbar_bg": "#f1f3f6",
                "enable_publishing": false,
                "allow_symbol_change": true,
                "container_id": "tradingview_{symbol}"
            }});
        </script>
    </div>
    """
def display_market_overview():
    st.components.v1.html("""
    <div class="tradingview-widget-container">
        <div class="tradingview-widget-container__widget"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js">
        {
            "colorTheme": "light",
            "dateRange": "12M",
            "showChart": true,
            "locale": "th",
            "largeChartUrl": "",
            "isTransparent": false,
            "width": "100%",
            "height": "400",
            "plotLineColorGrowing": "rgba(41, 98, 255, 1)",
            "plotLineColorFalling": "rgba(41, 98, 255, 1)",
            "gridLineColor": "rgba(240, 243, 250, 1)",
            "scaleFontColor": "rgba(120, 123, 134, 1)",
            "belowLineFillColorGrowing": "rgba(41, 98, 255, 0.12)",
            "belowLineFillColorFalling": "rgba(41, 98, 255, 0.12)",
            "symbolActiveColor": "rgba(41, 98, 255, 0.12)",
            "tabs": [
                {
                    "title": "Cryptocurrencies",
                    "symbols": [
                        {"s": "BTCTHB"},
                        {"s": "ETHTHB"},
                        {"s": "XRPTHB"},
                        {"s": "DOGETHB"},
                        {"s": "KUBTHB"},
                        {"s": "USDTTHB"},
                        {"s": "ADATHB"}
                    ],
                    "originalTitle": "Cryptocurrencies"
                }
            ]
        }
        </script>
    </div>
    """, height=400)
    
# แสดงผล Widget

def autorefresh():
    """ฟังก์ชันสำหรับดึงข้อมูลใหม่และแสดงผล"""
    with refresh_placeholder.container():
        # เรียกใช้ฟังก์ชันใน Streamlit
        
        display_overall()
       
        display_assets_with_profit()
        # selected_symbol = st.selectbox("เลือก Symbol", list(symbols.keys()))
        # st.components.v1.html(tradingview_widget(selected_symbol), height=600)
        display_market_overview()

        display_portfolio_chart()
        # ล้างข้อมูลเก่าก่อนแสดงใหม่
        st.subheader("Real-Time Logs")
        #  # แสดงกราฟราคาสำหรับ Symbol ที่เลือก
        # timestamp = int(time.time() * 1000)  # ใช้เวลาเป็น key เพื่อหลีกเลี่ยงซ้ำ
        # display_asset_chart(selected_symbol, key=f"chart_{selected_symbol}_{timestamp}")
        # แสดงข้อมูล Trading Logs
        logs_df = fetch_trading_logs()
        display_logs("Trading Logs", logs_df)
        
        # แสดงข้อมูล Order Logs
        order_logs_df = fetch_order_logs()
        display_logs("Order Logs", order_logs_df)
        
        # แสดงข้อมูล Cancel Order Logs
        cancel_order_logs_df = fetch_cancel_order_logs()
        display_logs("Cancel Order Logs", cancel_order_logs_df)
        
        # แสดงข้อมูล Open Orders
        display_open_orders()
        
        display_assets()

    # เพิ่มการแสดงผลคำสั่งซื้อขายค้างใน UI
if st.button("Refresh"):
    autorefresh()
  
def restart_bot_if_running():
    if st.session_state.bot_status == "Running":
        restart_bot()

async def auto_refresh():
    while refresh_auto:
        autorefresh()
        await asyncio.sleep(300)  # รอ 60 วินาทีต่อการ Refresh
        if st.session_state.bot_status == "Running":
            restart_bot()
            
# เรียกใช้งาน Auto Refresh แบบ Async
if refresh_auto:
    asyncio.run(auto_refresh())
    