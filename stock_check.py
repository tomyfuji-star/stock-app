from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import math

app = Flask(__name__)

# ===== Googleスプレッドシート =====
SHEET_ID = "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
GID = "1052470389"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

# ===== util =====
def to_float(v):
    try:
        return float(v)
    except:
        return 0.0

def fmt(v):
    if v is None:
        return "—"
    try:
        return f"{int(round(v)):,}"
    except:
        return "—"

# ===== HTML =====
HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>株チェック</title>
<style>
 body { font-family: sans-serif; padding:20px; }
 table { border-collapse: collapse; width:100%; }
 th, td { border:1px solid #ccc; padding:8px; }
 th { background:#f0f0f0; }
 td.num { text-align:right; }
 .plus { color:green; font-weight:bold; }
 .minus { color:red; font-weight:bold; }
</style>
</head>
<body>
<h2>保有株一覧</h2>
<table>
<tr>
<th>証券コード</th>
<th>銘柄</th>
<th>取得時</th>
<th>枚数</th>
<th>現在価格</th>
<th>評価損益</th>
</tr>
{% for r in rows %}
<tr>
<td>{{ r.code }}</td>
<td>{{ r.name }}</td>
<td class="num">{{ r.buy }}</td>
<td class="num">{{ r.qty }}</td>
<td class="num">{{ r.price }}</td>
<td class="num">
{% if r.profit_raw is not none %}
<span class="{{ 'plus' if r.profit_raw >= 0 else 'minus' }}">
{{ r.profit }}
</span>
{% else %}
—
{% endif %}
</td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""

@app.route("/")
def index():
    try:
        df = pd.read_csv(CSV_URL)
    except Exception as e:
        return f"スプレッドシート読込失敗: {e}"

    rows = []

    for _, row in df.iterrows():
        try:
            code = str(row["証券コード"]).strip()
            name = str(row["銘柄"]).strip()
            buy = to_float(row["取得時"])
            qty = to_float(row["枚数"])

            price = None
            profit = None

            try:
                t = yf.Ticker(f"{code}.T")
                price = t.fast_info.get("last_price")
                if price is not None:
                    profit = (price - buy) * qty
            except:
                pass  # ← ここが超重要（500防止）

            rows.append({
                "code": code,
                "name": name,
                "buy": fmt(buy),
                "qty": fmt(qty),
                "price": fmt(price),
                "profit": fmt(profit),
                "profit_raw": profit
            })

        except:
            continue

    return render_template_string(HTML, rows=rows)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
