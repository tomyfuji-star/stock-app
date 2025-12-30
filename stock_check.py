from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import yfinance as yf
import re
import os

app = Flask(__name__)

SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

def to_float(val):
    try:
        val = re.sub(r"[^\d.-]", "", str(val))
        return float(val) if val else 0.0
    except:
        return 0.0

def get_stock_data(code):
    """
    history(1mo)を使って、直近価格と配当実績を一度に取得する最速メソッド
    """
    ticker_code = f"{code}.T"
    try:
        t = yf.Ticker(ticker_code)
        # 1ヶ月分のデータを一括取得（ここに配当情報も含まれる）
        hist = t.history(period="1mo")
        
        price = 0.0
        change = 0.0
        change_pct = 0.0
        dividend = 0.0

        if not hist.empty:
            # 最新の終値
            price = float(hist["Close"].iloc[-1])
            # 前日比
            if len(hist) >= 2:
                prev_price = float(hist["Close"].iloc[-2])
                change = price - prev_price
                change_pct = (change / prev_price * 100)
            
            # 配当計算：過去1年の配当履歴から合計（infoを使わないので速い）
            divs = t.dividends
            if not divs.empty:
                dividend = sum(divs.tail(2)) # 直近2回分

        return price, change, change_pct, dividend
    except:
        return 0.0, 0.0, 0.0, 0.0

@app.route("/")
def index():
    try:
        # スプレッドシートを読み込み
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        results = []
        total_profit = 0
        total_dividend_income = 0

        for _, row in df.iterrows():
            code = str(row.get("証券コード", "")).strip().upper()
            if not code or code == "NAN": continue

            name = str(row.get("銘柄", "")).strip()
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))

            # 1銘柄につき1回の通信で完結
            price, change, change_pct, dividend = get_stock_data(code)
            
            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit
            total_dividend_income += int(dividend * qty)

            results.append({
                "code": code, "name": name, "buy": buy_price, "qty": qty,
                "price": price, "change": change, "change_pct": round(change_pct, 2),
                "profit": profit,
                "yield_at_cost": round((dividend / buy_price * 100), 2) if buy_price > 0 else 0,
                "current_yield": round((dividend / price * 100), 2) if price > 0 else 0
            })
            
        return render_template_string("""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>株主管理</title>
    <style>
        body { font-family: sans-serif; margin: 10px; background: #f4f7f6; }
        .container { max-width: 600px; margin: auto; }
        .card-top { background: #fff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 15px; text-align: center; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .stock-card { background: #fff; padding: 12px; border-radius: 8px; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; }
        .plus { color: #28a745; font-weight: bold; }
        .minus { color: #dc3545; font-weight: bold; }
        .small { font-size: 0.75em; color: #777; }
    </style>
</head>
<body>
<div class="container">
    <div class="card-top">
        <div class="grid">
            <div><small>評価損益</small><br><span class="{{ 'plus' if total_profit >= 0 else 'minus' }}" style="font-size:1.2em;">¥{{ "{:,}".format(total_profit) }}</span></div>
            <div><small>予想配当</small><br><span style="font-size:1.2em; color:#007bff;">¥{{ "{:,}".format(total_dividend_income) }}</span></div>
        </div>
    </div>
    {% for r in results %}
    <div class="stock-card">
        <div>
            <strong>{{ r.name }}</strong> <span class="small">{{ r.code }}</span><br>
            <span class="small">{{ r.qty }}株 / 利回り {{ r.current_yield }}%</span>
        </div>
        <div style="text-align:right;">
            <strong>{{ "{:,}".format(r.price|int) if r.price > 0 else '---' }}</strong><br>
            <span class="{{ 'plus' if r.profit >= 0 else 'minus' }}" style="font-size:0.9em;">
                {{ "{:+,}".format(r.profit) if r.price > 0 else '' }}
            </span>
        </div>
    </div>
    {% endfor %}
    <p style="text-align:center;"><a href="/" style="color:#007bff; text-decoration:none;">更新する</a></p>
</div>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

    except Exception as e:
        return f"読み込み中... 再試行してください: {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
