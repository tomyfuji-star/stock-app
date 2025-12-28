from flask import Flask
import yfinance as yf
import os

app = Flask(__name__)

# ===== あなたの保有株 =====
stocks = [
    {"code": "7203.T", "name": "トヨタ", "buy_price": 2500, "shares": 100},
    {"code": "6758.T", "name": "ソニー", "buy_price": 12000, "shares": 50},
]

@app.route("/")
def index():
    rows = ""

    for s in stocks:
        ticker = yf.Ticker(s["code"])
        price = ticker.fast_info.get("last_price", 0)

        value = price * s["shares"]
        cost = s["buy_price"] * s["shares"]
        profit = value - cost
        yield_rate = (profit / cost * 100) if cost > 0 else 0

        rows += f"""
        <tr>
            <td>{s['name']}</td>
            <td>{s['code']}</td>
            <td>{price:,.0f}</td>
            <td>{s['buy_price']:,.0f}</td>
            <td>{s['shares']}</td>
            <td>{value:,.0f}</td>
            <td>{profit:,.0f}</td>
            <td>{yield_rate:.2f}%</td>
        </tr>
        """

    html = f"""
    <h1>📊 保有株一覧</h1>
    <table border="1" cellpadding="6">
        <tr>
            <th>銘柄</th>
            <th>コード</th>
            <th>現在価格</th>
            <th>取得単価</th>
            <th>株数</th>
            <th>評価額</th>
            <th>損益</th>
            <th>利回り</th>
        </tr>
        {rows}
    </table>
    """

    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
