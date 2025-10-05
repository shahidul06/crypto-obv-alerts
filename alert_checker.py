import ccxt
import pandas as pd
import requests
import os
import time

# --- কনফিগারেশন: ইন্ডিকেটর প্যারামিটার ও ট্রেড সেটিংস ---
PUSHBULLET_TOKEN = os.environ.get('PUSHBULLET_TOKEN')
MA_PERIOD = 30           # OBV Moving Average (EMA) পিরিয়ড
ATR_PERIOD = 14          # ATR পিরিয়ড
ADX_PERIOD = 14          # ADX পিরিয়ড
ADX_THRESHOLD = 25       # ADX শর্ত: প্রবণতা শক্তিশালী হওয়ার জন্য সর্বনিম্ন মান
SL_MULTIPLIER = 2.0      # Stop Loss: 2.0 * ATR
TP_RR_RATIO = 1.5        # Take Profit: 1.5 : 1 (Risk/Reward Ratio)

SYMBOL_PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
TIMEFRAMES = ['5m', '15m', '30m', '1h'] # 10m বাদ দেওয়া হয়েছে
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

def calculate_technical_indicators(dataframe):
    """OBV, OBV MA, ATR এবং ADX গণনা করে"""
    
    # --- 1. OBV and MA Calculation ---
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

    # --- 2. ATR Calculation ---
    # True Range (TR)
    h_l = dataframe['high'] - dataframe['low']
    h_pc = abs(dataframe['high'] - dataframe['close'].shift(1))
    l_pc = abs(dataframe['low'] - dataframe['close'].shift(1))
    dataframe['TR'] = h_l.combine(h_pc, max).combine(l_pc, max)
    dataframe['ATR'] = dataframe['TR'].ewm(span=ATR_PERIOD, adjust=False).mean()

    # --- 3. ADX Calculation ---
    
    # Directional Movement (DM)
    dataframe['+DM'] = dataframe['high'] - dataframe['high'].shift(1)
    dataframe['-DM'] = dataframe['low'].shift(1) - dataframe['low']

    # True DM (Filtering out negative values and setting the dominant DM)
    dataframe['+DM'] = dataframe.apply(lambda row: row['+DM'] if row['+DM'] > row['-DM'] and row['+DM'] > 0 else 0, axis=1)
    dataframe['-DM'] = dataframe.apply(lambda row: row['-DM'] if row['+DM'] < row['-DM'] and row['+DM'] <= 0 and row['-DM'] > 0 else 0, axis=1)
    
    # Smooth DM and TR (Wilder's smoothing method using EWM)
    def smooth_indicator(series, period):
        # EWM equivalent to Wilder's smoothing
        return series.ewm(alpha=1/period, adjust=False).mean()
        
    dataframe['TR_S'] = smooth_indicator(dataframe['TR'], ADX_PERIOD)
    dataframe['+DM_S'] = smooth_indicator(dataframe['+DM'], ADX_PERIOD)
    dataframe['-DM_S'] = smooth_indicator(dataframe['+DM'], ADX_PERIOD)
    
    # Directional Index (DI)
    dataframe['+DI'] = (dataframe['+DM_S'] / dataframe['TR_S']) * 100
    dataframe['-DI'] = (dataframe['+DM_S'] / dataframe['TR_S']) * 100
    
    # DX and ADX
    dataframe['DX'] = (abs(dataframe['+DI'] - dataframe['-DI']) / (dataframe['+DI'] + dataframe['-DI'])) * 100
    dataframe['ADX'] = dataframe['DX'].ewm(span=ADX_PERIOD, adjust=False).mean()
    
    # শুধুমাত্র প্রয়োজনীয় কলামগুলো রাখুন
    columns_to_keep = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'OBV', 'MA_OBV_30', 'ATR', 'ADX']
    return dataframe[columns_to_keep]

