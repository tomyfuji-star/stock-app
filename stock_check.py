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
    try:
        if pd.isna(val):
            return 0.0
        val = re.sub(r"[^\d.-]", "", str(val))
        return float(val) if val else 0.0
    except Exception:
        return 0.0

def to_int(val):
    try:
        return int(to_float(val))
    except Exception:
        return 0

@app.route("/")
def index():
    try:
        df = pd.read_csv(SPREADSHEET_CSV_URL)
    except Exception as e:
        return f"<h3>CSV読み込みエラー</h3><pre>{e}</pre>"

    # 列名正規化
    df.columns = df.columns.str.strip()

    required_cols = ["証券コード", "銘柄", "取得時", "枚数"]
    for col in required_cols:
        if col not in df.columns:
            return f"<h3>列が見つかりません: {col}</h3><pre>{list(df.columns)}</pre>"

    results = []

    for i, row in df.iterrows():
        try:
            code = str(row["証券コード"]).strip()
            name = str(row["銘柄"]).strip()

            if not code or code.lower() == "nan":
                continue

            buy_price = to_float(row["取得時"])
            qty = to_int(row["枚数"])

            ticker = yf.Ticker(f"{code}.T")
            price = ticker.fast_info.get("last_price") or 0.0

            profit = (price - buy_price) * qty

            results.append({
                "code": code,
                "name": name,
                "qty": qty,
                "price": round(price, 2),
                "profit": round(profit, 0),
            })

        except Exception as e:
            # 1行壊れても続行
            results.append({
                "code": "ERROR",
                "name": f"row {i}",
                "qty": 0,
                "price": 0,
                "profit": 0,
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
