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

        # 配当と履歴(1年分)を一括取得
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
            change = 0.0
            change_pct = 0.0
            annual_div = 0.0
            
            try:
                if ticker_code in data:
                    ticker_df = data[ticker_code].dropna(subset=['Close'])
                    if len(ticker_df) >= 1:
                        price = float(ticker_df['Close'].iloc[-1])
                        if len(ticker_df) >= 2:
                            prev_price = float(ticker_df['Close'].iloc[-2])
                            change = price - prev_price
                            change_pct = (change / prev_price) * 100
                        
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
                "buy_price": buy_price,
                "price": price, 
                "change": change,
                "change_pct": round(change_pct, 2),
                "profit": profit,
                "current_yield": round((annual_div / price * 100), 2) if price > 0 else 0,
                "buy_yield": round((annual_div / buy_price * 100), 2) if buy_price > 0 else 0
            })

        return render_template_string("""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>株主管理 プレミアム</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/tablesort.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/sorts/tablesort.number.min.js"></script>
    <style>
        body { font-family: sans-serif; margin: 0; background: #f0f2f5; color: #333; padding: 10px; }
        .container { max-width: 1000px; margin: auto; }
        .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .summary-card { background: #fff; padding: 15px; border-radius: 12px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .summary-card small { color: #666; font-size: 0.85em; }
        .summary-card div { font-size: 1.4em; font-weight: bold; margin-top: 5px; }
        
        .table-wrapper { background: #fff; border-radius: 12px; overflow-x: auto; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; font-size: 0.82em; min-width: 700px; }
        th { background: #444; color: #fff; padding: 12px 5px; text-align: center; cursor: pointer; white-space: nowrap; }
        td { padding: 12px 5px; border-bottom: 1px solid #eee; text-align: center; }
        
        .plus { color: #28a745; font-weight: bold; }
        .minus { color: #dc3545; font-weight: bold; }
        .small-text { font-size: 0.75em; color: #888; }
        .refresh-btn { display: block; width: 180px; margin: 20px auto; padding: 10px; text-align: center; background: #007bff; color: white; text-decoration: none; border-radius: 20px; }
    </style>
</head>
<body>
<div class="container">
    <div class="summary-grid">
        <div class="summary-card"><small>評価損益合計</small><div class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</div></div>
        <div class="summary-card"><small>年間配当予想</small><div style="color: #007bff;">¥{{ "{:,}".format(total_dividend_income) }}</div></div>
    </div>

    <div class="table-wrapper">
    <table id="stock-table">
        <thead>
            <tr>
                <th>銘柄</th>
                <th data-sort-method="number">現在値 / 前日比</th>
                <th data-sort-method="number">取得時</th>
                <th data-sort-method="number">評価損益</th>
                <th data-sort-method="number">現在利回</th>
                <th data-sort-method="number">取得利回</th>
            </tr>
        </thead>
        <tbody>
            {% for r in results %}
            <tr>
                <td style="text-align:left; padding-left:15px;">
                    <strong>{{ r.name }}</strong><br><span class="small-text">{{ r.code }} ({{ r.qty }}株)</span>
                </td>
                <td>
                    <strong>{{ "{:,}".format(r.price|int) if r.price > 0 else '---' }}</strong><br>
                    <span class="{{ 'plus' if r.change > 0 else 'minus' if r.change < 0 else '' }}" style="font-size:0.85em;">
                        {{ "{:+,}".format(r.change|int) if r.price > 0 else '' }} ({{ "{:+.2f}".format(r.change_pct) }}%)
                    </span>
                </td>
                <td><span class="small-text">¥</span>{{ "{:,}".format(r.buy_price|int) }}</td>
                <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}" data-sort="{{ r.profit }}">
                    {{ "{:+,}".format(r.profit) if r.price > 0 else '' }}
                </td>
                <td data-sort="{{ r.current_yield }}">{{ r.current_yield }}%</td>
                <td data-sort="{{ r.buy_yield }}" style="background:#f9fafb; font-weight:bold;">{{ r.buy_yield }}%</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    </div>

    <a href="/" class="refresh-btn">最新情報に更新</a>
</div>

<script>
    new Tablesort(document.getElementById('stock-table'));
</script>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

    except Exception as e:
        return f"エラーが発生しました: {e}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
