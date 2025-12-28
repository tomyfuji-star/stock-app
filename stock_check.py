from flask import Flask
import yfinance as yf
import pandas as pd
import os

app = Flask(__name__)

# ===== Googleスプレッドシート（CSV公開URL）=====
CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1_jtP54CEzFlFn0lcqKB5qIwbYWbm7PU1EkpJnmW1Km8"
    "/export?format=csv&gid=249831611"
)

@app.route("/")
def index():
    try:
        df = pd.read_csv(CSV_URL)
    except Exception as e:
        return f"<h2>CSVの読み込みに失敗しました</h2><pre>{e}</pre>"

    rows = ""
    total_value_sum = 0
    total_cost_sum = 0

    for _, row in df.iterrows():
        ticker = str(row["ticker"])
        shares = float(row["shares"])
        avg_price = float(row["avg_price"])

        stock = yf.Ticker(ticker)
        price = stock.fast_info.get("last_price", 0)

        value = price * shares
        cost = avg_price * shares
        profit = value - cost
        yield_rate = (profit / cost * 100) if cost > 0 else 0

        total_value_sum += value
        total_cost_sum += cost

        color = "green" if profit >= 0 else "red"

        rows += f"""
        <tr>
            <td>{ticker}</td>
            <td>{shares:.0f}</td>
            <td>{price:,.0f}</td>
            <td>{avg_price:,.0f}</td>
            <td>{value:,.0f}</td>
            <td style="color:{color};">{profit:,.0f}</td>
            <td style="color:{color};">{yield_rate:.2f}%</td>
        </tr>
        """

    total_profit = total_value_sum - total_cost_sum
    total_yield = (total_profit / total_cost_sum * 100) if total_cost_sum > 0 else 0
    total_color = "green" if total_profit >= 0 else "red"

    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>保有株一覧</title>
    </head>
    <body>
        <h1>📊 保有株一覧</h1>

        <table border="1" cellpadding="6">
            <tr>
                <th>銘柄コード</th>
                <th>株数</th>
                <th>現在価格</th>
                <th>取得単価</th>
                <th>評価額</th>
                <th>損益</th>
                <th>利回り2</th>
            </tr>
            {rows}
        </table>

        <h2>合計
