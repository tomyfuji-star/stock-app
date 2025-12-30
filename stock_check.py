from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import re
import os
from functools import lru_cache
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

def to_int(val):
    return int(round(to_float(val)))

# 修正ポイント：価格と配当金を同時に取得するように変更
@lru_cache(maxsize=128)
def get_stock_data(code, today_str):
    try:
        ticker_code = f"{code}.T"
        t = yf.Ticker(ticker_code)
        
        # 価格の取得
        hist = t.history(period="1d")
        price = float(hist["Close"].iloc[-1]) if not hist.empty else 0.0
        
        # 配当金の取得 (yfinanceのinfoから年間配当額を取得)
        # 取得できない場合は 0.0 を設定
        info = t.info
        dividend = info.get("dividendRate") or 0.0
        
        return price, dividend
    except Exception as e:
        print(f"ERROR for {code}: {e}")
        return 0.0, 0.0

@app.route("/")
def index():
    try:
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        results = []
        today_str = str(date.today())

        for _, row in df.iterrows():
            code = str(row.get("証券コード", "")).strip()
            if not code or code.lower() == "nan" or not code.isdigit():
                continue

            name = str(row.get("銘柄", "")).strip()
            buy_price = to_float(row.get("取得時"))
            qty = to_int(row.get("株数"))

            # 価格と配当を取得
            price, dividend = get_stock_data(code, today_str)
            
            # 評価損益の計算
            profit = int((price - buy_price) * qty)
            
            # 取得時利回りの計算 (配当金 / 取得単価 * 100)
            yield_at_cost = (dividend / buy_price * 100) if buy_price > 0 else 0.0

            results.append({
                "code": code,
                "name": name,
                "buy": f"{int(buy_price):,}",
                "qty": f"{qty:,}",
                "price": f"{int(price):,}",
                "profit": f"{profit:,}",
                "profit_raw": profit,
                "dividend": dividend,
                "yield": f"{yield_at_cost:.2f}" # 小数点2位まで表示
            })
    except Exception as e:
        return f"エラーが発生しました: {e}"

    return render_template_string("""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>保有株・配当管理</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 10px; background-color: #f8f9fa; }
h2 { text-align: center; color: #333; }
table { width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.1); font-size: 0.9em; }
th, td { padding: 8px; border: 1px solid #dee2e6; text-align: center; }
th { background: #e9ecef; }
td.num { text-align: right; font-family: monospace; }
.plus { color: #28a745; font-weight: bold; }
.minus { color: #dc3545; font-weight: bold; }
.yield-val { color: #0056b3; font-weight: bold; }
</style>
</head>
<body>
<h2>保有株・配当一覧</h2>
<table>
<tr>
<th>コード</th>
<th>銘柄</th>
<th>取得単価</th>
<th>株数</th>
<th>現在値</th>
<th>評価損益</th>
<th>予想配当</th>
<th>取得時利回り</th>
</tr>
{% for r in results %}
<tr>
<td>{{ r.code }}</td>
<td>{{ r.name }}</td>
<td class="num">{{ r.buy }}</td>
<td class="num">{{ r.qty }}</td>
<td class="num">{{ r.price }}</td>
<td class="num">
<span class="{{ 'plus' if r.profit_raw >= 0 else 'minus' }}">
{{ r.profit }}
</span>
</td>
<td class="num">¥{{ r.dividend }}</td>
<td class="num"><span class="yield-val">{{ r.yield }}%</span></td>
</tr>
{% endfor %}
</table>
</body>
</html>
""", results=results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
