import ccxt
import pandas as pd
import requests
import os
import time

# --- কনফিগারেশন: ইন্ডিকেটর প্যারামিটার ও ট্রেড সেটিংস ---

# PUSHBULLET_TOKEN এর পরিবর্তে TELEGRAM ভ্যারিয়েবল ব্যবহার করা হবে
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

MA_PERIOD = 50           # OBV Moving Average (EMA) পিরিয়ড
ADX_PERIOD = 14          # ADX গণনার জন্য পিরিয়ড
ADX_THRESHOLD = 25       # ADX এই মানের উপরে থাকলে তবেই সিগনাল নিশ্চিত হবে

SYMBOL_PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
TIMEFRAMES = ['15m', '30m', '1h'] 
# ----------------------------------------------------

def send_telegram_message(title, body):
    """Telegram Bot এর মাধ্যমে নোটিফিকেশন পাঠানো হয়"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram টোকেন বা চ্যাট আইডি সেট করা নেই। নোটিফিকেশন পাঠানো সম্ভব নয়।")
        return

    # মেসেজের বডি তৈরি করা
    message_text = f"**{title}**\n\n{body}"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    params = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message_text,
        "parse_mode": "Markdown" # Markdown ফর্ম্যাটিং ব্যবহার করা হলো
    }

    try:
        # Telegram API call
        response = requests.post(url, data=params)
        
        if response.status_code == 200:
            print(f"Telegram নোটিফিকেশন সফলভাবে পাঠানো হয়েছে: {title}")
        else:
            print(f"Telegram ত্রুটি: স্ট্যাটাস কোড {response.status_code} - বডি: {response.text}")
    except Exception as e:
        print(f"Telegram সংযোগ ত্রুটি: {e}")

# Pushbullet ফাংশনটি Telegram ফাংশনে প্রতিস্থাপন করা হয়েছে 
# যাতে check_crossover ফাংশনটিকে পরিবর্তন করতে না হয়।
send_pushbullet_notification = send_telegram_message


def calculate_obv_ma(dataframe):
    """OBV এবং 50 পিরিয়ডের EMA গণনা করে"""
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
    dataframe[f'MA_OBV_{MA_PERIOD}'] = dataframe['OBV'].ewm(span=MA_PERIOD, adjust=False).mean()
    return dataframe

def calculate_adx(dataframe, period=ADX_PERIOD):
    """
    ADX ইন্ডিকেটর গণনা করে।
    """
    
    # 1. True Range (TR)
    tr1 = dataframe['high'] - dataframe['low']
    tr2 = abs(dataframe['high'] - dataframe['close'].shift(1))
    tr3 = abs(dataframe['low'] - dataframe['close'].shift(1))
    dataframe['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # 2. Directional Movement (+DM and -DM)
    dataframe['+DM'] = dataframe['high'] - dataframe['high'].shift(1)
    dataframe['-DM'] = dataframe['low'].shift(1) - dataframe['low']
    
    # +DM and -DM rules:
    dataframe['+DM'] = dataframe.apply(
        lambda row: row['+DM'] if row['+DM'] > row['-DM'] and row['+DM'] > 0 else 0, axis=1
    )
    dataframe['-DM'] = dataframe.apply(
        lambda row: row['-DM'] if row['-DM'] > row['+DM'] and row['-DM'] > 0 else 0, axis=1
    )

    # 3. Smoothed TR, +DM, -DM (Using Wilder's smoothing method - EMA equivalent)
    alpha = 1 / period
    dataframe['ATR'] = dataframe['TR'].ewm(alpha=alpha, adjust=False).mean()
    dataframe['+DI'] = (dataframe['+DM'].ewm(alpha=alpha, adjust=False).mean() / dataframe['ATR']) * 100
    dataframe['-DI'] = (dataframe['-DM'].ewm(alpha=alpha, adjust=False).mean() / dataframe['ATR']) * 100

    # 4. Directional Index (DX)
    dataframe['DX'] = (abs(dataframe['+DI'] - dataframe['-DI']) / (dataframe['+DI'] + dataframe['-DI'])) * 100

    # 5. Average Directional Index (ADX)
    dataframe['ADX'] = dataframe['DX'].ewm(alpha=alpha, adjust=False).mean()

    return dataframe

def check_crossover(df, symbol, timeframe, exchange_name):
    """
    OBV/MA ক্রসওভার চেক করে এবং ADX দিয়ে ফিল্টার করে।
    """
    
    if len(df) < (ADX_PERIOD * 2):
        return False
        
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    PRE_CROSS_THRESHOLD = 0.001 
    
    obv_value = last['OBV']
    ma_value = last[f'MA_OBV_{MA_PERIOD}'] 
    adx_value = last['ADX']
    
    alert_title_base = f"[{symbol} - {timeframe} ({exchange_name})]"
    
    # 2. Hard Crossover (OBV/MA ক্রস)
    is_bullish_cross = (prev['OBV'] < prev[f'MA_OBV_{MA_PERIOD}'] and obv_value > ma_value)
    is_bearish_cross = (prev['OBV'] > prev[f'MA_OBV_{MA_PERIOD}'] and obv_value < ma_value)
    
    # 3. ADX ফিল্টার চেক (ADX > 25?)
    is_strong_trend = (adx_value >= ADX_THRESHOLD)

    # A. HIGH-QUALITY SIGNAL (OBV/MA ক্রস AND ADX > 25)
    if (is_bullish_cross or is_bearish_cross) and is_strong_trend:
        action = "BUY" if is_bullish_cross else "SELL"
        signal_type = "Bullish" if is_bullish_cross else "Bearish"

        alert_body = (
            f"🔥🔥🔥 HIGH CONFIRMATION SIGNAL (*{action}*)! 🔥🔥🔥\n"
            f"OBV/MA Cross: {signal_type} প্রবণতা শুরু।\n"
            f"ADX Confirmation: ADX = *{adx_value:,.2f}* ({ADX_THRESHOLD} এর উপরে)।"
        )
        send_pushbullet_notification(f"🌟 HIGH QUALITY {action} {alert_title_base}", alert_body)
        return True

    # B. REGULAR OBV/MA Crossover (ADX ফিল্টার ছাড়া)
    elif (is_bullish_cross or is_bearish_cross) and not is_strong_trend:
        action = "BUY" if is_bullish_cross else "SELL"
        alert_body = (
            f"🎯 REGULAR *{action}* Crossover! (সতর্ক থাকুন, ADX দুর্বল: *{adx_value:,.2f}*)\n"
            f"OBV:{obv_value:,.2f}, MA({MA_PERIOD}):{ma_value:,.2f}"
        )
        send_pushbullet_notification(f"🎯 REGULAR {action} {alert_title_base}", alert_body)
        return True
        
    # C. Pre-Cross (সতর্কতা) লজিক: ADX ফিল্টার এখানে প্রযোজ্য নয়
    if abs(ma_value) > 1: 
        difference = abs(obv_value - ma_value)
        distance_percent = difference / abs(ma_value)
        
        if distance_percent <= PRE_CROSS_THRESHOLD:
            alert_body = (
                f"⚠️ Pre-Cross Warning: OBV MA({MA_PERIOD})-এর খুব কাছাকাছি! দূরত্ব: *{distance_percent:.2%}*\n"
                f"OBV:{obv_value:,.2f}, MA({MA_PERIOD}):{ma_value:,.2f}"
            )
            send_pushbullet_notification(f"⚠️ PRE-CROSS {alert_title_base}", alert_body)
            return True
        
    return False

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
                        
                        if len(df) < (ADX_PERIOD * 2):
                            continue
                            
                        check_crossover(df, symbol, tf, exchange_name.upper()) 
                        
                        time.sleep(0.5) 
                        
                    except Exception as e:
                        print(f"ডেটা প্রসেসিং বা API কল ত্রুটি ({symbol} {tf} - {exchange_name.upper()}): {e}")

        except Exception as e:
            print(f"এক্সচেঞ্জ কানেকশন ত্রুটি ({exchange_name.upper()}): {e}")
            continue 
            
if __name__ == "__main__":
    main()
