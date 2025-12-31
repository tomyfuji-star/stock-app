from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import re
import os

app = Flask(__name__)

# スプレッドシートのURL（「メモ」列があることを前提としています）
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

        # データ一括取得（actions=Trueで配当も取得）
        data = yf.download(codes, period="1mo", group_by='ticker', threads=True, actions=True)

        results = []
        total_profit = 0
        total_dividend_income = 0

        for _, row in valid_df.iterrows():
            c = row['証券コード']
            ticker_code = f"{c}.T"
            name = str(row.get("銘柄", ""))[:6] # スマホ用に最大6文字に制限
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))
            memo = str(row.get("メモ", "")) if not pd.isna(row.get("メモ")) else ""

            price = 0.0
            change = 0.0
            change_pct = 0.0
            annual_div = 0.0
            earnings_date = "未定"
            
            try:
                if ticker_code in data:
                    ticker_df = data[ticker_code].dropna(subset=['Close'])
                    if not ticker_df.empty:
                        price = float(ticker_df['Close'].iloc[-1])
                        if len(ticker_df) >= 2:
                            prev_price = float(ticker_df['Close'].iloc[-2])
                            change = price - prev_price
                            change_pct = (change / prev_price) * 100
                        if 'Dividends' in ticker_df.columns:
                            # 1年分の配当は別途取得が必要な場合がありますが、downloadデータから直近を合算
                            annual_div = ticker_df['Dividends'].sum() * 12 # 簡易計算
            except:
                pass
            
            # 決算予定日取得（個別取得は重いため、今回は情報の一部として処理。将来的に拡張可能）
            # 注意: yfinanceのdownloadでは決算日は取得できないため、空欄または固定文字を表示
            
            profit = int((price - buy_price) * qty) if price > 0 else 0
            div_income = int(annual_div * qty)
            total_profit += profit
            total_dividend_income += div_income

            results.append({
                "code": c, "name": name, "qty": qty, "buy_price": buy_price,
                "price": price, "change": change, "change_pct": round(change_pct, 2),
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
    <title>株主管理 プレミアム</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/tablesort.min.js"></script>
    <style>
        body { font-family: sans-serif; margin: 0; background: #f0f2f5; padding: 5px; }
        .container { max-width: 100%; margin: auto; }
        .tabs { display: flex; margin-bottom: 10px; background: #ddd; border-radius: 8px; overflow: hidden; }
        .tab-btn { flex: 1; padding: 10px; border: none; background: none; cursor: pointer; font-weight: bold; }
        .tab-btn.active { background: #fff; color: #007bff; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-bottom: 10px; }
        .summary-card { background: #fff; padding: 10px; border-radius: 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .summary-card div { font-size: 1.1em; font-weight: bold; }
        
        table { width: 100%; border-collapse: collapse; background: #fff; font-size: 0.75em; }
        th { background: #444; color: #fff; padding: 8px 2px; position: sticky; top: 0; }
        td { padding: 10px 2px; border-bottom: 1px solid #eee; text-align: center; }
        .plus { color: #28a745; font-weight: bold; }
        .minus { color: #dc3545; font-weight: bold; }
        .name-col { text-align: left; max-width: 70px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-left: 5px; }
        .memo-text { font-size: 0.85em; color: #555; text-align: left; padding: 8px; }
    </style>
</head>
<body>
<div class="container">
    <div class="summary-grid">
        <div class="summary-card"><small>損益</small><div class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</div></div>
        <div class="summary-card"><small>配当</small><div style="color: #007bff;">¥{{ "{:,}".format(total_dividend_income) }}</div></div>
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="openTab('assets')">資産一覧</button>
        <button class="tab-btn" onclick="openTab('memos')">銘柄メモ</button>
    </div>

    <div id="assets" class="tab-content active">
        <table id="asset-table">
            <thead>
                <tr>
                    <th>銘柄</th>
                    <th>現在値(前日)</th>
                    <th>損益</th>
                    <th>利回</th>
                </tr>
            </thead>
            <tbody>
                {% for r in results %}
                <tr>
                    <td class="name-col"><strong>{{ r.name }}</strong><br><small>{{ r.code }}</small></td>
                    <td>{{ "{:,}".format(r.price|int) }}<br><small class="{{ 'plus' if r.change > 0 else 'minus' }}">{{ "{:+.0f}".format(r.change) }} ({{ r.change_pct }}%)</small></td>
                    <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}"> {{ "{:+,}".format(r.profit) }}</td>
                    <td>{{ r.buy_yield }}%</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <div id="memos" class="tab-content">
        <table>
            <thead>
                <tr>
                    <th>銘柄</th>
                    <th>決算日</th>
                    <th>メモ</th>
                </tr>
            </thead>
            <tbody>
                {% for r in results %}
                <tr>
                    <td class="name-col"><strong>{{ r.name }}</strong></td>
                    <td style="color: #e67e22; font-weight: bold;">{{ r.earnings }}</td>
                    <td class="memo-text">{{ r.memo }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <a href="/" style="display:block; text-align:center; margin:20px; color:#007bff; text-decoration:none;">最新に更新</a>
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
        return f"エラー: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
