from flask import Flask, render_template_string
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
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        df['証券コード'] = df['証券コード'].astype(str).str.strip().str.upper()
        valid_df = df[df['証券コード'].str.match(r'^\d{4}$', na=False)].copy()
        codes = [f"{c}.T" for c in valid_df['証券コード']]

        # 1. 【改善】価格データの一括取得
        data = yf.download(codes, period="5d", group_by='ticker', threads=True)
        
        # 2. 【新】配当データを確実に取るためのオブジェクト作成
        tickers = yf.Tickers(" ".join(codes))

        results = []
        total_profit = 0
        total_dividend_income = 0

        for _, row in valid_df.iterrows():
            c = row['証券コード']
            ticker_code = f"{c}.T"
            name = str(row.get("銘柄", "")).strip()
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))

            price = 0.0
            dividend = 0.0
            
            # 価格の抽出
            try:
                if ticker_code in data:
                    ticker_df = data[ticker_code].dropna(subset=['Close'])
                    if not ticker_df.empty:
                        price = float(ticker_df['Close'].iloc[-1])
            except:
                price = 0.0

            # 配当の抽出 (個別Tickerオブジェクトから直接historyを呼ぶ)
            try:
                # Tickersオブジェクトから該当銘柄を取り出し、配当を含む履歴を取得
                div_hist = tickers.tickers[ticker_code].history(period="1y")
                if 'Dividends' in div_hist.columns:
                    # 0以外の配当を抽出して合計
                    div_values = div_hist['Dividends'][div_hist['Dividends'] > 0]
                    if not div_values.empty:
                        # 直近1年間の合計配当
                        dividend = sum(div_values)
            except:
                dividend = 0.0

            profit = int((price - buy_price) * qty) if price > 0 else 0
            div_income = int(dividend * qty)
            total_profit += profit
            total_dividend_income += div_income

            results.append({
                "code": c, "name": name, "qty": qty,
                "price": price, "profit": profit,
                "current_yield": round((dividend / price * 100), 2) if price > 0 else 0
            })

        return render_template_string("""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>株主管理</title>
    <style>
        body { font-family: sans-serif; margin: 0; background: #f4f7f9; padding: 15px; }
        .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .summary-card { background: white; padding: 15px; border-radius: 12px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .stock-card { background: white; padding: 12px; border-radius: 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .plus { color: #28a745; font-weight: bold; }
        .minus { color: #dc3545; font-weight: bold; }
        .small { font-size: 0.75em; color: #888; margin-top: 3px; }
    </style>
</head>
<body>
    <div class="summary-grid">
        <div class="summary-card">
            <small style="color:#666;">評価損益合計</small><br>
            <span class="{{ 'plus' if total_profit >= 0 else 'minus' }}" style="font-size:1.1em;">¥{{ "{:,}".format(total_profit) }}</span>
        </div>
        <div class="summary-card">
            <small style="color:#666;">年間配当予想</small><br>
            <span style="font-size:1.1em; color:#007bff; font-weight:bold;">¥{{ "{:,}".format(total_dividend_income) }}</span>
        </div>
    </div>

    {% for r in results %}
    <div class="stock-card">
        <div>
            <strong>{{ r.name }}</strong> <span class="small">{{ r.code }}</span><br>
            <div class="small">{{ r.qty }}株 / 利回り {{ r.current_yield }}%</div>
        </div>
        <div style="text-align:right;">
            <strong>{{ "{:,}".format(r.price|int) if r.price > 0 else '---' }}</strong><br>
            <span class="{{ 'plus' if r.profit >= 0 else 'minus' }}" style="font-size:0.9em;">
                {{ "{:+,}".format(r.profit) if r.price > 0 else '' }}
            </span>
        </div>
    </div>
    {% endfor %}
    <p style="text-align:center; margin-top:20px;"><a href="/" style="color:#007bff; text-decoration:none;">最新に更新</a></p>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

    except Exception as e:
        return f"読み込み中... 再読み込みしてください: {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
