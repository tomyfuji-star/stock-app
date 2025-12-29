from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf

app = Flask(__name__)

# ===== Google スプレッドシート設定 =====
SPREADSHEET_ID = "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
SHEET_GID = "1052470389"

CSV_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={SHEET_GID}"

HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>株価チェック</title>
</head>
<body>
<h2>保有株一覧</h2>
<table border="1" cellpadding="6">
<tr>
  <th>銘柄</th>
  <th>取得時</th>
  <th>現在価格</th>
  <th>株数</th>
  <th>評価損益</th>
</tr>
{% for r in data %}
<tr>
  <td>{{ r.code }}</td>
  <td>{{ r.buy_price }}</td>
  <td>{{ r.current_price }}</td>
  <td>{{ r.shares }}</td>
  <td>{{ r.profit }}</td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""

@app.route("/")
def index():
    # Google Sheets を直接読み込み
    df = pd.read_csv(CSV_URL)

    results = []

    for _, row in df.iterrows():
        code = str(row["銘柄"])
        buy_price = float(row["取得時"])
        shares = int(row["株数"])

        try:
            ticker = yf.Ticker(code)
            hist = ticker.history(period="1d")

            if hist.empty:
                current_price = 0
            else:
                current_price = round(hist["Close"].iloc[-1], 2)

        except Exception:
            current_price = 0

        profit = round((current_price - buy_price) * shares, 2)

        results.append({
            "code": code,
            "buy_price": buy_price,
            "current_price": current_price,
            "shares": shares,
            "profit": profit
        })

    return render_template_string(HTML, data=results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
