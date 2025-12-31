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
        # 1. スプレッドシート読み込み
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        df['証券コード'] = df['証券コード'].astype(str).str.strip().str.upper()
        valid_df = df[df['証券コード'].str.match(r'^\d{4}$', na=False)].copy()
        codes = [f"{c}.T" for c in valid_df['証券コード']]

        # 2. 一括ダウンロード（actions=True で配当も取得）
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
                        price = float(ticker_df['Close'].iloc[-1])
                        if 'Dividends' in ticker_df.columns:
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
                "yield": round((annual_div / price * 100), 2) if price > 0 else 0
            })

        return render_template_string("""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>株主管理PRO</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/tablesort.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/sorts/tablesort.number.min.js"></script>
    <style>
        body { font-family: sans-serif; margin: 0; background: #f8f9fa; color: #333; padding: 10px; }
        .container { max-width: 900px; margin: auto; }
        .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .summary-card { background: #fff; padding: 15px; border-radius: 12px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .summary-card small { color: #666; font-size: 0.8em; }
        .summary-card div { font-size: 1.4em; font-weight: bold; margin-top: 5px; }
        
        table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px; overflow: hidden; font-size: 0.85em; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        th { background: #444; color: #fff; padding: 12px 8px; text-align: center; cursor: pointer; position: relative; }
        th:after { content: ' ↕'; font-size: 0.8em; opacity: 0.5; }
        td { padding: 10px 8px; border-bottom: 1px solid #eee; text-align: center; }
        
        .plus { color: #28a745; font-weight: bold; }
        .minus { color: #dc3545; font-weight: bold; }
        .code-label { color: #888; font-size: 0.8em; display: block; }
        .refresh-btn { display: block; width: 150px; margin: 20px auto; padding: 10px; text-align: center; background: #007bff; color: white; text-decoration: none; border-radius: 20px; font-size: 0.9em; }
    </style>
</head>
<body>
<div class="container">
    <div class="summary-grid">
        <div class="summary-card">
            <small>評価損益合計</small>
            <div class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</div>
        </div>
        <div class="summary-card">
            <small>年間配当予想</small>
            <div style="color: #007bff;">¥{{ "{:,}".format(total_dividend_income) }}</div>
        </div>
    </div>

    <table id="stock-table">
        <thead>
            <tr>
                <th>銘柄</th>
                <th data-sort-method="number">現在値</th>
                <th data-sort-method="number">損益</th>
                <th data-sort-method="number">利回り</th>
            </tr>
        </thead>
        <tbody>
            {% for r in results %}
            <tr>
                <td style="text-align:left;">
                    <strong>{{ r.name }}</strong>
                    <span class="code-label">{{ r.code }} ({{ r.qty }}株)</span>
                </td>
                <td>{{ "{:,}".format(r.price|int) if r.price > 0 else '---' }}</td>
                <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}" data-sort="{{ r.profit }}">
                    {{ "{:+,}".format(r.profit) if r.price > 0 else '' }}
                </td>
                <td data-sort="{{ r.yield }}">{{ r.yield }}%</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <a href="/" class="refresh-btn">最新情報に更新</a>
</div>

<script>
    new Tablesort(document.getElementById('stock-table'));
</script>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

    except Exception as e:
        return f"エラー: {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
