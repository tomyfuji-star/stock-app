from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import math

app = Flask(__name__)

SPREADSHEET_ID = "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
SHEET_GID = "1052470389"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={SHEET_GID}"

HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>株価チェック</title>
<style>
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ccc; padding: 8px; text-align: center; }
th { background: #f5f5f5; }
.plus { color: green; }
.minus { color: red; }
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
{% for r in data %}
<tr>
  <td>{{ r.code }}</td>
  <td>{{ r.name }}</td>
  <td>{{ r.buy_price }}</td>
  <td>{{ r.qty }}</td>
  <td>{{ r.current_price }}</td>
  <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}">{{ r.profit }}</td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""

def to_float(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return 0.0
    try:
        return float(str(v).replace(",", "").strip())
    except:
        return 0.0

def to_int(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return 0
    try:
        s = str(v)
        s = s.replace(",", "").replace("株", "").replace("枚", "").strip()
        return int(float(s))
    except:
        return 0

@app.route("/")
def index():
    df = pd.read_csv(
        CSV_URL,
        engine="python",
        on_bad_lines="skip"
    )

    results = []

    for _, row in df.iterrows():
        code_raw = str(row.get("証券コード", "")).strip()
        if not code_raw:
            continue

        # ✅ 日本株は .T を付与
        code = code_raw if code_raw.endswith(".T") else f"{code_raw}.T"

        name = str(row.get("銘柄", "")).strip()
        buy_price = to_float(row.get("取得時"))
        qty = to_int(row.get("枚数"))

        # 株価取得
        try:
            ticker = yf.Ticker(code)
            hist = ticker.history(period="1d")
            current = round(hist["Close"].iloc[-1], 2) if not hist.empty else 0.0
        except:
            current = 0.0

        profit = round((current - buy_price) * qty, 2)

        results.append({
            "code": code_raw,
            "name": name,
            "buy_price": buy_price,
            "qty": qty,
            "current_price": current,
            "profit": profit
        })

    return render_template_string(HTML, data=results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
