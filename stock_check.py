from flask import Flask
import os

app = Flask(__name__)

stocks = [
    {"code": "7203.T", "name": "トヨタ", "buy_price": 2500, "shares": 100},
    {"code": "6758.T", "name": "ソニー", "buy_price": 12000, "shares": 50},
]

@app.route("/")
def index():
    html = """
    <h1>保有株一覧</h1>
    <table border="1" cellpadding="5">
      <tr>
        <th>銘柄</th>
        <th>コード</th>
        <th>取得単価</th>
        <th>株数</th>
      </tr>
    """
    for s in stocks:
        html += f"""
        <tr>
          <td>{s['name']}</td>
          <td>{s['code']}</td>
          <td>{s['buy_price']}</td>
          <td>{s['shares']}</td>
        </tr>
        """
    html += "</table>"
    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
