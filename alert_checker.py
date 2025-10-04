def check_crossover(df, symbol, timeframe):
    """
    OBV এবং MA_OBV_30 ক্রসওভার চেক করে নোটিফিকেশন পাঠায়, 
    সাথে ক্রসওভার ঘটার ১% আগে Pre-crossover অ্যালার্টও পাঠায়।
    """
    
    if len(df) < 2:
        return False
        
    last = df.iloc[-1]
    prev = df.iloc[-2] # এই লাইনটি আসল ক্রসওভার লজিকের জন্য রাখা হয়েছে।
    
    # 1. থ্রেশহোল্ড এবং ডেটা গণনা
    PRE_CROSS_THRESHOLD = 0.01  # 1% দূরত্ব (0.01)
    
    obv_value = last['OBV']
    ma_value = last['MA_OBV_30']
    
    alert_title = f"[🎯 ALERT - {symbol} - {timeframe}]"
    
    # Pre-Cross লজিক:
    # শুধুমাত্র তখনই Pre-Cross অ্যালার্ট দেবে, যখন আগের ক্যান্ডেলটি দূরে ছিল এবং এখন কাছাকাছি এসেছে।
    # এটি Pre-Cross অ্যালার্টের স্প্যামিং কিছুটা কমাবে।

    if obv_value * (1 + PRE_CROSS_THRESHOLD) >= ma_value and obv_value < ma_value:
        # OBV MA-এর নিচে আছে, কিন্তু 1% এর কাছাকাছি বা নিচে চলে এসেছে (Bullish Pre-Cross)
        if prev['OBV'] * (1 + PRE_CROSS_THRESHOLD) < ma_value:
            alert_body = f"⚠️ Pre-Cross (Bullish)! OBV MA-এর নিচে থেকে কাছে আসছে (1% মধ্যে)।"
            send_pushbullet_notification(alert_title, alert_body)
            return True

    elif obv_value * (1 - PRE_CROSS_THRESHOLD) <= ma_value and obv_value > ma_value:
        # OBV MA-এর উপরে আছে, কিন্তু 1% এর কাছাকাছি বা নিচে চলে এসেছে (Bearish Pre-Cross)
        if prev['OBV'] * (1 - PRE_CROSS_THRESHOLD) > ma_value:
            alert_body = f"⚠️ Pre-Cross (Bearish)! OBV MA-এর উপরে থেকে কাছে আসছে (1% মধ্যে)।"
            send_pushbullet_notification(alert_title, alert_body)
            return True
            
    # 2. আসল Hard Crossover চেক (এই লজিকটি সবচেয়ে নির্ভরযোগ্য)
    if prev['OBV'] < prev['MA_OBV_30'] and last['OBV'] > last['MA_OBV_30']:
        alert_body = f"🚀 Bullish Crossover (ক্রস আপ)! নিশ্চিত প্রবণতা পরিবর্তন!"
        send_pushbullet_notification(alert_title, alert_body)
        return True

    elif prev['OBV'] > prev['MA_OBV_30'] and last['OBV'] < last['MA_OBV_30']:
        alert_body = f"📉 Bearish Crossover (ক্রস ডাউন)! নিশ্চিত প্রবণতা পরিবর্তন!"
        send_pushbullet_notification(alert_title, alert_body)
        return True
        
    return False 
