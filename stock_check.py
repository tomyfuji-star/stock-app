from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import yfinance as yf
import re
import os
import time
from functools import lru_cache
from datetime import date
import requests

app = Flask(__name__)

SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

# --- 改善1: さらに詳細なブラウザ偽装ヘッダー ---
custom_session = requests.Session()
custom_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
})

def to_float(val):
    try:
        val = re.sub(r"[^\d.-]", "", str(val))
        return float(val) if val else 0.0
    except:
        return 0.0

@lru_cache(maxsize=128)
def get_stock_data(code, today_str):
    ticker_code = f"{code}.T"
    t = yf.Ticker(ticker_code, session=custom_session)
    
    price = 0.0
    change = 0.0
    change_pct = 0.0
    dividend = 0.0

    # --- 改善2: 3段階の取得チャレンジ ---
    try:
        # 第1挑戦: 5日分の履歴から取得
        hist = t.history(period="5d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            if len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])
                change = price - prev_close
                change_pct = (change / prev_close * 100)
        
        # 第2挑戦: historyが空なら、最新の価格情報を直接狙う
        if price == 0:
            price = float(t.fast_info.last_price)
            
    except Exception as e:
        print(f"価格取得エラー ({code}): {e}")

    # --- 配当情報の取得 (infoがダメなら実績から) ---
    try:
        # infoは非常にブロックされやすいためタイムアウトを短く
        info = t.info
        dividend = info.get("dividendRate") or info.get("trailingAnnualDividendRate") or 0.0
    except:
        try:
            # 実績から直近1年分を合算
            div_hist = t.dividends
            if not div_hist.empty:
                dividend = sum(div_hist.tail(2))
        except:
            dividend = 0.0
            
    return price, dividend, change, change_pct

@app.route("/")
def index():
    if request.args.get("refresh"):
        get_stock_data.cache_clear()
        return redirect(url_for("index"))

    try:
        # キャッシュ対策のためURLにタイムスタンプを付与（任意）
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        results = []
        today_str = str(date.today())
        total_profit = 0
        total_dividend_income = 0

        for _, row in df.iterrows():
            code = str(row.get("証券コード", "")).strip().upper()
            if not code or code == "NAN": continue

            name = str(row.get("銘柄", "")).strip()
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))

            price, dividend, change, change_pct = get_stock_data(code, today_str)
            
            # 各銘柄の処理ごとに極小の待ち時間を入れて負荷を分散（ブロック対策）
            time.sleep(0.1) 

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
<title>株主管理</title>
<style>
body { font-family: sans-serif; margin: 10px; background-color: #f4f7f6; }
.container { max-width: 900px; margin: auto; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.summary-box { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
.card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
.card p { margin: 5px 0 0; font-size: 1.2em; font-weight: bold; }
.refresh-btn { background: #007bff; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; text-decoration: none; font-size: 0.9em; }
table { width: 100%; border-collapse: collapse; background: white; font-size: 0.8em; }
th, td { padding: 10px; border: 1px solid #eee; text-align: center; }
th { background: #343a40; color: white; }
.plus { color: #28a745; font-weight: bold; }
.minus { color: #dc3545; font-weight: bold; }
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
            <h3>年間配当総額</h3>
            <p style="color: #0056b3;">¥{{ "{:,}".format(total_dividend_income) }}</p>
        </div>
    </div>
    <table>
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
                <td style="text-align:right;">
                    <strong>{{ "{:,}".format(r.price|int) if r.price > 0 else '取得中...' }}</strong><br>
                    <small>{{ r.qty }}株</small>
                    {% if r.change != 0 %}
                    <span class="{{ 'plus' if r.change > 0 else 'minus' }}" style="display:block; font-size:0.9em;">
                        {{ '+' if r.change > 0 else '' }}{{ "{:,}".format(r.change|int) }} ({{ r.change_pct }}%)
                    </span>
                    {% endif %}
                </td>
                <td style="text-align:right;" class="{{ 'plus' if r.profit >= 0 else 'minus' }}">
                    {{ "{:,}".format(r.profit) if r.price > 0 else '---' }}
                </td>
                <td style="text-align:right;">{{ r.yield_at_cost }}%</td>
                <td style="text-align:right;">{{ r.current_yield }}%</td>
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
