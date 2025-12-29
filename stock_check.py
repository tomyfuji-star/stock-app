from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import re

app = Flask(__name__)

# Googleスプレッドシート CSV（gid は必ず指定）
SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

# 数値正規化（最重要）
def to_float(val):
    if pd.isna(val):
        return 0.0
    val = str(val)
    val = re.sub(r"[^\d.-]", "", val)  # カンマ・円など除去
    return float(val) if val else 0.0

def to_int(val):
    return int(to_float(val))

@app.route("/")
def index():
    df = pd.read_csv(SPREADSHEET_CSV_URL)

    # 列名の空白・ズレ対策
    df.columns = df.columns.str.strip()

    results = []

    for _, row in df.iterrows():
        code = str(row["証券コード"]).strip()
        name = str(row["銘柄"]).strip()

        if not code or code.lower() == "nan":
            continue

        ticker = yf.Ticker(f"{code}.T")
        price = ticker.fast_info.get("last_price")

        buy_price = to_float(row["取得時"])
        qty = to_int(row["枚数"])

        if price is None:
            price = 0.0

        profit = (price - buy_price) * qty

        results.append({
            "code": code,
            "name": name,
            "qty": qty,
            "price": round(price, 2),
            "profit": round(profit, 0),
        })

    html = """
    <h2>保有株一覧</h2>
    <table border="1" cellpadding="6">
      <tr>
        <th>証券コード</th><th>銘柄</th><th>枚数</th>
        <th>現在価格</th><th>評価損益</th>
      </tr>
      {% for r in results %}
      <tr>
        <td>{{ r.code }}</td>
        <td>{{ r.name }}</td>
        <td>{{ r.qty }}</td>
        <td>{{ r.price }}</td>
        <td>{{ r.profit }}</td>
      </tr>
      {% endfor %}
    </table>
    """
    return render_template_string(html, results=results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
