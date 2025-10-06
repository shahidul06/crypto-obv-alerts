import ccxt
import pandas as pd
import requests
import os
import time

# --- কনফিগারেশন: ইন্ডিকেটর প্যারামিটার ও ট্রেড সেটিংস ---
PUSHBULLET_TOKEN = os.environ.get('PUSHBULLET_TOKEN')
MA_PERIOD = 30           # OBV Moving Average (EMA) পিরিয়ড (আপনার অনুরোধে 30 এ রাখা হলো)
SYMBOL_PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']

# **পরিবর্তন:** 5 মিনিটের টাইমফ্রেম বাতিল করা হয়েছে।
TIMEFRAMES = ['15m', '30m', '1h'] 
# ----------------------------------------------------

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
            print(f"Pushbullet নোটিফিকেশন সফলভাবে পাঠানো হয়েছে: {title}")
        else:
            print(f"Pushbullet ত্রুটি: স্ট্যাটাস কোড {response.status_code} - বডি: {response.text}")
    except Exception as e:
        print(f"Pushbullet সংযোগ ত্রুটি: {e}")

def calculate_obv_ma(dataframe):
    """OBV এবং ৩০ পিরিয়ডের Exponential Moving Average (EMA) গণনা করে"""
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
    # EMA গণনা
    dataframe['MA_OBV_30'] = dataframe['OBV'].ewm(span=MA_PERIOD, adjust=False).mean()
    
    # শুধুমাত্র প্রয়োজনীয় কলামগুলো রাখুন
    columns_to_keep = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'OBV', 'MA_OBV_30']
    return dataframe[columns_to_keep]

def check_crossover(df, symbol, timeframe, exchange_name):
    """
    শুধুমাত্র OBV এবং MA_OBV_30 ক্রসওভার এবং Pre-Cross চেক করে।
    """
    
    if len(df) < 2:
        return False
        
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. সেটআপ: থ্রেশহোল্ড 0.1% এ সেট করা হলো (0.001)
    PRE_CROSS_THRESHOLD = 0.001 
    
    obv_value = last['OBV']
    ma_value = last['MA_OBV_30']
    
    alert_title_base = f"[{symbol} - {timeframe} ({exchange_name})]"
    
    # 2. Hard Crossover (নিশ্চিত ক্রসওভার) লজিক:
    if prev['OBV'] < prev['MA_OBV_30'] and obv_value > ma_value:
        alert_body = f"🚀 Bullish Crossover (ক্রস আপ)! নিশ্চিত প্রবণতা পরিবর্তন! OBV:{obv_value:,.2f}, MA:{ma_value:,.2f}"
        send_pushbullet_notification(f"✅ BUY SIGNAL {alert_title_base}", alert_body)
        return True

    elif prev['OBV'] > prev['MA_OBV_30'] and obv_value < ma_value:
        alert_body = f"📉 Bearish Crossover (ক্রস ডাউন)! নিশ্চিত প্রবণতা পরিবর্তন! OBV:{obv_value:,.2f}, MA:{ma_value:,.2f}"
        send_pushbullet_notification(f"❌ SELL SIGNAL {alert_title_base}", alert_body)
        return True
        
    # 3. Pre-Cross (সতর্কতা) লজিক:
    if abs(ma_value) > 1: 
        
        # দূরত্ব গণনা (শতাংশে):
        difference = abs(obv_value - ma_value)
        distance_percent = difference / abs(ma_value)
        
        # যদি দূরত্ব 0.1% এর মধ্যে থাকে
        if distance_percent <= PRE_CROSS_THRESHOLD:
            
            # শুধুমাত্র সতর্কবার্তা পাঠাবে যদি এটি আসল ক্রসওভার না হয়
            alert_body = (
                f"⚠️ Pre-Cross Warning: OBV MA-এর খুব কাছাকাছি! দূরত্ব: {distance_percent:.2%}\n"
                f"OBV:{obv_value:,.2f}, MA:{ma_value:,.2f}"
            )
            send_pushbullet_notification(f"⚠️ PRE-CROSS {alert_title_base}", alert_body)
            return True
        
    return False

def main():
    
    # ব্যবহারের জন্য এক্সচেঞ্জের তালিকা
    EXCHANGES_TO_CHECK = [
        ccxt.mexc(),    
        ccxt.kucoin(), 
    ]
    
    print(f"ট্রেডিং পেয়ার্স: {SYMBOL_PAIRS}, টাইমফ্রেম: {TIMEFRAMES}")
    
    # প্রতিটি এক্সচেঞ্জের জন্য ডেটা আনার চেষ্টা করা হবে
    for exchange in EXCHANGES_TO_CHECK:
        exchange_name = exchange.id
        print(f"\n--- {exchange_name.upper()} থেকে ডেটা আনার চেষ্টা ---")
        
        try:
            
            for symbol in SYMBOL_PAIRS:
                for tf in TIMEFRAMES:
                    try:
                        # লিমিট=200 ক্যান্ডেল ডেটা নেওয়া হচ্ছে
                        ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=200) 
                        
                        if not ohlcv:
                            print(f"ডেটা নেই: {symbol} {tf} ({exchange_name})")
                            continue
                            
                        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                        
                        df = calculate_obv_ma(df)
                        
                        # NaN ফিক্স: NaN ভ্যালু বাদ দেওয়া হচ্ছে
                        df.dropna(inplace=True) 
                        
                        if len(df) < 2:
                            continue
                            
                        # ক্রসওভার চেক করা
                        check_crossover(df, symbol, tf, exchange_name.upper()) 
                        
                        time.sleep(0.5) 
                        
                    except Exception as e:
                        # নির্দিষ্ট পেয়ারের ত্রুটি
                        print(f"ডেটা প্রসেসিং বা API কল ত্রুটি ({symbol} {tf} - {exchange_name.upper()}): {e}")

        except Exception as e:
            # এক্সচেঞ্জ স্তরের ত্রুটি
            print(f"এক্সচেঞ্জ কানেকশন ত্রুটি ({exchange_name.upper()}): {e}")
            continue # এই এক্সচেঞ্জ ব্যর্থ হলে পরেরটি চেষ্টা করা হবে
            
if __name__ == "__main__":
    main()