def check_crossover(df, symbol, timeframe, exchange_name):
    """
    OBV/MA, ADX (ট্রেন্ড) এবং ATR (ভোলাটিলিটি) এর সমন্বয়ে গঠিত নতুন স্ট্র্যাটেজি চেক করে।
    """
    
    if len(df) < (ADX_PERIOD * 2) or pd.isna(df.iloc[-1]['ADX']):
        # ADX ক্যালকুলেশনের জন্য পর্যাপ্ত ডেটা নেই বা ইনিশিয়াল NaN
        return False
        
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Indicator Values
    obv_value = last['OBV']
    ma_value = last['MA_OBV_30']
    adx_value = last['ADX']
    atr_value = last['ATR']
    current_close = last['close']
    
    # 1. ADX Condition: Trend must be strong
    if adx_value < ADX_THRESHOLD:
        return False # ADX 25 এর নিচে, দুর্বল প্রবণতা: অ্যালার্ট উপেক্ষা করুন

    # --- ট্রেডিং সিগন্যাল (Hard Crossover) ---
    
    # 2. Bullish Entry (Buy Signal)
    if prev['OBV'] < prev['MA_OBV_30'] and obv_value > ma_value:
        
        # SL/TP Calculation (ATR based)
        stop_loss_distance = atr_value * SL_MULTIPLIER
        stop_loss_price = current_close - stop_loss_distance
        take_profit_distance = stop_loss_distance * TP_RR_RATIO
        take_profit_price = current_close + take_profit_distance
        
        alert_title = f"[✅ BUY SIGNAL - {symbol} - {timeframe} ({exchange_name})]"
        alert_body = (
            f"🚀 BULLISH ENTRY (ক্রস আপ)!\n"
            f"OBV > MA: ভলিউম সমর্থন করছে।\n"
            f"Trend Strength (ADX): {adx_value:,.2f} (ADX > {ADX_THRESHOLD})\n"
            f"Volatility (ATR): {atr_value:,.4f}\n\n"
            f"Trade Plan (R/R {TP_RR_RATIO}:1):\n"
            f"Entry Price: {current_close:,.4f}\n"
            f"Stop Loss (SL): {stop_loss_price:,.4f} ({SL_MULTIPLIER}x ATR)\n"
            f"Take Profit (TP): {take_profit_price:,.4f}"
        )
        send_pushbullet_notification(alert_title, alert_body)
        return True

    # 3. Bearish Entry (Sell Signal)
    elif prev['OBV'] > prev['MA_OBV_30'] and obv_value < ma_value:
        
        # SL/TP Calculation (ATR based)
        stop_loss_distance = atr_value * SL_MULTIPLIER
        stop_loss_price = current_close + stop_loss_distance
        take_profit_distance = stop_loss_distance * TP_RR_RATIO
        take_profit_price = current_close - take_profit_distance
        
        alert_title = f"[❌ SELL SIGNAL - {symbol} - {timeframe} ({exchange_name})]"
        alert_body = (
            f"📉 BEARISH ENTRY (ক্রস ডাউন)!\n"
            f"OBV < MA: ভলিউম সমর্থন করছে।\n"
            f"Trend Strength (ADX): {adx_value:,.2f} (ADX > {ADX_THRESHOLD})\n"
            f"Volatility (ATR): {atr_value:,.4f}\n\n"
            f"Trade Plan (R/R {TP_RR_RATIO}:1):\n"
            f"Entry Price: {current_close:,.4f}\n"
            f"Stop Loss (SL): {stop_loss_price:,.4f} ({SL_MULTIPLIER}x ATR)\n"
            f"Take Profit (TP): {take_profit_price:,.4f}"
        )
        send_pushbullet_notification(alert_title, alert_body)
        return True
    
    # **Pre-Cross লজিক:** হার্ড ক্রসওভারের পরিবর্তে শুধুমাত্র সতর্কবার্তা
    # শুধুমাত্র শক্তিশালী প্রবণতার সময় (ADX > 25) Pre-Cross দেখাবে
    PRE_CROSS_THRESHOLD = 0.001 
    
    if abs(ma_value) > 1: # Numerical safety
        difference = abs(obv_value - ma_value)
        distance_percent = difference / abs(ma_value)
        
        if distance_percent <= PRE_CROSS_THRESHOLD:
            # Pre-Cross Warning
            alert_title = f"[⚠️ PRE-CROSS WARNING - {symbol} - {timeframe} ({exchange_name})]"
            alert_body = (
                f"OBV MA-এর খুব কাছে: {distance_percent:.2%} দূরত্বে।\n"
                f"Trend Strength (ADX): {adx_value:,.2f}।\n"
                f"পরবর্তী ক্যান্ডেলে এন্ট্রির জন্য প্রস্তুত থাকুন।"
            )
            send_pushbullet_notification(alert_title, alert_body)
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
                        
                        # নতুন ইন্ডিকেটর ফাংশন কল করা হয়েছে
                        df = calculate_technical_indicators(df) 
                        
                        df.dropna(inplace=True) 
                        
                        if len(df) < 2:
                            continue
                            
                        # ক্রসওভার চেক করা
                        check_crossover(df, symbol, tf, exchange_name.upper()) 
                        
                        time.sleep(0.5) 
                        
                    except Exception as e:
                        print(f"ডেটা প্রসেসিং বা API কল ত্রুটি ({symbol} {tf} - {exchange_name.upper()}): {e}")

        except Exception as e:
            print(f"এক্সচেঞ্জ কানেকশন ত্রুটি ({exchange_name.upper()}): {e}")
            continue 
            
if __name__ == "__main__":
    main()
