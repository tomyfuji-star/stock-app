from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import time

app = Flask(__name__)

CSV_URL = "https://docs.google.com/spreadsheets/d/1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M/export?format=csv&gid=1052470389"

@app.route("/")
def index():
    df = pd.read_csv(
        CSV_URL,
        skiprows=1,
        names=["証券コード", "銘柄", "株価", "取得時"]
    )

    results = []

    for _, row in df.iterrows():
        code = str(row["証券コード"]).strip()

        try:
            buy_price = pd.to_numeric(row["取得時"], errors="coerce")

            ticker = code + ".T"
            stock = yf.Ticker(ticker)
            price = stock.history(period="1d")["Close"].iloc[-1]

            if pd.isna(buy_price):
                profit = "-"
            else:
                profit = round((price - buy_price) / buy_price * 100, 2)

            results.append({
                "code": code,
                "buy": buy_price if not pd.isna(buy_price) else "-",
                "now": round(price, 2),
                "profit": profit
            })

            time.sleep(1)  # ★レート制限回避

        except Exception as e:
            results.append({
                "code": code,
                "buy": "-",
                "now": "-",
                "profit": f"エラー"
            })

    html = """
    <h1>保有株一覧</h1>
    <table border="1" cellpadding="6">
        <tr>
            <th>銘柄コード</th>
            <th>取得価格</th>
            <th>現在価格</th>
            <th>損益率(%)</th>
        </tr>
        {% for r in results %}
        <tr>
            <td>{{ r.code }}</td>
            <td>{{ r.buy }}</td>
            <td>{{ r.now }}</td>
            <td>{{ r.profit }}</td>
        </tr>
        {% endfor %}
    </table>
    """
    return render_template_string(html, results=results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
