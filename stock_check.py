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

        # 1. 【最強設定】配当(actions=True)も含めて全銘柄を一括ダウンロード
        # periodを1年にすることで、過去1年間の配当実績を全て取得します
        data = yf.download(codes, period="1y", group_by='ticker', threads=True, actions=True)

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
            annual_div = 0.0
            
            try:
                if ticker_code in data:
                    ticker_df = data[ticker_code].dropna(subset=['Close'])
                    if not ticker_df.empty:
                        # 最新価格
                        price = float(ticker_df['Close'].iloc[-1])
                        
                        # 2. 【改善】ダウンロード済みのデータから配当(Dividends)を抽出
                        if 'Dividends' in ticker_df.columns:
                            # 過去1年間の配当合計を算出
                            annual_div = ticker_df['Dividends'].sum()
            except:
                pass

            profit = int((price - buy_price) * qty) if price > 0 else 0
            div_income = int(annual_div * qty)
            total_profit += profit
            total_dividend_income += div_income

            results.append({
                "code": c, "name": name, "qty": qty,
                "price": price, "profit": profit,
                "current_yield": round((annual_div / price * 100), 2) if price > 0 else 0
            })

        return render_template_string("""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>株主管理</title>
    <style>
        body { font-family: sans-serif; margin: 0; background: #f0f4f8; padding: 10px; }
        .summary-container { display: flex; gap: 10px; margin-bottom: 15px; }
        .summary-box { flex: 1; background: white; padding: 15px; border-radius: 12px; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .stock-item { background: white; padding: 12px; border-radius: 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; border-left: 5px solid #ccc; }
        .plus { border-left-color: #28a745; color: #28a745; }
        .minus { border-left-color: #dc3545; color: #dc3545; }
        .plus-text { color: #28a745; font-weight: bold; }
        .minus-text { color: #dc3545; font-weight: bold; }
        .small { font-size: 0.75em; color: #777; }
    </style>
</head>
<body>
    <div class="summary-container">
        <div class="summary-box">
            <small>評価損益</small><br>
            <span class="{{ 'plus-text' if total_profit >= 0 else 'minus-text' }}" style="font-size:1.2em;">¥{{ "{:,}".format(total_profit) }}</span>
        </div>
        <div class="summary-box">
            <small>年間配当</small><br>
            <span style="font-size:1.2em; color:#007bff; font-weight:bold;">¥{{ "{:,}".format(total_dividend_income) }}</span>
        </div>
    </div>

    {% for r in results %}
    <div class="stock-item {{ 'plus' if r.profit >= 0 else 'minus' }}">
        <div>
            <strong>{{ r.name }}</strong> <span class="small">{{ r.code }}</span><br>
            <span class="small">{{ r.qty }}株 / 利回り {{ r.current_yield }}%</span>
        </div>
        <div style="text-align:right;">
            <strong>{{ "{:,}".format(r.price|int) if r.price > 0 else '---' }}</strong><br>
            <span class="{{ 'plus-text' if r.profit >= 0 else 'minus-text' }}" style="font-size:0.85em;">
                {{ "{:+,}".format(r.profit) if r.price > 0 else '' }}
            </span>
        </div>
    </div>
    {% endfor %}
    <p style="text-align:center;"><a href="/" style="color:#007bff; text-decoration:none; font-size:0.9em;">最新情報に更新</a></p>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

    except Exception as e:
        return f"データ取得エラー: {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
