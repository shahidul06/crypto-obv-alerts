import ccxt
import pandas as pd
import requests
import os
import time

# --- কনফিগারেশন: এই ভ্যালুগুলো কোডে পরিবর্তন করার প্রয়োজন নেই ---
PUSHBULLET_TOKEN = os.environ.get('PUSHBULLET_TOKEN')
MA_PERIOD = 30 
SYMBOL_PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
TIMEFRAMES = ['5m', '10m', '15m', '30m', '1h']
# -----------------------------------------------------------------

def send_pushbullet_notification(title, body):
    """Pushbullet এর মাধ্যমে নোটিফিকেশন পাঠানো হয়"""
    if not PUSHBULLET_TOKEN:
        print("Pushbullet টোকেন সেট করা নেই। নোটিফিকেশন পাঠানো সম্ভব নয়।")
        return

    url = "https://api.pushbullet.com/v2/pushes"
    headers = {
        "Access-Token": PUSHBULLET_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "type": "note",
        "title": title,
        "body": body
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            print(f"Pushbullet নোটিফিকেশন সফলভাবে পাঠানো হয়েছে: {title}")
        else:
            print(f"Pushbullet ত্রুটি: স্ট্যাটাস কোড {response.status_code}")
    except Exception as e:
        print(f"Pushbullet সংযোগ ত্রুটি: {e}")

def calculate_obv_ma(dataframe):
    """OBV এবং ৩০ পিরিয়ডের Moving Average (MA) গণনা করে"""
    obv = [0] * len(dataframe)
    for i in range(1, len(dataframe)):
        volume = dataframe['volume'].iloc[i]
        close = dataframe['close'].iloc[i]
        prev_close = dataframe['close'].iloc[i-1]

        if close > prev_close:
            obv[i] = obv[i-1] + volume
        elif close < prev_close:
            obv[i] = obv[i-1] - volume
        else:
            obv[i] = obv[i-1]
    
    dataframe['OBV'] = obv
    dataframe['MA_OBV_30'] = dataframe['OBV'].ewm(span=MA_PERIOD, adjust=False).mean()
    
    return dataframe

def check_crossover(df, symbol, timeframe):
    """OBV এবং MA_OBV_30 ক্রসওভার চেক করে নোটিফিকেশন পাঠায়"""
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    alert_title = f"[🎯 ALERT - {symbol} - {timeframe}]"
    alert_body = ""

    # ক্রস আপ (Bullish Crossover) চেক
    if prev['OBV'] < prev['MA_OBV_30'] and last['OBV'] > last['MA_OBV_30']:
        alert_body = f"🚀 Bullish Crossover (ক্রস আপ)!\nবর্তমান OBV: {last['OBV']:.2f}, MA_OBV_30: {last['MA_OBV_30']:.2f}"
        send_pushbullet_notification(alert_title, alert_body)
        return True

    # ক্রস ডাউন (Bearish Crossover) চেক
    elif prev['OBV'] > prev['MA_OBV_30'] and last['OBV'] < last['MA_OBV_30']:
        alert_body = f"📉 Bearish Crossover (ক্রস ডাউন)!\nবর্তমান OBV: {last['OBV']:.2f}, MA_OBV_30: {last['MA_OBV_30']:.2f}"
        send_pushbullet_notification(alert_title, alert_body)
        return True
        
    return False

def main():
    """মূল অ্যালার্ট চেকার ফাংশন"""
    try:
        exchange = ccxt.binance()

        def main():
            """মূল অ্যালার্ট চেকার ফাংশন"""
    try:
        # ccxt এর মাধ্যমে Binance এক্সচেঞ্জ কানেক্ট করা
        exchange = ccxt.binance()
        
        # --- নতুন টেস্ট নোটিফিকেশন ফাংশনটি যোগ করা হয়েছে ---
        send_manual_test_notification()
        # ----------------------------------------------------
        
        print(f"ট্রেডিং পেয়ার্স: {SYMBOL_PAIRS}, টাইমফ্রেম: {TIMEFRAMES}")
        # ... বাকি কোড একই থাকবে ...
        
        for symbol in SYMBOL_PAIRS:
            for tf in TIMEFRAMES:
                try:
                    ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=200)
                    if not ohlcv: continue
                        
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    
                    df = calculate_obv_ma(df)
                    check_crossover(df, symbol, tf)
                    
                    time.sleep(0.5) 
                    
                except Exception as e:
                    print(f"ডেটা প্রসেসিং বা API কল ত্রুটি ({symbol} {tf}): {e}")

    except Exception as e:
        print(f"এক্সচেঞ্জ কানেকশন বা প্রধান ত্রুটি: {e}")
def send_manual_test_notification():
    """ম্যানুয়ালি একটি টেস্ট নোটিফিকেশন পাঠায়"""
    test_title = "✅ GitHub Actions: Pushbullet টেস্ট সফল"
    test_body = "অভিনন্দন! আপনার Pushbullet এবং GitHub সংযোগ ঠিক আছে। এখন ট্রেডিং অ্যালার্ট সিস্টেম চালু হতে পারে।"
    send_pushbullet_notification(test_title, test_body)
    
if __name__ == "__main__":
    main()
