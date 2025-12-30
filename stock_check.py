from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import re
import os
from functools import lru_cache

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

# 🔥 キャッシュ（重要）
@lru_cache(maxsize=64)
def get_ticker(code):
    return yf.Ticker(f"{code}.T")

@lru_cache(maxsize=128)
def get_current_price(code):
    try:
        t = get_ticker(code)
        price = t.fast_info.get("last_price")
        return float(price) if price else 0.0
    except:
        return 0.0

@app.route("/")
def index():
    try:
        df = pd.read_csv(SPREADSHEET_CSV_URL)
    except Exception as e:
        return f"<h3>スプレッドシート取得失敗</h3><pre>{e}</pre>"

    results = []

    for _, row in df.iterrows():
        code = str(row.get("証券コード", "")).strip()
        if not code or code.lower() == "nan":
            continue

        name = str(row.get("銘柄", ""))
        buy_price = to_float(row.get("取得時"))
        qty = to_int(row.get("株数"))
        price = get_current_price(code)

        profit = int((price - buy_price) * qty)

        results.append({
            "code": code,
            "name": name,
            "buy_price": f"{int(buy_price):,}",
            "qty": f"{qty:,}",
            "price": f"{int(price):,}",
            "profit": f"{profit:,}",
            "profit_raw": profit
        })

    html = """
<style>
body { font-family: -apple-system; margin: 10px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 6px; border: 1px solid #ddd; }
th { background: #f5f5f5; }
td.num { text-align: right; }
.plus { color: green; font-weight: bold; }
.minus { color: red; font-weight: bold; }
</style>

<h2>保有株一覧</h2>
<table>
<tr>
<th>コード</th><th>銘柄</th><th>取得時</th><th>株数</th>
<th>現在</th><th>評価損益</th>
</tr>

{% for r in results %}
<tr>
<td>{{ r.code }}</td>
<td>{{ r.name }}</td>
<td class="num">{{ r.buy_price }}</td>
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
"""
    return render_template_string(html, results=results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.
