import threading
from concurrent.futures import ThreadPoolExecutor
import hmac
import hashlib
import time
import requests
from dotenv import load_dotenv
import os
from decimal import Decimal

# โหลดไฟล์ .env
load_dotenv()

API_KEY = os.getenv("BITKUB_API_KEY")
API_SECRET = os.getenv("BITKUB_API_SECRET")
API_URL = "https://api.bitkub.com"

def create_signature(api_secret, method, path, query, payload):
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
        return response.json()
    else:
        print(f"HTTP Error: {response.status_code}, {response.text}")
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

    params = {"sym": symbol, "ts": ts}
    signature = create_signature_params(API_SECRET, "GET", "/api/v3/market/my-open-orders", params, {"ts": ts})

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
        else:
            print(f"HTTP Error: {response.status_code}, {response.text}")


def scalping_bot(symbol="BTC_THB", budget=250, profit_percent=1, cut_loss_percent=2, trading_fee_percent=0.25):
    """บอท Scalping พร้อม Take Profit และ Cut Loss"""
    trading_fee_rate = trading_fee_percent / 100  # แปลงค่าธรรมเนียมเป็นอัตราส่วน

    # ตรวจสอบยอดคงเหลือ
    wallet = get_wallet_balance()
    btc_balance = float(wallet.get("BTC", 0))  # BTC คงเหลือ
    print(f"BTC คงเหลือ: {btc_balance}")

    buy_price = None
    buy_fee = 0  # ตั้งค่าดีฟอลต์

    if btc_balance > 0:
        print("มี BTC อยู่แล้ว กำลังรอขาย...")
        ticker = get_market_ticker(symbol)
        if ticker and "last" in ticker:
            buy_price = float(ticker.get("last"))  # ใช้ราคาล่าสุดเป็นราคาซื้อ (กรณีไม่รู้ราคาจริง)
        else:
            print("ไม่สามารถดึงราคาล่าสุดได้")
            return
    else:
        # ยกเลิกคำสั่งค้าง (ถ้ามี)
        cancel_all_orders(symbol)

        # ดึงราคาล่าสุด
        ticker = get_market_ticker(symbol)
        if not ticker or "last" not in ticker:
            print("ไม่สามารถดึงข้อมูลราคาล่าสุดได้")
            return

        current_price = float(ticker.get("last"))
        print(f"ราคาปัจจุบัน: {current_price:.2f} THB")

        # คำนวณจำนวนที่ต้องการซื้อ
        amount_to_buy = budget / current_price
        buy_fee = amount_to_buy * current_price * trading_fee_rate  # ค่าธรรมเนียมการซื้อ
        print(f"กำลังซื้อ {amount_to_buy:.6f} BTC ที่ราคา {current_price:.2f} THB (ค่าธรรมเนียม: {buy_fee:.2f} THB)")
        buy_response = place_order(symbol, "buy", budget, current_price)
        print("ผลลัพธ์การซื้อ:", buy_response)

        if buy_response and buy_response.get("error") == 0:
            buy_price = current_price
            print(f"ซื้อสำเร็จที่ราคา {buy_price:.2f} THB")
        else:
            print("ไม่สามารถซื้อ BTC ได้")
            return

    # ตรวจสอบว่ามีค่า buy_price หรือไม่
    if buy_price is None:
        print("ไม่สามารถกำหนดราคาซื้อ (buy_price) ได้")
        return

    # คำนวณเป้าหมาย Take Profit และ Cut Loss
    target_sell_price = buy_price * (1 + profit_percent / 100)
    cut_loss_price = buy_price * (1 - cut_loss_percent / 100)
    print(f"เป้าหมายขายกำไร: {target_sell_price:.2f} THB")
    print(f"เป้าหมาย Cut Loss: {cut_loss_price:.2f} THB")

    # คำนวณกำไร/ขาดทุน
    amount_to_sell = btc_balance if btc_balance > 0 else amount_to_buy
    sell_fee_profit = amount_to_sell * target_sell_price * trading_fee_rate
    sell_fee_loss = amount_to_sell * cut_loss_price * trading_fee_rate
    net_profit = (amount_to_sell * target_sell_price) - (amount_to_sell * buy_price) - buy_fee - sell_fee_profit
    net_loss = (amount_to_sell * buy_price) + buy_fee + sell_fee_loss - (amount_to_sell * cut_loss_price)

    print(f"กำไรสุทธิ (ถ้าขายที่เป้าหมายกำไร): {net_profit:.2f} THB")
    print(f"ขาดทุนสุทธิ (ถ้าขายที่ Cut Loss): {net_loss:.2f} THB")

    # รอขาย
    while True:
        ticker = get_market_ticker(symbol)
        if ticker and isinstance(ticker, dict):
            current_price = float(ticker.get("last"))
            print(f"ราคาปัจจุบัน: {current_price:.2f} THB")

            # ขายเมื่อถึงเป้าหมาย Take Profit
            if current_price >= target_sell_price:
                print("ถึงเป้าหมายกำไร! กำลังขาย...")
                sell_response = place_order(symbol, "sell", amount_to_sell, current_price)
                print("ผลลัพธ์การขาย:", sell_response)
                break

            # ขายเมื่อถึงเป้าหมาย Cut Loss
            elif current_price <= cut_loss_price:
                print("ถึงเป้าหมาย Cut Loss! กำลังขาย...")
                sell_response = place_order(symbol, "sell", amount_to_sell, current_price)
                print("ผลลัพธ์การขาย:", sell_response)
                break

        time.sleep(10)  # ตรวจสอบราคาใหม่ทุก 10 วินาที


if __name__ == "__main__":
    while True:
        scalping_bot()
        time.sleep(60)  # รอ 1 นาทีเพื่อเริ่มรอบใหม่
        