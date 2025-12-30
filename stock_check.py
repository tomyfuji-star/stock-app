from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import yfinance as yf
import re
import os
from functools import lru_cache
from datetime import date
import requests

app = Flask(__name__)

# スプレッドシートのURL
SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

# 401エラー対策：ブラウザを装うための設定
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
def get_stock_data(code, today_str):
    ticker_code = f"{code}.T"
    try:
        # sessionを指定してアクセスを安定させる
        t = yf.Ticker(ticker_code, session=session)
        
        # 履歴データの取得（株価）
        hist = t.history(period="5d")
        
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0.0
        else:
            # 最終手段として info からの取得を試みるが、エラーなら0にする
            price = 0.0
            change, change_pct = 0.0, 0.0

        # 配当情報の取得（ここが最も401エラーが出やすい）
        dividend = 0.0
        try:
            # infoが取れない場合は t.dividends から直近の配当を推測する
            info = t.info
            dividend = info.get("dividendRate") or info.get("trailingAnnualDividendRate") or 0.0
            
            # それでも0の場合、もし配当実績があれば直近の値を採用（簡易計算）
            if dividend == 0:
                divs = t.dividends
                if not divs.empty:
                    # 日本株の場合、年2回配当が多いので直近2回分を合算
                    dividend = sum(divs.tail(2))
        except:
            dividend = 0.0
            
        return price, dividend, change, change_pct

    except Exception as e:
        print(f"ERROR fetching {code}: {e}")
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
            
            # 損益と利回りの計算
            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit
            total_dividend_income += int(dividend * qty)
            
            yield_at_cost = (dividend / buy_price * 100) if buy_price > 0 else 0.0
            current_yield = (dividend / price * 100) if price > 0 else 0.0

            results.append({
                "code": code,
                "name": name,
                "buy": buy_price,
                "qty": qty,
                "price": price,
                "change": change,
                "change_pct": round(change_pct, 2),
                "profit": profit,
                "yield_at_cost": round(yield_at_cost, 2),
                "current_yield": round(current_yield, 2)
            })
    except Exception as e:
        return f"システムエラー: {e}"

    # HTMLテンプレート (全項目表示、ソート、色分け機能付き)
    return render_template_string("""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>資産管理</title>
<style>
body { font-family: sans-serif; margin: 10px; background: #f4f7f6; }
.container { max-width: 900px; margin: auto; }
.header { display: flex; justify-content: space-between; align-items: center; }
.summary { display: flex; gap: 10px; margin-bottom: 15px; }
.card { flex: 1; background: #fff; padding: 10px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }
.card h3 { font-size: 0.8em; color: #666; margin: 0; }
.card p { font-size: 1.1em; font-weight: bold; margin: 5px 0 0; }
.btn { background: #007bff; color: #fff; text-decoration: none; padding: 5px 10px; border-radius: 4px; font-size: 0.8em; }
table { width: 100%; border-collapse: collapse; background: #fff; font-size: 0.85em; }
th, td { padding: 8px; border: 1px solid #eee; text-align: center; }
th { background: #333; color: #fff; cursor: pointer; }
.plus { color: #28a745; font-weight: bold; }
.minus { color: #dc3545; font-weight: bold; }
.num { text-align: right; }
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h2>資産管理</h2>
        <a href="/?refresh=1" class="btn">データ更新</a>
    </div>
    <div class="summary">
        <div class="card">
            <h3>合計損益</h3>
            <p class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</p>
        </div>
        <div class="card">
            <h3>配当合計</h3>
            <p style="color: #0056b3;">¥{{ "{:,}".format(total_dividend_income) }}</p>
        </div>
    </div>
    <table id="stockTable">
        <thead>
            <tr>
                <th onclick="sortTable(0)">銘柄</th>
                <th onclick="sortTable(1)">価格/株数</th>
                <th onclick="sortTable(2)">損益</th>
                <th onclick="sortTable(3)">取得利回り</th>
                <th onclick="sortTable(4)">現在利回り</th>
            </tr>
        </thead>
        <tbody>
            {% for r in results %}
            <tr>
                <td style="text-align:left;">{{ r.name }}<br><small>{{ r.code }}</small></td>
                <td class="num" data-value="{{ r.price }}">
                    {{ "{:,}".format(r.price|int) }}<br>
                    <small style="color:#666">{{ r.qty }}株</small>
                    <div class="{{ 'plus' if r.change > 0 else 'minus' if r.change < 0 else '' }}" style="font-size:0.8em;">
                        {{ '+' if r.change > 0 else '' }}{{ "{:,}".format(r.change|int) }} ({{ r.change_pct }}%)
                    </div>
                </td>
                <td class="num" data-value="{{ r.profit }}">
                    <span class="{{ 'plus' if r.profit >= 0 else 'minus' }}">{{ "{:,}".format(r.profit) }}</span>
                </td>
                <td class="num" data-value="{{ r.yield_at_cost }}">{{ r.yield_at_cost }}%</td>
                <td class="num" data-value="{{ r.current_yield }}" style="background:#f0faff;">{{ r.current_yield }}%</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
<script>
function sortTable(n) {
  var table = document.getElementById("stockTable");
  var rows = Array.from(table.rows).slice(1);
  var dir = table.getAttribute("data-dir") === "asc" ? "desc" : "asc";
  table.setAttribute("data-dir", dir);
  rows.sort((a, b) => {
    var valA = a.cells[n].getAttribute("data-value") || a.cells[n].innerText;
    var valB = b.cells[n].getAttribute("data-value") || b.cells[n].innerText;
    return dir === "asc" ? (valA > valB ? 1 : -1) : (valA < valB ? 1 : -1);
  });
  rows.forEach(row => table.tBodies[0].appendChild(row));
}
</script>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
