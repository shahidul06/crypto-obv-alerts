import ccxt
import pandas as pd
import requests
import os
import time

# --- কনফিগারেশন: ইন্ডিকেটর প্যারামিটার ও ট্রেড সেটিংস ---
PUSHBULLET_TOKEN = os.environ.get('PUSHBULLET_TOKEN')
MA_PERIOD = 30           # OBV Moving Average (EMA) পিরিয়ড
# প্রাইস এই লেভেলের কত শতাংশ কাছাকাছি থাকলে অ্যালার্ট দেবে (0.005 = 0.5%)
SR_PROXIMITY_PERCENT = 0.005 

SYMBOL_PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
TIMEFRAMES = ['5m', '15m', '30m', '1h'] 
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
    dataframe['MA_OBV_30'] = dataframe['OBV'].ewm(span=MA_PERIOD, adjust=False).mean()
    return dataframe

def calculate_pivot_points(df):
    """Traditional Pivot Points গণনা করে"""
    
    # Pivot Points গণনার জন্য শেষ ক্যান্ডেলের আগের ক্যান্ডেল ব্যবহার করা হয় (C-2) 
    # কারণ C-1 (শেষ ক্যান্ডেল) এখনও ওপেন থাকতে পারে। 
    # যদিও OHLCV ডেটা ক্লোজড ক্যান্ডেল হিসেবে আসে, তবুও ট্রেডিশনাল পদ্ধতি C-2 ব্যবহার করে।
    if len(df) < 2:
        return None
        
    prev_candle = df.iloc[-2]
    H = prev_candle['high']
    L = prev_candle['low']
    C = prev_candle['close']
    
    # Pivot Point (PP)
    PP = (H + L + C) / 3
    
    # Resistance Levels (R)
    R1 = (2 * PP) - L
    R2 = PP + (H - L)
    R3 = H + 2 * (PP - L)

    # Support Levels (S)
    S1 = (2 * PP) - H
    S2 = PP - (H - L)
    S3 = L - 2 * (H - PP)
    
    # PP ও R3/S3 সাধারণত কম ব্যবহৃত হয়, আমরা R1, R2, S1, S2 ব্যবহার করব।
    return [S1, S2, R1, R2] 

def is_near_sr(current_close, sr_levels):
    """বর্তমান মূল্য গণনা করা Pivot Points লেভেলের কাছাকাছি কিনা তা চেক করে"""
    if not sr_levels:
        return None, None 
    
    for level in sr_levels:
        if abs(current_close - level) / level <= SR_PROXIMITY_PERCENT:
            sr_type = "Support" if current_close > level else "Resistance"
            return level, sr_type
            
    return None, None

def check_candlestick_patterns(df, sr_level, sr_type):
    """
    S/R লেভেলের কাছাকাছি একাধিক Candlestick Pattern চেক করে।
    """
    if len(df) < 2:
        return None, None 

    c1 = df.iloc[-1]
    c2 = df.iloc[-2]

    body_c1 = abs(c1['close'] - c1['open'])
    c1_range = c1['high'] - c1['low']
    
    DOJI_THRESHOLD = 0.1
    SHADOW_RATIO = 2.0 
    
    # ------------------- 1. ENGULFING PATTERNS (2-Candle) -------------------
    body_c2 = abs(c2['close'] - c2['open'])
    if body_c1 > 0 and body_c2 > 0:
        
        # Bullish Engulfing (সাপোর্টে)
        if (sr_type == "Support" and c2['close'] < c2['open'] and c1['close'] > c1['open'] and
            c1['close'] >= c2['open'] and c1['open'] <= c2['close']):
            return "BULLISH ENGULFING", "Bullish"

        # Bearish Engulfing (রেজিস্ট্যান্সে)
        elif (sr_type == "Resistance" and c2['close'] > c2['open'] and c1['close'] < c1['open'] and
              c1['open'] >= c2['close'] and c1['close'] <= c2['open']):
            return "BEARISH ENGULFING", "Bearish"

    # ------------------- 2. HAMMER / HANGING MAN (1-Candle) -------------------
    lower_shadow = min(c1['open'], c1['close']) - c1['low']
    upper_shadow = c1['high'] - max(c1['open'], c1['close'])
    
    # Hammer (সাপোর্টে বুলিশ রিভার্সাল)
    if (sr_type == "Support" and body_c1 > 0 and 
        lower_shadow >= body_c1 * SHADOW_RATIO and upper_shadow < body_c1):
        return "BULLISH HAMMER", "Bullish"

    # Hanging Man (রেজিস্ট্যান্সে বেয়ারিশ রিভার্সাল)
    elif (sr_type == "Resistance" and body_c1 > 0 and 
          lower_shadow >= body_c1 * SHADOW_RATIO and upper_shadow < body_c1):
        return "BEARISH HANGING MAN", "Bearish"

    # ------------------- 3. DOJI (1-Candle) -------------------
    if body_c1 < c1_range * DOJI_THRESHOLD:
        return "DOJI STAR (Indecision)", "Indecision"

    return None, None 

