from datetime import datetime
import concurrent.futures
import threading
import asyncio

import sqlite3
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder
import subprocess
# from multi_short import get_open_orders , get_wallet_balance , get_market_ticker , get_latest_buy_order
import time
import psutil
import plotly.express as px

import pytz
import sys
import numpy as np
import threading
from concurrent.futures import ThreadPoolExecutor
import hmac
import hashlib
import time
import requests
from dotenv import load_dotenv
import os
from decimal import Decimal
import sqlite3
from datetime import datetime
import asyncio

# โหลดไฟล์ .env
load_dotenv()

API_KEY = os.getenv("BITKUB_API_KEY")
API_SECRET = os.getenv("BITKUB_API_SECRET")
API_URL = "https://api.bitkub.com"

def create_signature(api_secret, method, path, query, payload = None):
    """สร้าง Signature สำหรับ Bitkub API V3"""
    # รวมข้อมูลที่ใช้ในการสร้าง Signature
    data = f"{payload['ts']}{method}{path}"
    if query:
        data += f"?{query}"
    if payload:
        data += str(payload).replace("'", '"')  # JSON payload ต้องเป็นแบบ double quotes
    
    # เข้ารหัส HMAC SHA-256
    signature = hmac.new(api_secret.encode(), msg=data.encode(), digestmod=hashlib.sha256).hexdigest()
    return signature

def create_signature_params(api_secret, method, path, query, payload):
    """สร้าง Signature สำหรับ Bitkub API V3"""
    # Query string (แปลง Query Parameters ให้เป็น string)
    query_string = "&".join([f"{key}={value}" for key, value in query.items()]) if query else ""

    # สร้างข้อมูลที่ใช้ใน Signature
    data = f"{payload['ts']}{method}{path}"
    if query_string:
        data += f"?{query_string}"

    # เข้ารหัส HMAC SHA-256
    signature = hmac.new(api_secret.encode(), msg=data.encode(), digestmod=hashlib.sha256).hexdigest()
    return signature

def get_server_time():
    """ดึงเวลาจากเซิร์ฟเวอร์ของ Bitkub"""
    response = requests.get(f"{API_URL}/api/v3/servertime")
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None

def get_market_ticker(symbol="BTC_THB"):
    """ดึงราคาล่าสุดของตลาด"""
    endpoint = f"{API_URL}/api/v3/market/ticker"
    params = {"sym": symbol}
    response = requests.get(endpoint, params=params)
    if response.status_code == 200:
        data = response.json()  # ข้อมูลที่ส่งกลับมา
        if isinstance(data, list):  # ตรวจสอบว่าข้อมูลเป็น list
            for item in data:
                if item.get("symbol") == symbol:  # ตรวจสอบว่าตรงกับ symbol ที่ต้องการ
                    return item
            print(f"Symbol {symbol} ไม่พบในผลลัพธ์")
            return None
        else:
            print("รูปแบบข้อมูลไม่รองรับ:", type(data))
            return None
    else:
        print(f"HTTP Error: {response.status_code}, {response.text}")
        return None

def place_order(symbol, side, amount, rate):
    """ส่งคำสั่งซื้อหรือขาย"""
    # ดึงเวลาจากเซิร์ฟเวอร์ (มิลลิวินาที)
    ts = get_server_time()
    if not ts:
        print("ไม่สามารถดึงเวลาจากเซิร์ฟเวอร์ได้")
        return None
    amount = float(Decimal(amount).normalize())

    # JSON Payload
    payload = {
        "sym": symbol,
        "amt": amount,
        "rat": rate,
        "typ": "limit",
        "ts": ts
    }

    # กำหนด Endpoint และ Path
    path = "/api/v3/market/place-bid" if side == "buy" else "/api/v3/market/place-ask"
    endpoint = f"{API_URL}{path}"

    # สร้าง Signature
    method = "POST"
    query = ""  # ไม่มี Query Parameters
    signature = create_signature(API_SECRET, method, path, query, payload)

    # ใส่ Header
    headers = {
        "X-BTK-APIKEY": API_KEY,
        "X-BTK-TIMESTAMP": str(ts),
        "X-BTK-SIGN": signature,
        "Content-Type": "application/json"
    }

    # ส่งคำสั่งซื้อหรือขาย
    response = requests.post(endpoint, json=payload, headers=headers)
    if response.status_code == 200:
        save_order_log(symbol,side, amount, rate, "success")
        return response.json()
    else:
        print(f"HTTP Error: {response.status_code}, {response.text}")
        save_order_log(symbol,side, amount, rate, f"failed : HTTP Error: {response.status_code}, {response.text}")
        return None


