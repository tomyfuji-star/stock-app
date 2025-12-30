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

@lru_cache(maxsize=128)
def get_current_price(code, today):
    try:
        t = yf.Ticker(f"{code}.T")

        # ① info（8306はここに入ることがある）
        info = t.info
        price = info.get("regularMarketPrice")
        if price and price > 0:
            return float(price)

        # ② 5日分取得 → 最終日
        hist = t.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].dropna().iloc[-1])

        return 0.0
    except Exception as e:
        print("PRICE ERROR", code, e)
        return 0.0



@app.route("/")
def index():
    df = pd.read_csv(SPREADSHEET_CSV_URL)
    results = []

    today = date.today()

    for _, row in df.iterrows():
        code = str(row.get("証券コード", "")).strip()
        if not code or code.lower() == "nan":
            continue

        name = str(row.get("銘柄", "")).strip()
        buy_price = to_float(row.get("取得時"))
        qty = to_int(row.get("株数"))

        price = get_current_price(code, today)
        profit = int((price - buy_price) * qty)

        results.append({
            "code": code,
            "name": name,
            "buy": f"{int(buy_price):,}",
            "qty": f"{qty:,}",
            "price": f"{int(price):,}",
            "profit": f"{profit:,}",
            "profit_raw": profit
        })

    return render_template_string("""
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 10px; }
table { width: 100%; border-collapse: collapse; border: 1px solid #ddd; }
th, td { padding: 6px; border: 1px solid #ddd; }
th { background: #f5f5f5; }
td.num { text-align: right; }
.plus { color: green; font-weight: bold; }
.minus { color: red; font-weight: bold; }
</style>
</head>
<body>
<h2>保有株一覧</h2>
<table>
<tr>
<th>コード</th>
<th>銘柄</th>
<th>取得時</th>
<th>株数</th>
<th>現在価格</th>
<th>評価損益</th>
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
</tr>
{% endfor %}
</table>
</body>
</html>
""", results=results)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
