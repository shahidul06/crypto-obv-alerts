def check_crossover(df, symbol, timeframe):
    """
    OBV এবং MA_OBV_30 ক্রসওভার চেক করে নোটিফিকেশন পাঠায়, 
    সাথে ক্রসওভার ঘটার ১% আগে Pre-crossover অ্যালার্টও পাঠায়।
    """
    
    if len(df) < 2:
        return False
        
    last = df.iloc[-1]
    
    # 1. থ্রেশহোল্ড এবং ডেটা গণনা
    PRE_CROSS_THRESHOLD = 0.01  # 1% দূরত্ব (0.01)
    
    obv_value = last['OBV']
    ma_value = last['MA_OBV_30']
    
    # OBV, MA থেকে কত দূরে আছে, তার শতাংশ গণনা
    distance = abs(obv_value - ma_value) / ma_value
    
    alert_title = f"[🎯 ALERT - {symbol} - {timeframe}]"
    
    # 2. নতুন: Pre-crossover চেক (ক্রসওভার ঘটেনি, কিন্তু কাছে আছে)
    if distance <= PRE_CROSS_THRESHOLD:
        
        # Bullish Pre-Cross: OBV এখন নিচে আছে, কিন্তু কাছে আসছে
        if obv_value < ma_value:
            alert_body = f"⚠️ Pre-Cross (Bullish)! OBV লাইনটি MA-এর নিচে থেকে মাত্র {distance:.2%} দূরত্বে আছে। ক্রসিংয়ের জন্য প্রস্তুত হোন!"
            send_pushbullet_notification(alert_title, alert_body)
            return True
            
        # Bearish Pre-Cross: OBV এখন উপরে আছে, কিন্তু কাছে আসছে
        elif obv_value > ma_value:
            alert_body = f"⚠️ Pre-Cross (Bearish)! OBV লাইনটি MA-এর উপরে থেকে মাত্র {distance:.2%} দূরত্বে আছে। ক্রসিংয়ের জন্য প্রস্তুত হোন!"
            send_pushbullet_notification(alert_title, alert_body)
            return True
        
    # 3. পুরনো: Hard Crossover চেক (যদি ১% এর চেয়ে বেশি দূর থেকেও ক্রস করে)
    # এই অংশটি আপনার পুরনো এবং নির্ভরযোগ্য লজিক
    prev = df.iloc[-2]
    
    if prev['OBV'] < prev['MA_OBV_30'] and last['OBV'] > last['MA_OBV_30']:
        alert_body = f"🚀 Bullish Crossover (ক্রস আপ)! নিশ্চিত প্রবণতা পরিবর্তন!"
        send_pushbullet_notification(alert_title, alert_body)
        return True

    elif prev['OBV'] > prev['MA_OBV_30'] and last['OBV'] < last['MA_OBV_30']:
        alert_body = f"📉 Bearish Crossover (ক্রস ডাউন)! নিশ্চিত প্রবণতা পরিবর্তন!"
        send_pushbullet_notification(alert_title, alert_body)
        return True
        
    return False 
