from flask import Flask
import pandas as pd
import yfinance as yf

app = Flask(__name__)

# Googleスプレッドシート（CSV公開URL）
CSV_URL = "https://docs.google.com/spreadsheets/d/1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M/export?format=csv&gid=1052470389"

@app.route("/")
def index():
    df = pd.read_csv(CSV_URL)

    # 列名に依存しない（1列目=銘柄コード、2列目=取得価格）
    code_col = df.columns[0]
    buy_col = df.columns[1]

    html = """
    <h1>保有株一覧</h1>
    <table border="1" cellpadding="8">
    <tr>
        <th>銘柄コード</th>
        <th>取得価格</th>
        <th>現在価格</th>
        <th>損益率</th>
    </tr>
    """

    for _, row in df.iterrows():
        try:
            code = str(int(row[code_col])) + ".T"
            buy_price = float(row[buy_col])

            stock = yf.Ticker(code)
            current_price = stock.history(period="1d")["Close"].iloc[-1]

            profit_rate = (current_price - buy_price) / buy_price * 100

            html += f"""
            <tr>
                <td>{code}</td>
                <td>{buy_price:.2f}</td>
                <td>{current_price:.2f}</td>
                <td>{profit_rate:.2f}%</td>
            </tr>
            """
        except Exception as e:
            html += f"""
            <tr>
                <td colspan="4">エラー: {e}</td>
            </tr>
            """

    html += "</table>"
    return html


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
