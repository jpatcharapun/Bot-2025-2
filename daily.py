import hmac
import hashlib
import time
import requests
from dotenv import load_dotenv
import os

# โหลดไฟล์ .env
load_dotenv()

API_KEY = os.getenv("BITKUB_API_KEY")
API_SECRET = os.getenv("BITKUB_API_SECRET")
API_URL = "https://api.bitkub.com"

def sign_payload(payload):
    """สร้าง Signature สำหรับ payload"""
    encoded_payload = str(payload).encode()
    signature = hmac.new(
        API_SECRET.encode(),
        msg=encoded_payload,
        digestmod=hashlib.sha256
    ).hexdigest()
    return signature

def get_server_time():
    """ดึงเวลาจากเซิร์ฟเวอร์ของ Bitkub"""
    response = requests.get(f"{API_URL}/api/servertime")
    return response.json()

def get_market_ticker(symbol="THB_BTC"):
    """ดึงราคาปัจจุบันของตลาด"""
    response = requests.get(f"{API_URL}/api/market/ticker")
    ticker = response.json()
    return ticker.get(symbol)

def place_order(symbol, side, amount, rate):
    """ส่งคำสั่งซื้อ/ขาย"""
    payload = {
        "sym": symbol,
        "amt": amount,
        "rat": rate,
        "typ": "limit",  # limit หรือ market
        "ts": int(time.time())
    }
    payload["sig"] = sign_payload(payload)
    headers = {"X-BTK-APIKEY": API_KEY}
    endpoint = f"{API_URL}/api/market/place-bid" if side == "buy" else f"{API_URL}/api/market/place-ask"
    response = requests.post(endpoint, json=payload, headers=headers)
    return response.json()

def calculate_net_profit(cost_price, sell_price, amount, fee_percent=0.25):
    """
    คำนวณกำไรสุทธิหลังหักค่าธรรมเนียม
    :param cost_price: ราคาที่ซื้อ (บาทต่อหน่วย)
    :param sell_price: ราคาที่ขาย (บาทต่อหน่วย)
    :param amount: จำนวนที่ซื้อ/ขาย
    :param fee_percent: ค่าธรรมเนียม (% ต่อธุรกรรม)
    :return: กำไรสุทธิ (บาท)
    """
    fee_rate = fee_percent / 100

    # ต้นทุนรวมค่าธรรมเนียม
    total_cost = (cost_price * amount) * (1 + fee_rate)

    # รายรับรวมค่าธรรมเนียม
    total_revenue = (sell_price * amount) * (1 - fee_rate)

    # กำไรสุทธิ
    net_profit = total_revenue - total_cost

    return net_profit

def daily_trade_bot():
    """บอทซื้อ-ขายรายวัน"""
    symbol = "THB_BTC"
    budget = 260  # งบประมาณในบาท
    profit_percent = 10  # เป้าหมายกำไร (%)
    cut_loss_percent = 5  # ระดับ Cut Loss (%)
    fee_percent = 0.25  # ค่าธรรมเนียม (%)

    # ดึงราคาตลาด
    ticker = get_market_ticker(symbol)
    if ticker:
        current_price = ticker["last"]
        print(f"ราคาปัจจุบันของ {symbol}: {current_price} THB")

        # ซื้อเมื่อราคาลดลง 2%
        target_buy_price = current_price * 0.98
        amount_to_buy = budget / target_buy_price

        print(f"ส่งคำสั่งซื้อที่ราคา: {target_buy_price} จำนวน: {amount_to_buy} BTC")
        buy_response = place_order(symbol, "buy", amount_to_buy, target_buy_price)
        print("ผลลัพธ์การซื้อ:", buy_response)

        # ตรวจสอบผลลัพธ์การซื้อ
        if buy_response.get("result") == 1:
            print("ซื้อสำเร็จ!")
            
            # คำนวณราคาขายเป้าหมายและ Cut Loss
            target_sell_price = target_buy_price * (1 + profit_percent / 100)
            cut_loss_price = target_buy_price * (1 - cut_loss_percent / 100)

            print(f"ราคาขายเป้าหมาย: {target_sell_price} THB")
            print(f"ราคาขาย Cut Loss: {cut_loss_price} THB")
            
            # ตรวจสอบราคาปัจจุบันเพื่อขาย
            while True:
                ticker = get_market_ticker(symbol)
                if ticker:
                    current_price = ticker["last"]
                    print(f"ราคาปัจจุบัน: {current_price} THB")

                    # ขายเมื่อได้กำไร
                    if current_price >= target_sell_price:
                        print("ถึงเป้าหมายกำไร! กำลังขาย...")
                        sell_response = place_order(symbol, "sell", amount_to_buy, current_price)
                        print("ผลลัพธ์การขาย:", sell_response)
                        if sell_response.get("result") == 1:
                            profit = calculate_net_profit(target_buy_price, current_price, amount_to_buy, fee_percent)
                            print(f"กำไรสุทธิหลังหักค่าธรรมเนียม: {profit:.2f} บาท")
                        break

                    # ขายเมื่อถึง Cut Loss
                    elif current_price <= cut_loss_price:
                        print("ถึงระดับ Cut Loss! กำลังขาย...")
                        sell_response = place_order(symbol, "sell", amount_to_buy, current_price)
                        print("ผลลัพธ์การขาย:", sell_response)
                        if sell_response.get("result") == 1:
                            loss = calculate_net_profit(target_buy_price, current_price, amount_to_buy, fee_percent)
                            print(f"ขาดทุนสุทธิหลังหักค่าธรรมเนียม: {loss:.2f} บาท")
                        break

                time.sleep(10)  # รอ 10 วินาทีก่อนตรวจสอบราคาอีกครั้ง

if __name__ == "__main__":
    daily_trade_bot()
