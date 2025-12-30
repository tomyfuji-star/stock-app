from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import yfinance as yf
import re
import os
from datetime import date

app = Flask(__name__)

SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

def to_float(val):
    try:
        val = re.sub(r"[^\d.-]", "", str(val))
        return float(val) if val else 0.0
    except:
        return 0.0

def get_stock_data_simple(code):
    """
    セッション指定を廃止し、yfinanceの自動制御(curl_cffi)に任せる方式
    """
    ticker_code = f"{code}.T"
    try:
        # セッション引数を削除
        t = yf.Ticker(ticker_code)
        
        # 5日分の履歴を取得
        hist = t.history(period="5d")
        
        if not hist.empty:
            current_price = float(hist["Close"].iloc[-1])
            prev_price = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current_price
            change = current_price - prev_price
            change_pct = (change / prev_price * 100) if prev_price > 0 else 0
            
            print(f"FETCHED: {code} = {current_price}")
            return current_price, change, change_pct
        else:
            print(f"NO DATA: {code}")
            return 0.0, 0.0, 0.0
    except Exception as e:
        print(f"ERROR: {code} - {str(e)}")
        return 0.0, 0.0, 0.0

@app.route("/")
def index():
    try:
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        results = []
        total_profit = 0

        for _, row in df.iterrows():
            code = str(row.get("証券コード", "")).strip().upper()
            if not code or code == "NAN": continue

            name = str(row.get("銘柄", "")).strip()
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))

            price, change, change_pct = get_stock_data_simple(code)
            
            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit

            results.append({
                "code": code, "name": name, "buy": buy_price, "qty": qty,
                "price": price, "change": change, "change_pct": round(change_pct, 2),
                "profit": profit
            })
            
        return render_template_string("""
        <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
        <body style="font-family:sans-serif; padding:15px; background:#f4f7f6;">
            <div style="background:white; padding:20px; border-radius:10px; box-shadow:0 2px 4px rgba(0,0,0,0.1); text-align:center;">
                <h3 style="margin:0; color:#666; font-size:0.9em;">評価損益合計</h3>
                <h2 style="margin:5px 0; color:{{ 'green' if total_profit >= 0 else 'red' }}">
                    ¥{{ "{:,}".format(total_profit) }}
                </h2>
            </div>
            <table border="1" cellpadding="8" style="border-collapse:collapse; width:100%; margin-top:20px; background:white; font-size:0.9em;">
                <tr style="background:#333; color:white;"><th>銘柄</th><th>現在値</th><th>前日比</th><th>損益</th></tr>
                {% for r in results %}
                <tr>
                    <td><strong>{{ r.name }}</strong><br><small>{{ r.code }}</small></td>
                    <td align="right">{{ "{:,}".format(r.price|int) if r.price > 0 else '取得不可' }}</td>
                    <td align="right" style="color:{{ 'green' if r.change > 0 else 'red' }}">
                        {{ '+' if r.change > 0 }}{{ "{:,}".format(r.change|int) if r.change != 0 else '' }}
                    </td>
                    <td align="right" style="color:{{ 'green' if r.profit >= 0 else 'red' }}">
                        {{ "{:,}".format(r.profit) }}
                    </td>
                </tr>
                {% endfor %}
            </table>
            <p style="text-align:center;"><a href="/">最新情報に更新</a></p>
        </body>
        </html>
        """, results=results, total_profit=total_profit)

    except Exception as e:
        return f"読み込み失敗: {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
