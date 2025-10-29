name: OBV Alert Checker

on:
  schedule:
    # এটি প্রতি 15 মিনিট অন্তর কোড রান করবে। আপনার প্রয়োজন অনুযায়ী এটি পরিবর্তন করতে পারেন।
    - cron: '*/15 * * * *' 
  workflow_dispatch:
    # এটি আপনাকে GitHub Actions ট্যাবে গিয়ে ম্যানুয়ালি রান করার সুযোগ দেবে।

jobs:
  check_alerts:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Install dependencies
        # আপনার requirements.txt ফাইলে থাকা সব লাইব্রেরি ইন্সটল করবে
        run: pip install -r requirements.txt

      - name: Run main()
        # এখানে আপনার সিক্রেটগুলো Python স্ক্রিপ্টের জন্য পরিবেশ ভ্যারিয়েবল হিসেবে লোড করা হচ্ছে।
        # এটিই অ্যালার্ট না আসার মূল কারণটি সমাধান করবে।
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python alert_checker.py
