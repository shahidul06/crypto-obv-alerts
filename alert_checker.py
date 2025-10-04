def check_crossover(df, symbol, timeframe):
    """
    OBV এবং MA_OBV_30 ক্রসওভার চেক করে নোটিফিকেশন পাঠায়।
    এই লজিকটি নিশ্চিত করে যেন একবার ক্রসওভার হলেই নোটিফিকেশন আসে এবং প্রবণতা চলতে থাকলে বারবার না আসে।
    """
    
    if len(df) < 2:
        return False
        
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    alert_title = f"[🎯 ALERT - {symbol} - {timeframe}]"
    
    # 1. ক্রস আপ (Bullish Crossover) চেক
    # আগের পিরিয়ডে OBV ছিল MA-এর নিচে, আর এখন OBV MA-এর উপরে
    if prev['OBV'] < prev['MA_OBV_30'] and last['OBV'] > last['MA_OBV_30']:
        alert_body = f"🚀 Bullish Crossover (ক্রস আপ)!\nOBV লাইনটি তার ৩০-পিরিয়ডের MA লাইনটিকে অতিক্রম করে উপরে উঠেছে।\nবর্তমান OBV: {last['OBV']:.2f}, MA_OBV_30: {last['MA_OBV_30']:.2f}"
        send_pushbullet_notification(alert_title, alert_body)
        return True

    # 2. ক্রস ডাউন (Bearish Crossover) চেক
    # আগের পিরিয়ডে OBV ছিল MA-এর উপরে, আর এখন OBV MA-এর নিচে
    elif prev['OBV'] > prev['MA_OBV_30'] and last['OBV'] < last['MA_OBV_30']:
        alert_body = f"📉 Bearish Crossover (ক্রস ডাউন)!\nOBV লাইনটি তার ৩০-পিরিয়ডের MA লাইনটিকে অতিক্রম করে নিচে নেমেছে।\nবর্তমান OBV: {last['OBV']:.2f}, MA_OBV_30: {last['MA_OBV_30']:.2f}"
        send_pushbullet_notification(alert_title, alert_body)
        return True
        
    return False # কোনো ক্রসওভার ঘটেনি