def check_crossover(df, symbol, timeframe, exchange_name):
    """
    Pivot Points, Candlestick এবং OBV/MA এর সমন্বয়ে অ্যালার্ট চেক করে।
    """
    
    if len(df) < 2:
        return False
        
    last = df.iloc[-1]
    prev = df.iloc[-2]
    current_close = last['close']
    
    # 1. OBV/MA Crossover Check 
    PRE_CROSS_THRESHOLD = 0.001 
    obv_value = last['OBV']
    ma_value = last['MA_OBV_30']
    
    # Hard Crossover 
    is_bullish_cross = (prev['OBV'] < prev['MA_OBV_30'] and obv_value > ma_value)
    is_bearish_cross = (prev['OBV'] > prev['MA_OBV_30'] and obv_value < ma_value)
    
    # Pre-Cross Logic
    is_pre_cross = False
    if abs(ma_value) > 1:
        difference = abs(obv_value - ma_value)
        distance_percent = difference / abs(ma_value)
        if distance_percent <= PRE_CROSS_THRESHOLD:
            is_pre_cross = True
            
    # 2. Pivot Points and Candlestick Check (স্বয়ংক্রিয় S/R লেভেল)
    sr_levels = calculate_pivot_points(df) # Pivot Points গণনা করা হচ্ছে
    sr_level, sr_type = is_near_sr(current_close, sr_levels)
    pattern_name, pattern_signal = None, None
    
    if sr_level is not None:
        pattern_name, pattern_signal = check_candlestick_patterns(df, sr_level, sr_type)
        
    # --- অ্যালার্ট জেনারেশন ---
    alert_title_base = f"[{symbol} - {timeframe} ({exchange_name})]"
    
    # A. HIGH CONVICTION SIGNAL (OBV/MA + S/R/Candle)
    if (is_bullish_cross and pattern_signal == "Bullish") or \
       (is_bearish_cross and pattern_signal == "Bearish"):
        
        signal_type = "BUY" if is_bullish_cross else "SELL"
        
        alert_body = (
            f"🔥🔥🔥 HIGH CONFIRMATION ENTRY ({signal_type})! 🔥🔥🔥\n"
            f"1. OBV/MA Cross: নিশ্চিত প্রবণতা পরিবর্তন।\n"
            f"2. Pivot Reversal: **{pattern_name}** তৈরি হয়েছে {sr_type} ({sr_level:,.2f})-এর কাছে।"
        )
        send_pushbullet_notification(f"🌟 PIVOT & OBV CONFIRMATION ({signal_type}) {alert_title_base}", alert_body)
        return True
    
    # B. PIVOT Reversal Alert (শুধুমাত্র Pivot Points এবং Candlestick, কোনো ক্রস নেই)
    elif pattern_name is not None:
        
        if "DOJI" in pattern_name:
            alert_priority = "⚠️ PIVOT INDECISION"
        else:
            alert_priority = "⚠️ PIVOT REVERSAL"
        
        alert_body = (
            f"**{pattern_name}** তৈরি হয়েছে!\n"
            f"Candle Pattern: তৈরি হয়েছে {sr_type} ({sr_level:,.2f})-এর কাছে।\n"
            f"OBV/MA অবস্থান: {obv_value:,.2f} / {ma_value:,.2f}।"
        )
        send_pushbullet_notification(f"{alert_priority} {alert_title_base}", alert_body)
        return True
        
    # C. REGULAR OBV/MA Crossover 
    elif is_bullish_cross or is_bearish_cross:
        action = "BUY" if is_bullish_cross else "SELL"
        alert_body = f"🚀 {action} Crossover! OBV:{obv_value:,.2f}, MA:{ma_value:,.2f}"
        send_pushbullet_notification(f"🎯 REGULAR {action} {alert_title_base}", alert_body)
        return True

    # D. Pre-Cross Alert 
    elif is_pre_cross:
        alert_body = (
            f"⚠️ Pre-Cross Warning: OBV MA-এর খুব কাছাকাছি! দূরত্ব: {distance_percent:.2%}\n"
            f"OBV:{obv_value:,.2f}, MA:{ma_value:,.2f}"
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
                        # 200টি ক্যান্ডেল ডেটা নেওয়া হচ্ছে
                        ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=200) 
                        
                        if not ohlcv:
                            print(f"ডেটা নেই: {symbol} {tf} ({exchange_name})")
                            continue
                            
                        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                        
                        df = calculate_obv_ma(df)
                        df.dropna(inplace=True) 
                        
                        if len(df) < 2:
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
