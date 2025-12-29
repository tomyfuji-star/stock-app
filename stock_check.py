from flask import Flask, render_template_string
import pandas as pd
import requests

app = Flask(__name__)

# ===== Google Sheet =====
SHEET_ID = "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
GID = "1052470389"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

def to_float(v):
    try:
        return float(v)
    except:
        return 0.0

def fmt(v):
    if v is None:
        return "—"
    try:
        return f"{round(v):,}"
    except:
        return "—"

def get_price(code):
    try:
        url = "https://query1.finance.yahoo.com/v7/finance/quote"
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        r = requests.get(
            url,
            params={"symbols": f"{code}.T"},
            headers=headers,
            timeout=5
        )
        data = r.json()
        result = data.get("quoteResponse", {}).get("result", [])
        if not result:
            return None

        quote = result[0]

        # 市場時間中 → 現在価格
        price = quote.get("regularMarketPrice")

        # 市場時間外 → 前日終値
        if price is None:
            price = quote.get("regularMarketPreviousClose")

        return price

    except Exception as e:
        print("price error:", e)
        return None


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
<th>株数</th>
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
{% else %}—{% endif %}
</td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""

@app.route("/")
def index():
    df = pd.read_csv(CSV_URL)

    qty_col = "株数" if "株数" in df.columns else "枚数"
    rows = []

    for _, row in df.iterrows():
        code = str(row.get("証券コード", "")).strip()
        if not code:
            continue

        name = str(row.get("銘柄", ""))
        buy = to_float(row.get("取得時", 0))
        qty = to_float(row.get(qty_col, 0))

        price = get_price(code)
        profit = (price - buy) * qty if price is not None else None

        rows.append({
            "code": code,
            "name": name,
            "buy": fmt(buy),
            "qty": fmt(qty),
            "price": fmt(price),
            "profit": fmt(profit),
            "profit_raw": profit
        })

    return render_template_string(HTML, rows=rows)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
