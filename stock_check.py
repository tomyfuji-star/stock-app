import os
from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import re

app = Flask(__name__)

PORT = int(os.environ.get("PORT", 5000))

SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

def to_float(val):
    if pd.isna(val):
        return 0.0
    val = re.sub(r"[^\d.-]", "", str(val))
    return float(val) if val else 0.0

def to_int(val):
    return int(round(to_float(val)))

def get_current_price(code):
    try:
        ticker = yf.Ticker(f"{code}.T")
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return 0.0

@app.route("/")
def index():
    df = pd.read_csv(SPREADSHEET_CSV_URL)
    df.columns = df.columns.str.strip()

    results = []

    for _, row in df.iterrows():
        code = str(row["証券コード"]).strip()
        if not code or code.lower() == "nan":
            continue

        name = str(row["銘柄"]).strip()
        buy_price = to_float(row["取得時"])
        qty = to_int(row["株数"])

        price = round(get_current_price(code))
        profit = round((price - buy_price) * qty)

        results.append({
            "code": code,
            "name": name,
            "qty": f"{qty:,}",
            "price": f"{price:,}",
            "profit": f"{profit:,}",
            "profit_raw": profit,
        })

    return render_template_string("""
    <h2>保有株一覧</h2>
    <table border="1" cellpadding="6">
      <tr>
        <th>コード</th><th>銘柄</th><th>株数</th><th>現在価格</th><th>損益</th>
      </tr>
      {% for r in results %}
      <tr>
        <td>{{ r.code }}</td>
        <td>{{ r.name }}</td>
        <td align="right">{{ r.qty }}</td>
        <td align="right">{{ r.price }}</td>
        <td align="right">{{ r.profit }}</td>
      </tr>
      {% endfor %}
    </table>
    """, results=results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
