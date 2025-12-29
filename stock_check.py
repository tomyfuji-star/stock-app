from flask import Flask
import pandas as pd
import yfinance as yf

app = Flask(__name__)

CSV_URL = "https://docs.google.com/spreadsheets/d/1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M/export?format=csv&gid=1052470389"

@app.route("/")
def index():
    try:
        df = pd.read_csv(CSV_URL)
    except Exception as e:
        return f"スプレッドシート取得エラー: {e}"

    rows_html = ""

    for _, row in df.iterrows():
        code = str(int(row["銘柄コード"])) + ".T"
        buy_price = float(row["取得価格"])
        shares = int(row["株数"])

        try:
            ticker = yf.Ticker(code)
            current_price = ticker.fast_info.get("last_price")
        except Exception:
            current_price = None

        if current_price is not None:
            profit = (current_price - buy_price) * shares
            profit_rate = (current_price - buy_price) / buy_price * 100
            price_html = f"{current_price:.1f}"
        else:
            profit = 0
            profit_rate = 0
            price_html = "取得失敗"

        color = "green" if profit >= 0 else "red"

        rows_html += f"""
        <tr>
            <td>{code}</td>
            <td>{buy_price:.1f}</td>
            <td>{shares}</td>
            <td>{price_html}</td>
            <td style="color:{color};">{profit:+,.0f}</td>
            <td style="color:{color};">{profit_rate:+.2f}%</td>
        </tr>
        """

    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>株式ポートフォリオ</title>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            table {{ border-collapse: collapse; }}
            th, td {{ border: 1px solid #999; padding: 6px 10px; text-align: right; }}
            th {{ background: #f0f0f0; }}
            td:first-child {{ text-align: left; }}
        </style>
    </head>
    <body>
        <h2>株式ポートフォリオ（Yahoo Finance連動）</h2>
        <table>
            <tr>
                <th>銘柄</th>
                <th>取得価格</th>
                <th>株数</th>
                <th>現在株価</th>
                <th>評価損益</th>
                <th>利回り</th>
            </tr>
            {rows_html}
        </table>
        <p>※ データ取得元：Yahoo Finance</p>
    </body>
    </html>
    """
    return html


if __name__ == "__main__":
    print("株価アプリ 起動成功")
    app.run(host="0.0.0.0", port=5000)
