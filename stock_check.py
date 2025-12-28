from flask import Flask
import yfinance as yf

app = Flask(__name__)

@app.route("/")
def index():
    ticker = yf.Ticker("8306.T")
    info = ticker.fast_info

    current_price = info["last_price"]
    prev_close = info["previous_close"]

    diff = current_price - prev_close
    diff_rate = (diff / prev_close) * 100

    return f"""
    <html>
        <head>
            <title>三菱UFJ銀行 株価</title>
        </head>
        <body>
            <h1>三菱UFJフィナンシャル・グループ（8306）</h1>
            <ul>
                <li>現在株価：{current_price:.1f} 円</li>
                <li>前日終値：{prev_close:.1f} 円</li>
                <li>前日比：{diff:+.1f} 円（{diff_rate:+.2f}%）</li>
            </ul>
            <p>※ データ取得元：Yahoo Finance</p>
        </body>
    </html>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
