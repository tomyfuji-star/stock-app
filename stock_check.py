from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import re
import os
from functools import lru_cache
from datetime import date
import requests

app = Flask(__name__)

# [cite_start]スプレッドシートのURL [cite: 1]
SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

# Yahooからのブロックを避けるための設定
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
})

def to_float(val):
    try:
        val = re.sub(r"[^\d.-]", "", str(val))
        return float(val) if val else 0.0
    except:
        return 0.0

def to_int(val):
    return int(round(to_float(val)))

@lru_cache(maxsize=128)
def get_current_price(code, today_str):
    """
    Yahoo Financeから株価を取得する
    引数エラーを避けるため today_str を受け取るように修正
    """
    try:
        # 数字だけのコードに .T を付けて日本株として扱う
        ticker_code = f"{code}.T" if code.isdigit() else f"{code}.T"
        t = yf.Ticker(ticker_code, session=session)

        # 履歴データから直近の終値を取得（infoよりエラーになりにくい）
        hist = t.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        
        # 履歴が取れない場合、fast_infoを試す
        return float(t.fast_info.last_price)
    except Exception as e:
        print(f"Yahoo Fetch Error ({code}): {e}")
        return 0.0

@app.route("/")
def index():
    try:
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        results = []
        total_profit = 0
        today_str = str(date.today()) # キャッシュ更新用の日付文字列

        for _, row in df.iterrows():
            code = str(row.get("証券コード", "")).strip()
            if not code or code.lower() == "nan":
                continue

            name = str(row.get("銘柄", "")).strip()
            buy_price = to_float(row.get("取得時"))
            qty = to_int(row.get("株数"))

            # 正しい引数で株価を取得
            price = get_current_price(code, today_str)
            
            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit

            results.append({
                "code": code,
                "name": name,
                "buy": f"{int(buy_price):,}",
                "qty": f"{qty:,}",
                "price": f"{int(price):,}" if price > 0 else "取得エラー",
                "profit": f"{profit:,}",
                "profit_raw": profit
            })
    except Exception as e:
        return f"システムエラー: {e}"

    return render_template_string("""
<!doctype html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>株価管理</title>
    <style>
        body { font-family: sans-serif; margin: 15px; background: #f4f7f6; }
        .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }
        th, td { padding: 12px; border: 1px solid #eee; text-align: center; }
        th { background: #333; color: white; }
        .plus { color: #28a745; font-weight: bold; }
        .minus { color: #dc3545; font-weight: bold; }
        .num { text-align: right; }
    </style>
</head>
<body>
    <div class="card">
        <small>合計損益</small>
        <h2 class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</h2>
    </div>
    <table>
        <tr><th>銘柄</th><th>現在価格</th><th>評価損益</th></tr>
        {% for r in results %}
        <tr>
            <td style="text-align:left;">{{ r.name }}<br><small>{{ r.code }}</small></td>
            <td class="num">{{ r.price }}</td>
            <td class="num">
                <span class="{{ 'plus' if r.profit_raw >= 0 else 'minus' }}">{{ r.profit }}</span><br>
                <small>{{ r.qty }}株</small>
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
""", results=results, total_profit=total_profit)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
