from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import yfinance as yf
import re
import os
from functools import lru_cache
from datetime import date
import requests

app = Flask(__name__)

# スプレッドシートのURL（変更なし）
SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

# --- 改善1: ブラウザを装うセッション ---
custom_session = requests.Session()
custom_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
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
def get_stock_data(code, today_str):
    try:
        ticker_code = f"{code}.T"
        t = yf.Ticker(ticker_code, session=custom_session)
        
        # --- 改善2: 最大5日分の履歴を取得して「最新の終値」を拾う ---
        hist = t.history(period="5d")
        
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            if len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])
                change = price - prev_close
                change_pct = (change / prev_close * 100)
            else:
                change, change_pct = 0.0, 0.0
        else:
            price, change, change_pct = 0.0, 0.0, 0.0

        # --- 改善3: 配当情報の取得強化 ---
        dividend = 0.0
        try:
            info = t.info
            dividend = info.get("dividendRate") or info.get("trailingAnnualDividendRate") or 0.0
            if dividend == 0:
                div_hist = t.dividends
                if not div_hist.empty:
                    # 直近2回（半年配当×2）を年額とする
                    dividend = sum(div_hist.tail(2))
        except:
            pass
            
        return price, dividend, change, change_pct

    except Exception as e:
        print(f"ERROR for {code}: {e}")
        return 0.0, 0.0, 0.0, 0.0

@app.route("/")
def index():
    if request.args.get("refresh"):
        get_stock_data.cache_clear()
        return redirect(url_for("index"))

    try:
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        results = []
        today_str = str(date.today())
        total_profit = 0
        total_dividend_income = 0

        for _, row in df.iterrows():
            code = str(row.get("証券コード", "")).strip().upper()
            if not code or code == "NAN":
                continue

            name = str(row.get("銘柄", "")).strip()
            buy_price = to_float(row.get("取得時"))
            qty = to_int(row.get("株数"))

            price, dividend, change, change_pct = get_stock_data(code, today_str)
            
            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit
            total_dividend_income += int(dividend * qty)
            
            yield_at_cost = (dividend / buy_price * 100) if buy_price > 0 else 0.0
            current_yield = (dividend / price * 100) if price > 0 else 0.0

            results.append({
                "code": code, "name": name, "buy": buy_price, "qty": qty,
                "price": price, "change": change, "change_pct": round(change_pct, 2),
                "profit": profit, "yield_at_cost": round(yield_at_cost, 2), "current_yield": round(current_yield, 2)
            })
    except Exception as e:
        return f"読み込みエラー: {e}"

    return render_template_string("""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>株主管理ダッシュボード</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 10px; background-color: #f4f7f6; }
.container { max-width: 1000px; margin: auto; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.summary-box { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
.card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
.card h3 { margin: 0; font-size: 0.8em; color: #666; }
.card p { margin: 5px 0 0; font-size: 1.2em; font-weight: bold; }
.refresh-btn { background: #007bff; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; text-decoration: none; font-size: 0.9em; }
table { width: 100%; border-collapse: collapse; background: white; font-size: 0.8em; }
th, td { padding: 10px; border: 1px solid #eee; text-align: center; }
th { background: #343a40; color: white; position: relative; }
td.num { text-align: right; font-family: monospace; }
.plus { color: #28a745; font-weight: bold; }
.minus { color: #dc3545; font-weight: bold; }
.diff-small { font-size: 0.85em; display: block; margin-top: 2px; }
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h2>保有株管理</h2>
        <a href="/?refresh=1" class="refresh-btn">最新情報に更新</a>
    </div>
    <div class="summary-box">
        <div class="card">
            <h3>合計評価損益</h3>
            <p class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</p>
        </div>
        <div class="card">
            <h3>年間予想配当総額</h3>
            <p style="color: #0056b3;">¥{{ "{:,}".format(total_dividend_income) }}</p>
        </div>
    </div>
    <table id="stockTable">
        <thead>
            <tr>
                <th>銘柄</th>
                <th>現在値 / 株数</th>
                <th>評価損益</th>
                <th>取得利回り</th>
                <th>現在利回り</th>
            </tr>
        </thead>
        <tbody>
            {% for r in results %}
            <tr>
                <td style="text-align:left;"><strong>{{ r.name }}</strong><br><small>{{ r.code }}</small></td>
                <td class="num">
                    <strong>{{ "{:,}".format(r.price|int) if r.price > 0 else '取得不可' }}</strong><br>
                    <small style="color:#666">{{ r.qty }}株</small>
                    <span class="diff-small {{ 'plus' if r.change > 0 else 'minus' if r.change < 0 else '' }}">
                        {{ '+' if r.change > 0 else '' }}{{ "{:,}".format(r.change|int) if r.change != 0 else '' }} ({{ r.change_pct if r.change_pct != 0 else '' }}%)
                    </span>
                </td>
                <td class="num">
                    <span class="{{ 'plus' if r.profit >= 0 else 'minus' }}">{{ "{:,}".format(r.profit) if r.price > 0 else '---' }}</span>
                </td>
                <td class="num">{{ r.yield_at_cost }}%</td>
                <td class="num" style="background: #f0f8ff;">{{ r.current_yield }}%</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
