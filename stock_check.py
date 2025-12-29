from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import re

app = Flask(__name__)

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
    ticker = yf.Ticker(f"{code}.T")

    price = ticker.fast_info.get("last_price")
    if price and price > 0:
        return float(price)

    hist = ticker.history(period="1d")
    if not hist.empty:
        return float(hist["Close"].iloc[-1])

    return 0.0

@app.route("/")
def index():
    df = pd.read_csv(SPREADSHEET_CSV_URL)
    df.columns = df.columns.str.strip()

    required_cols = ["証券コード", "銘柄", "取得時", "株数"]
    for col in required_cols:
        if col not in df.columns:
            return f"<h3>列が見つかりません: {col}</h3><pre>{list(df.columns)}</pre>"

    results = []

    for _, row in df.iterrows():
        code = str(row["証券コード"]).strip()
        name = str(row["銘柄"]).strip()
        if not code or code.lower() == "nan":
            continue

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

    html = """
    <style>
      table { border-collapse: collapse; }
      th, td { padding: 6px 10px; border: 1px solid #ccc; }
      td.num { text-align: right; }
      .plus { color: green; font-weight: bold; }
      .minus { color: red; font-weight: bold; }
    </style>

    <h2>保有株一覧</h2>
    <table>
      <tr>
        <th>証券コード</th>
        <th>銘柄</th>
        <th>株数</th>
        <th>現在価格</th>
        <th>評価損益</th>
      </tr>
      {% for r in results %}
      <tr>
        <td>{{ r.code }}</td>
        <td>{{ r.name }}</td>
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
    app.run(host="0.0.0.0", port=5000)
