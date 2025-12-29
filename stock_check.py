from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import math

app = Flask(__name__)

# ====== Googleスプレッドシート設定 ======
SHEET_ID = "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
GID = "1052470389"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

# ====== ユーティリティ ======
def to_float(v):
    try:
        if pd.isna(v):
            return 0.0
        return float(v)
    except:
        return 0.0

def round_int(v):
    if v is None or math.isnan(v):
        return 0
    return int(round(v))

# ====== HTML ======
HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>株チェック</title>
<style>
  body { font-family: sans-serif; padding: 20px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 8px; }
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
  <th>証券コード</th>
  <th>銘柄</th>
  <th>取得時</th>
  <th>枚数</th>
  <th>現在価格</th>
  <th>評価損益</th>
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
</body>
</html>
"""

# ====== メイン ======
@app.route("/")
def index():
    # スプレッドシート読込
    df = pd.read_csv(CSV_URL)

    results = []

    for _, row in df.iterrows():
        code = str(row["証券コード"]).strip()
        name = str(row["銘柄"]).strip()
        buy_price = to_float(row["取得時"])
        qty = to_float(row["枚数"])

        if code == "" or qty == 0:
            continue

        # 日本株は .T
        ticker = yf.Ticker(f"{code}.T")
        price = ticker.fast_info.get("last_price")

        if price is None or math.isnan(price):
            price = 0.0

        profit = (price - buy_price) * qty

        results.append({
            "code": code,
            "name": name,
            "buy_price": f"{round_int(buy_price):,}",
            "qty": f"{round_int(qty):,}",
            "price": f"{round_int(price):,}",
            "profit": f"{round_int(profit):,}",
            "profit_raw": profit
        })

    return render_template_string(HTML, results=results)

# ====== 起動 ======
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
