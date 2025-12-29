from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import time

app = Flask(__name__)

CSV_PATH = "stocks.csv"  # Renderに置いたCSV名

HTML = """
<!doctype html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <title>株価チェック</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ccc; padding: 8px; text-align: center; }
        th { background: #f5f5f5; }
    </style>
</head>
<body>
<h2>保有株一覧</h2>
<table>
<tr>
    <th>銘柄</th>
    <th>取得価格</th>
    <th>現在価格</th>
    <th>株数</th>
    <th>評価額</th>
    <th>損益</th>
</tr>
{% for row in rows %}
<tr>
    <td>{{ row.symbol }}</td>
    <td>{{ row.buy_price }}</td>
    <td>{{ row.current_price }}</td>
    <td>{{ row.shares }}</td>
    <td>{{ row.value }}</td>
    <td>{{ row.profit }}</td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""

@app.route("/")
def index():
    df = pd.read_csv(CSV_PATH)

    rows = []

    for _, row in df.iterrows():
        symbol = row["銘柄"]
        buy_price = row["取得時"]   # ← ★ 修正ポイント
        shares = row["株数"]

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")

            if hist.empty:
                current_price = "-"
            else:
                current_price = round(hist["Close"].iloc[-1], 2)

        except Exception as e:
            current_price = "-"

        # 数値計算できる場合のみ損益計算
        if current_price != "-" and pd.notna(buy_price):
            value = round(current_price * shares, 2)
            profit = round((current_price - buy_price) * shares, 2)
        else:
            value = "-"
            profit = "-"

        rows.append({
            "symbol": symbol,
            "buy_price": buy_price,
            "current_price": current_price,
            "shares": shares,
            "value": value,
            "profit": profit
        })

        time.sleep(1)  # ★ yfinance レート制限対策

    return render_template_string(HTML, rows=rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
