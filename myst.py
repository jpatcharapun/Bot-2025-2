import streamlit as st
import threading
import time

# บอทที่เรามี
from short import scalping_bot , get_market_ticker  # นำเข้าบอท Python เดิม (สมมุติชื่อไฟล์ st.py)

# สถานะบอท
bot_running = False


def start_bot():
    """ฟังก์ชันรันบอทใน Thread แยก"""
    global bot_running
    bot_running = True
    st.info("Bot started...")
    scalping_bot()  # รันฟังก์ชันบอทของคุณ


def stop_bot():
    """หยุดการทำงานบอท"""
    global bot_running
    bot_running = False
    st.warning("Bot stopped.")


# สร้าง UI
st.title("Bitkub Scalping Bot Dashboard")

# แสดงสถานะของบอท
if bot_running:
    st.success("Bot is currently running.")
else:
    st.error("Bot is not running.")

# ปุ่มควบคุมบอท
if st.button("Start Bot"):
    if not bot_running:
        threading.Thread(target=start_bot).start()

if st.button("Stop Bot"):
    if bot_running:
        stop_bot()

# Monitor ราคา
st.header("Market Data")
ticker = get_market_ticker("BTC_THB")  # ดึงราคาปัจจุบัน
if ticker:
    st.metric(label="BTC/THB Price", value=f"{ticker.get('last')} THB")
else:
    st.error("Unable to fetch market data.")
