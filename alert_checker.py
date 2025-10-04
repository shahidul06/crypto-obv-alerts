def check_crossover(df, symbol, timeframe):
    """
    OBV এবং MA_OBV_30 ক্রসওভার চেক করে নোটিফিকেশন পাঠায়।
    Pre-crossover-এর জন্য 0.5% দূরত্ব চেক করে।
    """
    
    if len(df) < 2:
        return False
        
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. সেটআপ
    # MA-এর সাপেক্ষে 0.5% বা তার কম দূরত্বে থাকলেই Pre-Cross অ্যালার্ট দেবে
    PRE_CROSS_THRESHOLD = 0.005 
    
    obv_value = last['OBV']
    ma_value = last['MA_OBV_30']
    
    alert_title = f"[🎯 ALERT - {symbol} - {timeframe}]"
    
    # 2. Hard Crossover (নিশ্চিত ক্রসওভার) লজিক:
    # এটিই সবচেয়ে নির্ভরযোগ্য সিগন্যাল
    if prev['OBV'] < prev['MA_OBV_30'] and obv_value > ma_value:
        alert_body = f"🚀 Bullish Crossover (ক্রস আপ)! নিশ্চিত প্রবণতা পরিবর্তন! OBV:{obv_value:,.2f}, MA:{ma_value:,.2f}"
        send_pushbullet_notification(alert_title, alert_body)
        return True

    elif prev['OBV'] > prev['MA_OBV_30'] and obv_value < ma_value:
        alert_body = f"📉 Bearish Crossover (ক্রস ডাউন)! নিশ্চিত প্রবণতা পরিবর্তন! OBV:{obv_value:,.2f}, MA:{ma_value:,.2f}"
        send_pushbullet_notification(alert_title, alert_body)
        return True
        
    # 3. Pre-Cross (সতর্কতা) লজিক:
    # সংখ্যাসূচক নিরাপত্তা: যদি MA-এর মান ১-এর চেয়ে কম হয় তবে দূরত্ব চেক এড়িয়ে যান।
    if abs(ma_value) > 1: 
        
        # দূরত্ব গণনা (শতাংশে):
        difference = abs(obv_value - ma_value)
        distance_percent = difference / abs(ma_value)
        
        # যদি দূরত্ব 0.5% এর মধ্যে থাকে
        if distance_percent <= PRE_CROSS_THRESHOLD:
            
            # শুধুমাত্র সতর্কবার্তা পাঠাবে যদি এটি আসল ক্রসওভার না হয়
            if obv_value > ma_value:
                alert_body = f"⚠️ Pre-Cross (Bearish)! OBV MA-এর উপরে আছে, কিন্তু মাত্র {distance_percent:.2%} দূরত্বে।"
                send_pushbullet_notification(alert_title, alert_body)
                return True
            elif obv_value < ma_value:
                alert_body = f"⚠️ Pre-Cross (Bullish)! OBV MA-এর নিচে আছে, কিন্তু মাত্র {distance_percent:.2%} দূরত্বে।"
                send_pushbullet_notification(alert_title, alert_body)
                return True
        
    return False
