from flask import Flask, render_template_string
import pandas as pd
import requests

app = Flask(__name__)

# ===== Google Spreadsheet =====
SHEET_ID = "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
GID = "1052470389"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

# ===== Utils =====
def to_float(v):
    if pd.isna(v):
        return 0.0
    try:
        return float(v)
    except:
        return 0.0

def fmt(v):
    if v is None:
        return "—"
    return f"{round(v):,}"

# ===== Yahoo Finance (API直叩き) =====
def get_price(code):
    try:
        url = "https://query1.finance.yahoo.com/v7/finance/quote"
        r = requests.get(
            url,
            params={"symbols": f"{code}.T"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        )

        data = r.json()
        result = data.get("quoteResponse", {}).get("result", [])
        if not result:
            return None

        q = result[0]

        # 市場時間中
        if q.get("regularMarketPrice") is not None:
            return q["regularMarketPrice"]

        # 市場時間外
        return q.get("regularMarketPreviousClose")

    except Exception as e:
        print("price error:", e)
        return None

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

# ===== Flask =====
@app.route("/")
def index():
    df = pd.read_csv(CSV_URL)

    required_cols = ["証券コード", "銘柄", "取得時", "株数"]
    for c in required_cols:
        if c not in df.columns:
            return f"列が見つかりません: {c}<br>{list(df.columns)}"

    rows = []

    for _, row in df.iterrows():
        code = str(row["証券コード"]).strip()
        if not code:
            continue

        name = str(row["銘柄"])
        buy = to_float(row["取得時"])
        qty = to_float(row["株数"])

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
