from flask import Flask, render_template
import yfinance as yf

app = Flask(__name__)

stocks_data = [
    {"code": "7203.T", "name": "トヨタ", "shares": 100, "buy_price": 2000},
]

@app.route("/")
def index():
    stocks = []
    total_value = 0

    for s in stocks_data:
        price = yf.Ticker(s["code"]).history(period="1d")["Close"][0]
        value = int(price * s["shares"])
        rate = round((price - s["buy_price"]) / s["buy_price"] * 100, 2)

        total_value += value

        stocks.append({
            "name": s["name"],
            "price": int(price),
            "shares": s["shares"],
            "value": value,
            "rate": rate
        })

    return render_template(
        "index.html",
        stocks=stocks,
        total=total_value
    )

if __name__ == "__main__":
    app.run()