def get_trade_limits():
    """ดึงข้อมูลค่าขั้นต่ำในการซื้อ/ขาย"""
    endpoint = f"{API_URL}/api/v3/user/limits"
    ts = get_server_time()
    if not ts:
        print("ไม่สามารถดึงเวลาจากเซิร์ฟเวอร์ได้")
        return None

    payload = {"ts": ts}
    payload_string = str(payload).replace("'", '"')  # JSON payload ใช้ double quotes
    signature = create_signature(API_SECRET, "POST", "/api/v3/user/limits", "", payload)

    headers = {
        "X-BTK-APIKEY": API_KEY,
        "X-BTK-TIMESTAMP": str(ts),
        "X-BTK-SIGN": signature,
        "Content-Type": "application/json"
    }

    response = requests.post(endpoint, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"HTTP Error: {response.status_code}, {response.text}")
        return None

def get_wallet_balance():
    """ดึงยอดคงเหลือในกระเป๋า"""
    ts = get_server_time()
    if not ts:
        print("ไม่สามารถดึงเวลาจากเซิร์ฟเวอร์ได้")
        return None

    payload = {"ts": ts}
    signature = create_signature(API_SECRET, "POST", "/api/v3/market/wallet", "", payload)

    headers = {
        "X-BTK-APIKEY": API_KEY,
        "X-BTK-TIMESTAMP": str(ts),
        "X-BTK-SIGN": signature,
        "Content-Type": "application/json"
    }

    response = requests.post(f"{API_URL}/api/v3/market/wallet", json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("result", {})
    else:
        print(f"HTTP Error: {response.status_code}, {response.text}")
        return None

def get_open_orders(symbol):
    """ดึงรายการคำสั่งค้าง"""
    ts = get_server_time()
    if not ts:
        print("ไม่สามารถดึงเวลาจากเซิร์ฟเวอร์ได้")
        return None
    if symbol is None:
        params = {"ts":ts}
    else:
        params = {"sym": symbol, "ts": ts}
    signature = create_signature_params(API_SECRET, "GET", "/api/v3/market/my-open-orders", params, params)

    headers = {
        "X-BTK-APIKEY": API_KEY,
        "X-BTK-TIMESTAMP": str(ts),
        "X-BTK-SIGN": signature
    }

    response = requests.get(f"{API_URL}/api/v3/market/my-open-orders", params=params, headers=headers)

    if response.status_code == 200:
        return response.json().get("result", [])
    else:
        print(f"HTTP Error: {response.status_code}, {response.text}")
        return None

def cancel_all_orders(symbol):
    """ยกเลิกคำสั่งซื้อ/ขายที่ยังค้าง"""
    open_orders = get_open_orders(symbol)
    if not open_orders:
        print("ไม่มีคำสั่งค้าง")
        return

    for order in open_orders:
        if order is None:
            continue
        order_id = order.get("id")
        order_side = order.get("side")  # เปลี่ยนจาก "sd" เป็น "side"
        ts = get_server_time()
        if not ts:
            print("ไม่สามารถดึงเวลาจากเซิร์ฟเวอร์ได้")
            return

        # สร้าง payload
        payload = {"sym": symbol, "id": order_id, "sd": order_side, "ts": ts}
        # สร้าง Signature
        signature = create_signature(API_SECRET, "POST", "/api/v3/market/cancel-order", {}, payload)

        # Headers
        headers = {
            "X-BTK-APIKEY": API_KEY,
            "X-BTK-TIMESTAMP": str(ts),
            "X-BTK-SIGN": signature,
            "Content-Type": "application/json"
        }

        # ส่งคำขอยกเลิกคำสั่ง
        response = requests.post(f"{API_URL}/api/v3/market/cancel-order", json=payload, headers=headers)
        if response.status_code == 200:
            print(f"คำสั่ง {order_id} ถูกยกเลิกสำเร็จ")
            save_cancel_order_log(symbol, order_id , order_side, "success")
        else:
            print(f"HTTP Error: {response.status_code}, {response.text}")
            save_cancel_order_log(symbol, order_id , order_side, "failed")
            

def get_latest_buy_order(symbol):
    """ดึงคำสั่งซื้อ (buy) ล่าสุดที่ดำเนินการ"""
    ts = get_server_time()
    if not ts:
        print(f"{symbol}: ไม่สามารถดึงเวลาจากเซิร์ฟเวอร์ได้")
        return None

    # Query Parameters
    params = {"sym": symbol, "lmt": 10, "ts": ts}
    
    # สร้าง Signature
    signature = create_signature_params(API_SECRET, "GET", "/api/v3/market/my-order-history", params , {"ts": ts})

    # Headers
    headers = {
        "X-BTK-APIKEY": API_KEY,
        "X-BTK-TIMESTAMP": str(ts),
        "X-BTK-SIGN": signature
    }

    # ส่งคำขอ GET
    response = requests.get(f"{API_URL}/api/v3/market/my-order-history", params=params, headers=headers)
    if response.status_code == 200:
        orders = response.json().get("result", [])
        if orders:
            # กรองคำสั่งซื้อที่มี side == "buy" และจัดเรียงตาม ts (timestamp) มากที่สุด
            buy_orders = sorted(
                [order for order in orders if order.get("side") == "buy"],
                key=lambda x: x.get("ts", 0),
                reverse=True
            )
            if buy_orders:
                latest_buy_order = buy_orders[0]
                return {
                    "buy_price": float(latest_buy_order["rate"]),
                    "amount": float(latest_buy_order["amount"]),
                    "fee": float(latest_buy_order["fee"]),
                    "timestamp": latest_buy_order["ts"]
                }
            else:
                # print(f"{symbol}: ไม่มีคำสั่งซื้อในประวัติ")
                return {
                    "buy_price": 0,  # กำหนดค่าเริ่มต้นหากไม่พบข้อมูล
                    "amount": 0,
                    "fee": 0,
                    "timestamp": 0
                }
        else:
            # print(f"{symbol}: ไม่พบข้อมูลคำสั่งซื้อ")
            return {
                "buy_price": 0,  # กำหนดค่าเริ่มต้นหากไม่พบข้อมูล
                "amount": 0,
                "fee": 0,
                "timestamp": 0
            }
    else:
        print(f"{symbol}: HTTP Error: {response.status_code}, {response.text}")
        return {
            "buy_price": 0,
            "amount": 0,
            "fee": 0,
            "timestamp": 0
        }

# ฟังก์ชันสำหรับสร้างฐานข้อมูลและตาราง Log
def initialize_database():
    conn = sqlite3.connect("trade_logs.db")  # ชื่อไฟล์ฐานข้อมูล
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            order_type TEXT,
            profit_loss REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# ฟังก์ชันสำหรับบันทึกข้อความ Log
def save_log(symbol, message):
    print(message)
    conn = sqlite3.connect("trade_logs.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO logs (symbol, message) VALUES (?, ?)", (symbol, message))
    conn.commit()
    conn.close()
    
def save_order_log(symbol, order_type, amount, rate, status):
    """บันทึก log การวางคำสั่ง Order ลง SQLite"""
    conn = sqlite3.connect("trade_logs.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            order_type TEXT,
            amount REAL,
            rate REAL,
            status TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(
        "INSERT INTO order_logs (symbol, order_type, amount, rate, status) VALUES (?, ?, ?, ?, ?)",
        (symbol, order_type, amount, rate, status)
    )
    conn.commit()
    conn.close()
    
def save_cancel_order_log(symbol, order_id, side, status):
    """บันทึก log การยกเลิกคำสั่งลง SQLite"""
    conn = sqlite3.connect("trade_logs.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cancel_order_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            order_id TEXT,
            side TEXT,
            status TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(
        "INSERT INTO cancel_order_logs (symbol, order_id, side, status) VALUES (?, ?, ?, ?)",
        (symbol, order_id, side, status)
    )
    conn.commit()
    conn.close()
    
def save_trade_record(symbol, order_type, profit_loss):
    """
    บันทึกข้อมูลกำไร/ขาดทุนลงในตาราง trade_records
    """
    conn = sqlite3.connect("trade_logs.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            order_type TEXT,
            profit_loss REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(
        """
        INSERT INTO trade_records (symbol, order_type, profit_loss)
        VALUES (?, ?, ?)
        """,
        (symbol, order_type, profit_loss)
    )
    conn.commit()
    conn.close()
    
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

def scalping_bot(symbol, budget=100, profit_percent=2, cut_loss_percent=3, trading_fee_percent=0.25 , timetosleep=10 , reloadtime=120):
    """บอท Scalping พร้อม Take Profit และ Cut Loss"""
    trading_fee_rate = trading_fee_percent / 100  # แปลงค่าธรรมเนียมเป็นอัตราส่วน
    
    # ตรวจสอบยอดคงเหลือ
    wallet = get_wallet_balance()
    balance = float(wallet.get(symbol.split("_")[0], 0))  # ดึงยอดคงเหลือของเหรียญที่สนใจ
    # save_log(symbol,f"{symbol}: คงเหลือ {balance}")

    buy_price = None
    buy_fee = 0

    if balance > 0:
        save_log(symbol,f"{symbol}: มีอยู่แล้ว รอขาย...")
        # ดึงข้อมูลราคาซื้อจากคำสั่งซื้อที่ดำเนินการล่าสุด
        latest_buy = get_latest_buy_order(symbol)
        if latest_buy:
            buy_price = latest_buy["buy_price"]
            buy_fee = latest_buy["fee"] # คำนวณค่าธรรมเนียมการซื้อ
            # save_log(symbol,f"{symbol}: ราคาซื้อจากคำสั่งล่าสุด: {buy_price:.2f} THB (ค่าธรรมเนียม: {buy_fee:.2f} THB)")
        else:
            # save_log(symbol,f"{symbol}: ไม่พบข้อมูลราคาซื้อจากคำสั่งล่าสุด")
            return
            # ตรวจสอบว่า buy_price มีค่า
        if buy_price is None:
            # save_log(symbol,f"{symbol}: ไม่สามารถกำหนดราคาซื้อได้")
            return

        # คำนวณเป้าหมาย Take Profit และ Cut Loss
        target_sell_price = buy_price * (1 + profit_percent / 100) / (1 - trading_fee_rate)
        cut_loss_price = buy_price * (1 - cut_loss_percent / 100) / (1 - trading_fee_rate)
        # save_log(symbol,f"{symbol}: เป้าหมายขายกำไร {target_sell_price:.2f} THB (รวมค่าธรรมเนียม)")
        # save_log(symbol,f"{symbol}: เป้าหมาย Cut Loss {cut_loss_price:.2f} THB (รวมค่าธรรมเนียม)")
    else:
        # ยกเลิกคำสั่งค้าง (ถ้ามี)
        cancel_all_orders(symbol)

        # ดึงราคาล่าสุด
        ticker = get_market_ticker(symbol)
        if not ticker or "last" not in ticker:
            save_log(symbol,f"{symbol}: (New) ไม่สามารถดึงราคาล่าสุดได้")
            return

        current_price = float(ticker.get("last"))
        save_log(symbol,f"{symbol}: (New) ราคาปัจจุบัน {current_price:.2f} THB")

        # คำนวณจำนวนที่ต้องการซื้อ
        amount_to_buy = budget / current_price
        buy_fee = amount_to_buy * current_price * trading_fee_rate
        save_log(symbol,f"{symbol}: (New) กำลังซื้อ {amount_to_buy:.6f} ที่ราคา {current_price:.2f} THB ({budget} + ค่าธรรมเนียม {buy_fee:.2f} THB)")
        buy_response = place_order(symbol, "buy", budget, current_price)

        if buy_response and buy_response.get("error") == 0:
            buy_price = current_price
            save_log(symbol,f"{symbol}: (New) ซื้อสำเร็จที่ราคา {buy_price:.2f} THB")
        else:
            save_log(symbol,f"{symbol}: (New) ไม่สามารถซื้อได้")
            return

        # คำนวณเป้าหมาย Take Profit และ Cut Loss
        target_sell_price = buy_price * (1 + profit_percent / 100) / (1 - trading_fee_rate)
        cut_loss_price = buy_price * (1 - cut_loss_percent / 100) / (1 - trading_fee_rate)
        save_log(symbol,f"{symbol}: (New) เป้าหมายขายกำไร {target_sell_price:.2f} THB (รวมค่าธรรมเนียม)")
        save_log(symbol,f"{symbol}: (New) เป้าหมาย Cut Loss {cut_loss_price:.2f} THB (รวมค่าธรรมเนียม)")
    
    
    
    # รอขาย
    while True:
        # save_log(symbol,"-----------------------------------------------------------------------")
        ticker = get_market_ticker(symbol)
        if ticker and "last" in ticker:
            current_price = float(ticker.get("last"))
            # save_log(symbol,f"{symbol}: ราคาปัจจุบัน {current_price:.2f} THB")
            # ตรวจสอบยอดคงเหลือ
            wallet = get_wallet_balance()

            balance = float(wallet.get(symbol.split("_")[0], 0))  # ดึงยอดคงเหลือของเหรียญที่สนใจ
            balancestr = format(balance, '.10f')
            # save_log(symbol,f"{symbol}: คงเหลือ {balancestr}")
            if(balance > 0):
                sell_fee = balance * target_sell_price * trading_fee_rate
                net_profit = (balance * target_sell_price) - (balance * buy_price) - buy_fee - sell_fee
                # save_log(symbol,f"{symbol}: กำไรสุทธิ หาก ขายตรงเป้า({target_sell_price:.2f}): {net_profit:.2f} THB ค่า fee ไปกลับ ")
                
                net_loss = (balance * cut_loss_price) - (balance * buy_price) - buy_fee - sell_fee
                # save_log(symbol,f"{symbol}: ขาดทุนสุทธิหาก ขายตรงเป้า({cut_loss_price:.2f}): {net_loss:.2f} THB ค่า fee ไปกลับ ")
                
                # ขายเมื่อถึงเป้าหมาย Take Profit
                if current_price >= target_sell_price:
                    save_log(symbol,f"{symbol}: ถึงเป้าหมายกำไร! กำลังขาย...")
                    sell_response = place_order(symbol, "sell", balance, current_price)
                    save_log(symbol,f"{symbol}: ผลลัพธ์การขาย: {sell_response}")

                    # คำนวณ Net Profit
                    sell_fee = balance * current_price * trading_fee_rate
                    net_profit = (balance * current_price) - (balance * buy_price) - buy_fee - sell_fee
                    save_log(symbol,f"{symbol}: กำไรสุทธิหลังขาย: {net_profit:.2f} THB")
                    save_trade_record(symbol, "sell", net_profit)
                    break

                # ขายเมื่อถึงเป้าหมาย Cut Loss
                elif current_price <= cut_loss_price:
                    save_log(symbol,f"{symbol}: ถึงเป้าหมาย Cut Loss! กำลังขาย...")
                    sell_response = place_order(symbol, "sell", balance, current_price)
                    save_log(symbol,f"{symbol}: ผลลัพธ์การขาย: {sell_response}")

                    # คำนวณ Net Loss
                    sell_fee = balance * current_price * trading_fee_rate
                    net_loss = (balance * current_price) - (balance * buy_price) - buy_fee - sell_fee
                    save_log(symbol,f"{symbol}: ขาดทุนสุทธิหลังขาย: {net_loss:.2f} THB")
                    save_trade_record(symbol, "sell", net_loss)
                    break
                # save_log(symbol,f"ไม่ซื้อไม่ขาย รอ {timetosleep} วิ โหลดใหม่")
            else:
                save_log(symbol,f"{symbol}: สงสัยยังซื้อไม่สำเร็จ")

        time.sleep(timetosleep)  # ตรวจสอบราคาใหม่ทุก 10 วินาที



def run_parallel(symbols, budget=50, profit_percent=1.5, cut_loss_percent=3, trading_fee_percent=0.25):
    """รัน Scalping Bot แบบ Parallel"""
    timetosleep = 5
    reloadtime = 30
    while True:
        with ThreadPoolExecutor(max_workers=len(symbols)) as executor:
            futures = [
                executor.submit(scalping_bot, symbol, budget, profit_percent, cut_loss_percent, trading_fee_percent , timetosleep , reloadtime)
                for symbol in symbols
            ]
            for future in futures:
                future.result()  # รอให้แต่ละ Task เสร็จสิ้น

        save_log("",f"รอบเสร็จสิ้น รอ {reloadtime} นาทีเพื่อเริ่มรอบใหม่...")
        time.sleep(reloadtime)  # รอ 1 นาทีเพื่อเริ่มรอบใหม่

def run(symbols, budget=50, profit_percent=1.5, cut_loss_percent=3, trading_fee_percent=0.25):
    """รัน Scalping Bot แบบ Parallel"""
    timetosleep = 5
    reloadtime = 30
    while True:
        save_log("","เริ่มรอบใหม่...")
        for symbol in symbols:
            scalping_bot(symbol, budget, profit_percent, cut_loss_percent, trading_fee_percent , timetosleep)

        save_log("",f"รอบเสร็จสิ้น รอ {reloadtime} นาทีเพื่อเริ่มรอบใหม่...")
        time.sleep(reloadtime)  # รอ 1 นาทีเพื่อเริ่มรอบใหม่

def cancel_all_orders_my():
    """ยกเลิกคำสั่งซื้อขายทั้งหมดที่ยังค้าง"""
    open_orders = get_open_orders()
    if not open_orders:
        print("No open orders to cancel.")
        return
    for order in open_orders:
        order_id = order.get("id")
        symbol = order.get("sym")

        if not order_id or not symbol:
            print("Invalid order data:", order)
            continue

        cancel_all_orders(symbol)


    print("All orders processed.")

if __name__ == "__main__":
    if "--cancel-all" in sys.argv:
        cancel_all_orders_my()
    symbols_to_trade = ["BTC_THB", "ETH_THB", "XRP_THB", "ADA_THB"]  # สกุลเงินที่ต้องการเทรด
    initialize_database()
    budget = 55  # ตั้งงบประมาณที่เหมาะสมต่อเหรียญ
    profit_percent = 2.0  # ตั้งเป้าหมายกำไรที่สมดุล
    cut_loss_percent = 4.0  # ตั้งค่าการหยุดขาดทุนเพื่อลดความเสี่ยง
    trading_fee_percent = 0.25  # ค่าธรรมเนียมการเทรดของตลาด
    timetosleep = 6  # เวลารอระหว่างการตรวจสอบ
    reloadtime = 10*60  # เวลารีโหลดบอทรอบใหม่
    # run_parallel(symbols_to_trade)
    run_parallel(symbols_to_trade, budget, profit_percent, cut_loss_percent, trading_fee_percent)


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
    