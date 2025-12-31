from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import re
import os
from datetime import datetime

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
        
        results = []
        total_profit = 0
        total_dividend_income = 0

        # まとめて価格取得（高速化のため）
        codes = [f"{c}.T" for c in valid_df['証券コード']]
        all_data = yf.download(codes, period="1y", group_by='ticker', threads=True, actions=True)

        for _, row in valid_df.iterrows():
            c = row['証券コード']
            ticker_code = f"{c}.T"
            name = str(row.get("銘柄", ""))
            short_name = name[:6] + ".." if len(name) > 6 else name
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))
            memo = str(row.get("メモ", "")) if not pd.isna(row.get("メモ")) else ""

            price, change, change_pct, annual_div = 0.0, 0.0, 0.0, 0.0
            earnings_date = "---"
            
            # 個別銘柄の詳細情報（決算予定日）を取得
            try:
                t = yf.Ticker(ticker_code)
                # 決算予定日の抽出
                cal = t.calendar
                if cal is not None and 'Earnings Date' in cal:
                    e_dates = cal['Earnings Date']
                    if isinstance(e_dates, list) and len(e_dates) > 0:
                        earnings_date = e_dates[0].strftime('%m/%d')
                
                # 価格・配当データ（一括取得分から）
                if ticker_code in all_data:
                    ticker_df = all_data[ticker_code].dropna(subset=['Close'])
                    if not ticker_df.empty:
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
            total_profit += profit
            total_dividend_income += int(annual_div * qty)

            results.append({
                "code": c, "name": short_name, "full_name": name, "price": price, 
                "change": change, "change_pct": round(change_pct, 2),
                "profit": profit, "memo": memo, "earnings": earnings_date,
                "current_yield": round((annual_div / price * 100), 2) if price > 0 else 0,
                "buy_yield": round((annual_div / buy_price * 100), 2) if buy_price > 0 else 0
            })

        return render_template_string("""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>株主管理 Pro</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/tablesort.min.js"></script>
    <style>
        body { font-family: sans-serif; margin: 0; background: #f0f2f5; padding: 5px; color: #333; }
        .container { max-width: 100%; margin: auto; }
        .tabs { display: flex; margin-bottom: 10px; background: #e0e0e0; border-radius: 8px; padding: 2px; }
        .tab-btn { flex: 1; padding: 12px; border: none; background: none; cursor: pointer; font-weight: bold; font-size: 0.85em; border-radius: 6px; }
        .tab-btn.active { background: #fff; color: #007bff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 15px; }
        .summary-card { background: #fff; padding: 12px; border-radius: 12px; text-align: center; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
        .summary-card small { color: #666; font-size: 0.7em; display: block; }
        .summary-card div { font-size: 1.1em; font-weight: bold; }
        
        .table-wrapper { background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        table { width: 100%; border-collapse: collapse; font-size: 0.78em; }
        th { background: #444; color: #fff; padding: 10px 4px; }
        td { padding: 12px 4px; border-bottom: 1px solid #f0f0f0; text-align: center; }
        
        .plus { color: #28a745; font-weight: bold; }
        .minus { color: #dc3545; font-weight: bold; }
        .name-col { text-align: left; padding-left: 8px; width: 28%; }
        
        /* 銘柄メモ・決算日のスタイル */
        .memo-item { padding: 12px; border-bottom: 1px solid #eee; background: #fff; }
        .memo-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
        .earnings-badge { background: #fff3cd; color: #856404; font-size: 0.75em; padding: 2px 8px; border-radius: 10px; font-weight: bold; border: 1px solid #ffeeba; }
        .memo-text { font-size: 0.85em; color: #555; white-space: pre-wrap; line-height: 1.5; }
        
        .refresh-btn { display: block; width: 160px; margin: 25px auto; padding: 10px; text-align: center; background: #007bff; color: white; text-decoration: none; border-radius: 25px; font-size: 0.8em; font-weight: bold; }
    </style>
</head>
<body>
<div class="container">
    <div class="summary-grid">
        <div class="summary-card"><small>評価損益</small><div class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</div></div>
        <div class="summary-card"><small>年間配当予想</small><div style="color: #007bff;">¥{{ "{:,}".format(total_dividend_income) }}</div></div>
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="openTab('assets')">資産一覧</button>
        <button class="tab-btn" onclick="openTab('memos')">決算・メモ</button>
    </div>

    <div id="assets" class="tab-content active">
        <div class="table-wrapper">
            <table id="asset-table">
                <thead>
                    <tr><th>銘柄</th><th>現在値</th><th>損益</th><th>利回り</th></tr>
                </thead>
                <tbody>
                    {% for r in results %}
                    <tr>
                        <td class="name-col"><strong>{{ r.name }}</strong><br><small style="color:#999">{{ r.code }}</small></td>
                        <td>{{ "{:,}".format(r.price|int) }}<br><small class="{{ 'plus' if r.change > 0 else 'minus' }}">{{ "{:+.0f}".format(r.change) }} ({{ r.change_pct }}%)</small></td>
                        <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}">{{ "{:+,}".format(r.profit) }}</td>
                        <td><strong>{{ r.buy_yield }}%</strong><br><small style="color:#888">現:{{ r.current_yield }}%</small></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div id="memos" class="tab-content">
        <div class="table-wrapper">
            {% for r in results %}
            <div class="memo-item">
                <div class="memo-header">
                    <strong>{{ r.full_name }} <small style="color:#888">({{ r.code }})</small></strong>
                    <span class="earnings-badge">決算: {{ r.earnings }}</span>
                </div>
                <div class="memo-text">{{ r.memo if r.memo else '（メモなし）' }}</div>
            </div>
            {% endfor %}
        </div>
    </div>

    <a href="/" class="refresh-btn">最新データに更新</a>
</div>

<script>
    function openTab(tabId) {
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');
        event.currentTarget.classList.add('active');
    }
    new Tablesort(document.getElementById('asset-table'));
</script>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

    except Exception as e:
        return f"エラーが発生しました: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
