from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import yfinance as yf
import re
import os
import requests
from datetime import date

app = Flask(__name__)

SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

# ブラウザ偽装をさらに強化
custom_session = requests.Session()
custom_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
})

def to_float(val):
    try:
        val = re.sub(r"[^\d.-]", "", str(val))
        return float(val) if val else 0.0
    except:
        return 0.0

def get_stock_data_simple(code):
    """
    もっともエラーが起きにくいhistory(5d)のみを使用
    """
    ticker_code = f"{code}.T"
    try:
        t = yf.Ticker(ticker_code, session=custom_session)
        # 5日分のデータを取得
        hist = t.history(period="5d")
        
        if not hist.empty:
            current_price = float(hist["Close"].iloc[-1])
            # 前日の終値
            prev_price = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current_price
            change = current_price - prev_price
            change_pct = (change / prev_price * 100) if prev_price > 0 else 0
            
            # ログに成功を表示
            print(f"SUCCESS: {code} - Price: {current_price}")
            return current_price, change, change_pct
        else:
            print(f"FAILED: {code} - No history data")
            return 0.0, 0.0, 0.0
    except Exception as e:
        print(f"CRITICAL ERROR: {code} - {str(e)}")
        return 0.0, 0.0, 0.0

@app.route("/")
def index():
    try:
        # 1. スプレッドシート読み込み
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        results = []
        total_profit = 0

        for _, row in df.iterrows():
            code = str(row.get("証券コード", "")).strip().upper()
            if not code or code == "NAN": continue

            name = str(row.get("銘柄", "")).strip()
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))

            # 2. 価格取得（infoを使わない軽量版）
            price, change, change_pct = get_stock_data_simple(code)
            
            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit

            results.append({
                "code": code, "name": name, "buy": buy_price, "qty": qty,
                "price": price, "change": change, "change_pct": round(change_pct, 2),
                "profit": profit
            })
            
        # 3. HTMLを返す（配当などは一旦省略して確実に表示させる）
        return render_template_string("""
        <html>
        <body style="font-family:sans-serif; padding:20px;">
            <h2>資産損益合計: ¥{{ "{:,}".format(total_profit) }}</h2>
            <table border="1" cellpadding="10" style="border-collapse:collapse; width:100%;">
                <tr style="background:#eee;"><th>銘柄</th><th>現在値</th><th>前日比</th><th>評価損益</th></tr>
                {% for r in results %}
                <tr>
                    <td>{{ r.name }}<br><small>{{ r.code }}</small></td>
                    <td align="right">{{ "{:,}".format(r.price|int) if r.price > 0 else '取得不可' }}</td>
                    <td align="right" style="color:{{ 'green' if r.change > 0 else 'red' }}">
                        {{ '+' if r.change > 0 }}{{ "{:,}".format(r.change|int) }} ({{ r.change_pct }}%)
                    </td>
                    <td align="right" style="color:{{ 'green' if r.profit >= 0 else 'red' }}">
                        {{ "{:,}".format(r.profit) }}
                    </td>
                </tr>
                {% endfor %}
            </table>
            <p><a href="/">画面を更新する</a></p>
        </body>
        </html>
        """, results=results, total_profit=total_profit)

    except Exception as e:
        return f"エラーが発生しました: {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
