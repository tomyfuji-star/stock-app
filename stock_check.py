from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf

app = Flask(__name__)

CSV_URL = "https://docs.google.com/spreadsheets/d/1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M/export?format=csv&gid=1052470389"

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>保有株一覧</title>
<style>
table { border-collapse: collapse; }
th, td { border: 1px solid #444; padding: 6px 10px; }
</style>
</head>
<body>
<h1>保有株一覧</h1>
<table>
<tr>
<th>銘柄コード</th>
<th>取得価格</th>
<th>現在価格</th>
<th>損益率(%)</th>
</tr>
{% for r in rows %}
<tr>
<td>{{ r.code }}</td>
<td>{{ r.buy }}</td>
<td>{{ r.now }}</td>
<td>{{ r.rate }}</td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""

@app.route("/")
def index():
    df = pd.read_csv(
        CSV_URL,
        skiprows=2,
        names=["証券コード", "銘柄", "株価", "取得時"]
    )

    rows = []

    for _, row in df.iterrows():
        code = str(row["証券コード"]).strip()
        if not code:
            continue

        ticker = yf.Ticker(f"{code}.T")
        hist = ticker.history(period="1d")

        if hist.empty:
            now_price = "-"
        else:
            now_price = round(hist["Close"].iloc[-1], 1)

        buy_price = pd.to_numeric(row["取得時"], errors="coerce")

        if pd.notna(buy_price) and isinstance(now_price, (int, float)):
            rate = round((now_price - buy_price) / buy_price * 100, 2)
        else:
            rate = "-"

        rows.append({
            "code": code,
            "buy": "-" if pd.isna(buy_price) else buy_price,
            "now": now_price,
            "rate": rate
        })

    return render_template_string(HTML, rows=rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
