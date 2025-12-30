from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import re
import os

app = Flask(__name__)

SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

def to_float(val):
    try:
        if pd.isna(val):
            return 0.0
        val = re.sub(r"[^\d.-]", "", str(val))
        return float(val) if val else 0.0
    except:
        return 0.0

def to_int(val):
    try:
        return int(round(to_float(val)))
    except:
        return 0

def get_current_price(code):
    try:
        ticker = yf.Ticker(f"{code}.T")
        price = ticker.fast_info.get("last_price")
        if price and price > 0:
            return float(price)
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except:
        pass
    return 0.0

def get_annual_dividend(code):
    try:
        ticker = yf.Ticker(f"{code}.T")
        divs = ticker.dividends
        if divs is None or divs.empty:
            return 0.0

        divs.index = divs.index.tz_localize(None)
        one_year_ago = pd.Timestamp.now() - pd.DateOffset(years=1)
        annual = divs[divs.index >= one_year_ago].sum()
        return float(annual)
    except:
        return 0.0

@app.route("/")
def index():
    df = pd.read_csv(SPREADSHEET_CSV_URL)
    df.columns = df.columns.str.strip()

    results = []

    for _, row in df.iterrows():
        code = str(row.get("証券コード", "")).strip()
        if not code or code.lower() == "nan":
            continue

        name = str(row.get("銘柄", "")).strip()
        buy_price = round(to_float(row.get("取得時")))
        qty = to_int(row.get("株数"))

        price = round(get_current_price(code))
        profit = (price - buy_price) * qty

        annual_div = round(get_annual_dividend(code), 2)
        yoc = round((annual_div / buy_price) * 100, 2) if buy_price > 0 else 0.0

        results.append({
            "code": code,
            "name": name,
            "buy_price": f"{buy_price:,}",
            "qty": f"{qty:,}",
            "price": f"{price:,}",
            "profit": f"{profit:,}",
            "profit_raw": profit,
            "annual_div": f"{annual_div:.2f}",
            "yoc": f"{yoc:.2f}%"
        })

    html = """
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 10px; }
table { width: 100%; border-collapse: collapse; border: 1px solid #ddd; }
th, td { padding: 6px; border: 1px solid #ddd; }
th { background: #f5f5f5; }
td.num { text-align: right; }
.plus { color: green; font-weight: bold; }
.minus { color: red; font-weight: bold; }
@media (max-width: 600px) {
  body { font-size: 14px; }
}
</style>

<h2>保有株一覧</h2>

<table>
<tr>
  <th>証券コード</th>
  <th>銘柄</th>
  <th>取得時</th>
  <th>株数</th>
  <th>現在価格</th>
  <th>評価損益</th>
  <th>年間配当</th>
  <th>取得利回り</th>
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
  <td class="num">{{ r.annual_div }}</td>
  <td class="num">{{ r.yoc }}</td>
</tr>
{% endfor %}
</table>
"""
    return render_template_string(html, results=results)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
