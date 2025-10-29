import ccxt
import pandas as pd
import requests
import os
import time
import json 
import numpy as np

# --- কনফিগারেশন: ইন্ডিকেটর প্যারামিটার ও ট্রেড সেটিংস ---

# GitHub Secrets থেকে ভ্যারিয়েবল লোড করা হচ্ছে
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

MA_PERIOD = 50           
ADX_PERIOD = 14          
ADX_THRESHOLD = 25       
PRE_CROSS_THRESHOLD = 0.001 

SYMBOL_PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
TIMEFRAMES = ['15m', '30m', '1h'] 

# ----------------------------------------------------

def send_telegram_message(title, body):
    """Telegram Bot এর মাধ্যমে নোটিফিকেশন পাঠানো হয়"""
    
    # সিক্রেট লোড হয়েছে কি না, তা পরীক্ষা করা
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("🔴 ERROR: Telegram টোকেন বা চ্যাট আইডি সেট করা নেই। নোটিফিকেশন পাঠানো সম্ভব নয়।")
        return

    # মেসেজের বডি তৈরি করা
    message_text = f"*{title}*\n\n{body}"

    # Telegram API Endpoint
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    params = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message_text,
        "parse_mode": "Markdown", 
        "disable_web_page_preview": True
    }

    try:
        # Telegram API call
        response = requests.post(url, data=params, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Telegram নোটিফিকেশন সফলভাবে পাঠানো হয়েছে: {title}")
        else:
            # API থেকে আসা ত্রুটি বার্তাটি প্রিন্ট করা হচ্ছে
            error_details = response.json()
            print(f"❌ Telegram API ত্রুটি: স্ট্যাটাস কোড {response.status_code} - বডি: {json.dumps(error_details, indent=2)}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Telegram সংযোগ ত্রুটি: {e}")


def calculate_obv_ma(dataframe):
    """OBV এবং 50 পিরিয়ডের EMA গণনা করে"""
    obv = np.zeros(len(dataframe))
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
    dataframe[f'MA_OBV_{MA_PERIOD}'] = dataframe['OBV'].ewm(span=MA_PERIOD, adjust=False).mean()
    return dataframe

def calculate_adx(dataframe, period=ADX_PERIOD):
    """ADX ইন্ডিকেটর গণনা করে।"""
        
    # True Range (TR)
    tr1 = dataframe['high'] - dataframe['low']
    tr2 = abs(dataframe['high'] - dataframe['close'].shift(1))
    tr3 = abs(dataframe['low'] - dataframe['close'].shift(1))
    dataframe['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Directional Movement (+DM and -DM)
    dataframe['+DM'] = dataframe['high'] - dataframe['high'].shift(1)
    dataframe['-DM'] = dataframe['low'].shift(1) - dataframe['low']
    
    # +DM এবং -DM নির্ধারণ
    dataframe['+DM'] = np.where((dataframe['+DM'] > dataframe['-DM']) & (dataframe['+DM'] > 0), dataframe['+DM'], 0)
    dataframe['-DM'] = np.where((dataframe['-DM'] > dataframe['+DM']) & (dataframe['-DM'] > 0), dataframe['-DM'], 0)

    # Smoothed TR, +DM, -DM (Wilder's smoothing)
    alpha = 1 / period
    dataframe['ATR'] = dataframe['TR'].ewm(alpha=alpha, adjust=False).mean()
    
    dataframe['+DI'] = (dataframe['+DM'].ewm(alpha=alpha, adjust=False).mean() / dataframe['ATR']) * 100
    dataframe['-DI'] = (dataframe['-DM'].ewm(alpha=alpha, adjust=False).mean() / dataframe['ATR']) * 100

    # Directional Index (DX) and ADX
    dataframe['DX'] = (abs(dataframe['+DI'] - dataframe['-DI']) / (dataframe['+DI'] + dataframe['-DI'])) * 100
    dataframe['ADX'] = dataframe['DX'].ewm(alpha=alpha, adjust=False).mean()

    return dataframe

def check_crossover(df, symbol, timeframe, exchange_name):
    """
    OBV/MA ক্রসওভার চেক করে এবং ADX দিয়ে ফিল্টার করে।
    """
        
    if len(df) < (ADX_PERIOD + MA_PERIOD): 
        return
        
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    obv_value = last['OBV']
    ma_value = last[f'MA_OBV_{MA_PERIOD}'] 
    adx_value = last['ADX']
    
    alert_title_base = f"[{symbol} - {timeframe} ({exchange_name})]"
    
    # Hard Crossover (OBV/MA ক্রস)
    is_bullish_cross = (prev['OBV'] < prev[f'MA_OBV_{MA_PERIOD}'] and obv_value > ma_value)
    is_bearish_cross = (prev['OBV'] > prev[f'MA_OBV_{MA_PERIOD}'] and obv_value < ma_value)
    
    # ADX ফিল্টার চেক
    is_strong_trend = (adx_value >= ADX_THRESHOLD)

    # A. HIGH-QUALITY SIGNAL (OBV/MA ক্রস AND ADX > 25)
    if (is_bullish_cross or is_bearish_cross) and is_strong_trend:
        action = "BUY" if is_bullish_cross else "SELL"
        signal_type = "Bullish" if is_bullish_cross else "Bearish"

        alert_body = (
            f"🔥🔥🔥 *HIGH CONFIRMATION SIGNAL* (*{action}*)! 🔥🔥🔥\n"
            f"OBV/MA Cross: {signal_type} প্রবণতা নিশ্চিত।\n"
            f"ADX Confirmation: ADX = *{adx_value:,.2f}* (>{ADX_THRESHOLD})"
        )
        send_telegram_message(f"🌟 HIGH QUALITY {action} {alert_title_base}", alert_body)
        return

    # B. REGULAR OBV/MA Crossover (ADX ফিল্টার ছাড়া)
    elif (is_bullish_cross or is_bearish_cross) and not is_strong_trend:
        action = "BUY" if is_bullish_cross else "SELL"
        alert_body = (
            f"🎯 *REGULAR {action} Crossover* (সতর্ক থাকুন, ADX দুর্বল!)\n"
            f"OBV:{obv_value:,.2f}, MA({MA_PERIOD}):{ma_value:,.2f}\n"
            f"ADX: *{adx_value:,.2f}*"
        )
        send_telegram_message(f"🎯 REGULAR {action} {alert_title_base}", alert_body)
        return
        
    # C. Pre-Cross (সতর্কতা)
    if abs(ma_value) > 1: 
        difference = abs(obv_value - ma_value)
        distance_percent = difference / abs(ma_value)
        
        if distance_percent <= PRE_CROSS_THRESHOLD:
            alert_body = (
                f"⚠️ *Pre-Cross Warning*: OBV MA({MA_PERIOD})-এর খুব কাছাকাছি!\n"
                f"দূরত্ব: *{distance_percent:.2%}*\n"
                f"OBV:{obv_value:,.2f}, MA({MA_PERIOD}):{ma_value:,.2f}"
            )
            send_telegram_message(f"⚠️ PRE-CROSS {alert_title_base}", alert_body)
            return

def main():
    
    EXCHANGES_TO_CHECK = [
        ccxt.mexc(),    
        ccxt.kucoin(), 
    ]
    
    print(f"ট্রেডিং পেয়ার্স: {SYMBOL_PAIRS}, টাইমফ্রেম: {TIMEFRAMES}")
    
    for exchange in EXCHANGES_TO_CHECK:
        exchange_name = exchange.id
        print(f"\n--- {exchange_name.upper()} থেকে ডেটা আনার চেষ্টা ---")
        
        try:
            for symbol in SYMBOL_PAIRS:
                for tf in TIMEFRAMES:
                    try:
                        ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=200) 
                        
                        if not ohlcv:
                            print(f"ডেটা নেই: {symbol} {tf} ({exchange_name})")
                            continue
                            
                        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                        
                        df = calculate_obv_ma(df)
                        df = calculate_adx(df) 
                        
                        df.dropna(inplace=True) 
                        
                        if len(df) < (ADX_PERIOD + MA_PERIOD):
                            continue
                            
                        check_crossover(df, symbol, tf, exchange_name.upper()) 
                        
                        time.sleep(0.5) 
                        
                    except Exception as e:
                        print(f"❌ ডেটা প্রসেসিং বা API কল ত্রুটি ({symbol} {tf} - {exchange_name.upper()}): {e}")

        except Exception as e:
            print(f"❌ এক্সচেঞ্জ কানেকশন ত্রুটি ({exchange_name.upper()}): {e}")
            continue 
            
    # --- ⭐ পরীক্ষামূলক মেসেজ যোগ করা হয়েছে ⭐ ---
    print("\n--- টেস্টিং মেসেজ পাঠানোর চেষ্টা ---")
    send_telegram_message("🤖 টেস্ট এলার্ট (জরুরী)", "যদি এই মেসেজটি পান, তাহলে টোকেন ও চ্যাট আইডি ঠিক আছে।")
    # -----------------------------------------------

if __name__ == "__main__":
    main()
