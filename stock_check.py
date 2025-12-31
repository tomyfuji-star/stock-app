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

        # 1. 【高速】価格データのみを一括ダウンロード
        data = yf.download(codes, period="5d", group_by='ticker', threads=True)
        
        # 2. 【改善】利回り情報を超高速に取得する準備
        tickers_obj = yf.Tickers(" ".join(codes))

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
            dividend_yield = 0.0
            
            # 株価の抽出
            try:
                if ticker_code in data:
                    ticker_df = data[ticker_code].dropna(subset=['Close'])
                    if not ticker_df.empty:
                        price = float(ticker_df['Close'].iloc[-1])
            except:
                price = 0.0

            # 利回りの抽出 (fast_infoを使用：通信を発生させないため爆速)
            try:
                # 履歴を遡らず、現在の基本情報を参照
                info = tickers_obj.tickers[ticker_code].fast_info
                dividend_yield = info.get('last_dividend', 0) / price if price > 0 else 0
                # もしlast_dividendが取れない場合は0になるが、これでタイムアウトは防げる
            except:
                dividend_yield = 0.0

            profit = int((price - buy_price) * qty) if price > 0 else 0
            
            # 年間配当（概算）
            annual_div = (price * dividend_yield) * qty
            total_profit += profit
            total_dividend_income += int(annual_div)

            results.append({
                "code": c, "name": name, "qty": qty,
                "price": price, "profit": profit,
                "current_yield": round(dividend_yield * 100, 2)
            })

        return render_template_string("""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; margin: 0; background: #f4f7f9; padding: 10px; }
        .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .summary-card { background: white; padding: 12px; border-radius: 10px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .stock-card { background: white; padding: 12px; border-radius: 8px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .plus { color: #28a745; font-weight: bold; }
        .minus { color: #dc3545; font-weight: bold; }
        .small { font-size: 0.7em; color: #888; }
    </style>
</head>
<body>
    <div class="summary-grid">
        <div class="summary-card"><small>評価損益</small><br><span class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</span></div>
        <div class="summary-card"><small>予想配当(年)</small><br><span style="color:#007bff; font-weight:bold;">¥{{ "{:,}".format(total_dividend_income) }}</span></div>
    </div>
    {% for r in results %}
    <div class="stock-card">
        <div><strong>{{ r.name }}</strong> <span class="small">{{ r.code }}</span><br><span class="small">{{ r.qty }}株 / 利回り {{ r.current_yield }}%</span></div>
        <div style="text-align:right;"><strong>{{ "{:,}".format(r.price|int) if r.price > 0 else '---' }}</strong><br><span class="{{ 'plus' if r.profit >= 0 else 'minus' }}" style="font-size:0.85em;">{{ "{:+,}".format(r.profit) if r.price > 0 else '' }}</span></div>
    </div>
    {% endfor %}
    <p style="text-align:center;"><a href="/" style="color:#007bff; text-decoration:none; font-size:0.9em;">更新</a></p>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

    except Exception as e:
        return f"エラー: {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
