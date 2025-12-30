from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import yfinance as yf
import re
import os
from datetime import date

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

def get_stock_full_data(code):
    """
    価格と配当をyfinanceから取得する。
    エラーを最小限にするためセッション設定はyfに任せる。
    """
    ticker_code = f"{code}.T"
    try:
        t = yf.Ticker(ticker_code)
        # 価格情報の取得 (5日分履歴)
        hist = t.history(period="5d")
        
        price = 0.0
        change = 0.0
        change_pct = 0.0
        dividend = 0.0

        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            if len(hist) >= 2:
                prev_price = float(hist["Close"].iloc[-2])
                change = price - prev_price
                change_pct = (change / prev_price * 100)
        
        # 配当情報の取得 (infoが重い/エラーになる場合はdividendsから計算)
        try:
            # 直近の配当履歴から年換算（直近2回分）
            div_history = t.dividends
            if not div_history.empty:
                dividend = sum(div_history.tail(2))
        except:
            dividend = 0.0

        print(f"FETCHED: {code} (Price: {price}, Div: {dividend})")
        return price, change, change_pct, dividend

    except Exception as e:
        print(f"ERROR: {code} - {str(e)}")
        return 0.0, 0.0, 0.0, 0.0

@app.route("/")
def index():
    try:
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

            price, change, change_pct, dividend = get_stock_full_data(code)
            
            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit
            total_dividend_income += int(dividend * qty)

            yield_at_cost = (dividend / buy_price * 100) if buy_price > 0 else 0.0
            current_yield = (dividend / price * 100) if price > 0 else 0.0

            results.append({
                "code": code, "name": name, "buy": buy_price, "qty": qty,
                "price": price, "change": change, "change_pct": round(change_pct, 2),
                "profit": profit, "dividend": dividend,
                "yield_at_cost": round(yield_at_cost, 2),
                "current_yield": round(current_yield, 2)
            })
            
        return render_template_string("""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>株主管理ダッシュボード</title>
    <style>
        body { font-family: -apple-system, sans-serif; margin: 10px; background-color: #f4f7f6; color: #333; }
        .container { max-width: 800px; margin: auto; }
        .summary-box { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .card { background: white; padding: 15px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }
        .card h3 { margin: 0; font-size: 0.8em; color: #777; }
        .card p { margin: 5px 0 0; font-size: 1.2em; font-weight: bold; }
        .plus { color: #28a745; }
        .minus { color: #dc3545; }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; font-size: 0.85em; }
        th { background: #343a40; color: white; padding: 12px 8px; }
        td { padding: 12px 8px; border-bottom: 1px solid #eee; }
        .num { text-align: right; font-family: 'Helvetica Neue', sans-serif; }
        .code-label { font-size: 0.7em; color: #888; }
        .refresh-area { text-align: center; margin-top: 20px; }
        .btn { text-decoration: none; background: #007bff; color: white; padding: 10px 20px; border-radius: 20px; font-size: 0.9em; }
    </style>
</head>
<body>
<div class="container">
    <h2 style="text-align:center;">My Portfolio</h2>
    
    <div class="summary-box">
        <div class="card">
            <h3>評価損益</h3>
            <p class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</p>
        </div>
        <div class="card">
            <h3>年間予想配当</h3>
            <p style="color: #0056b3;">¥{{ "{:,}".format(total_dividend_income) }}</p>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>銘柄</th>
                <th>現在値 / 損益</th>
                <th>取得 / 現在利回り</th>
            </tr>
        </thead>
        <tbody>
            {% for r in results %}
            <tr>
                <td>
                    <strong>{{ r.name }}</strong><br>
                    <span class="code-label">{{ r.code }} / {{ r.qty }}株</span>
                </td>
                <td class="num">
                    <strong>{{ "{:,}".format(r.price|int) if r.price > 0 else '---' }}</strong>
                    <br>
                    <span class="{{ 'plus' if r.profit >= 0 else 'minus' }}" style="font-size: 0.9em;">
                        {{ "{:+,}".format(r.profit) if r.price > 0 else '' }}
                    </span>
                </td>
                <td class="num">
                    <span style="color:#666;">取得: {{ r.yield_at_cost }}%</span><br>
                    <strong>現在: {{ r.current_yield }}%</strong>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <div class="refresh-area">
        <a href="/" class="btn">最新情報に更新</a>
    </div>
</div>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

    except Exception as e:
        return f"エラー: {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
