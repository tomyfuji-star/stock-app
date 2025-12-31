from flask import Flask, render_template_string, request
import pandas as pd
import yfinance as yf
import re
import os

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

@app.route("/")
def index():
    try:
        # 1. スプレッドシート読み込み
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        df['証券コード'] = df['証券コード'].astype(str).str.strip().str.upper()
        codes = [f"{c}.T" for c in df['証券コード'] if c and c != "NAN"]

        # 2. 【最速】全銘柄をまとめて一括取得（並列処理）
        # threads=True にすることで、複数を同時に取りに行きます
        data = yf.download(codes, period="5d", interval="1d", group_by='ticker', threads=True)

        results = []
        total_profit = 0
        total_dividend_income = 0

        for _, row in df.iterrows():
            c = row['証券コード']
            if not c or c == "NAN": continue
            
            ticker_code = f"{c}.T"
            name = str(row.get("銘柄", "")).strip()
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))

            price = 0.0
            change = 0.0
            
            # 一括取得したデータから対象の株価を抽出
            try:
                if ticker_code in data:
                    ticker_df = data[ticker_code].dropna()
                    if not ticker_df.empty:
                        price = float(ticker_df['Close'].iloc[-1])
                        if len(ticker_df) >= 2:
                            change = price - float(ticker_df['Close'].iloc[-2])
            except:
                pass

            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit

            results.append({
                "code": c, "name": name, "qty": qty,
                "price": price, "profit": profit, "change": change
            })

        # 3. 画面表示（まずはシンプルに損益を優先）
        return render_template_string("""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>株主管理</title>
    <style>
        body { font-family: sans-serif; margin: 0; background: #f0f2f5; padding: 10px; }
        .summary { background: #1a73e8; color: white; padding: 20px; border-radius: 15px; margin-bottom: 15px; text-align: center; }
        .card { background: white; padding: 12px; border-radius: 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .plus { color: #28a745; } .minus { color: #dc3545; }
        .small { font-size: 0.8em; color: #666; }
    </style>
</head>
<body>
    <div class="summary">
        <small>合計評価損益</small><br>
        <span style="font-size: 1.8em; font-weight: bold;">¥{{ "{:,}".format(total_profit) }}</span>
    </div>
    {% for r in results %}
    <div class="card">
        <div>
            <span style="font-weight:bold;">{{ r.name }}</span> <span class="small">{{ r.code }}</span><br>
            <span class="small">{{ r.qty }}株</span>
        </div>
        <div style="text-align:right;">
            <span style="font-weight:bold;">{{ "{:,}".format(r.price|int) if r.price > 0 else '取得不可' }}</span><br>
            <span class="{{ 'plus' if r.profit >= 0 else 'minus' }}" style="font-size:0.9em;">
                {{ "{:+,}".format(r.profit) if r.price > 0 else '' }}
            </span>
        </div>
    </div>
    {% endfor %}
    <p style="text-align:center;"><a href="/" style="text-decoration:none; color:#1a73e8;">データを更新</a></p>
</body>
</html>
""", results=results, total_profit=total_profit)

    except Exception as e:
        return f"エラーが発生しました。再読み込みしてください: {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
