import sys
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
