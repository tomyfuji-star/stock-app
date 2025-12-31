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

        # 2. 価格データと配当実績を取得（期間を1年に伸ばして配当漏れを防ぐ）
        # threads=Trueで高速化
        data = yf.download(codes, period="1y", group_by='ticker', threads=True, actions=True)

        results = []
        total_profit = 0
        total_dividend_income = 0

        for _, row in valid_df.iterrows():
            c = row['証券コード']
            ticker_code = f"{c}.T"
            name = str(row.get("銘柄", ""))
            # 表示用に短くカット（スマホ対応）
            short_name = name[:6] + ".." if len(name) > 6 else name
            
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))
            memo = str(row.get("メモ", "")) if not pd.isna(row.get("メモ")) else ""

            price = 0.0
            change = 0.0
            change_pct = 0.0
            annual_div = 0.0
            
            try:
                if ticker_code in data:
                    ticker_df = data[ticker_code].dropna(subset=['Close'])
                    if not ticker_df.empty:
                        # 現在値と前日比
                        price = float(ticker_df['Close'].iloc[-1])
                        if len(ticker_df) >= 2:
                            prev_price = float(ticker_df['Close'].iloc[-2])
                            change = price - prev_price
                            change_pct = (change / prev_price) * 100
                        
                        # 配当計算（過去1年の合計実績を使用）
                        if 'Dividends' in ticker_df.columns:
                            annual_div = ticker_df['Dividends'].sum()
            except:
                pass
            
            profit = int((price - buy_price) * qty) if price > 0 else 0
            div_income = int(annual_div * qty)
            
            total_profit += profit
            total_dividend_income += div_income

            results.append({
                "code": c, "name": short_name, "full_name": name, "qty": qty, 
                "buy_price": buy_price, "price": price, 
                "change": change, "change_pct": round(change_pct, 2),
                "profit": profit, "memo": memo,
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
        body { font-family: sans-serif; margin: 0; background: #f0f2f5; padding: 5px; color: #333; }
        .container { max-width: 100%; margin: auto; }
        
        /* タブデザイン */
        .tabs { display: flex; margin-bottom: 10px; background: #e0e0e0; border-radius: 8px; padding: 2px; }
        .tab-btn { flex: 1; padding: 12px; border: none; background: none; cursor: pointer; font-weight: bold; font-size: 0.9em; transition: 0.3s; border-radius: 6px; }
        .tab-btn.active { background: #fff; color: #007bff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .tab-content { display: none; animation: fadeIn 0.3s; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

        /* サマリーカード */
        .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 15px; }
        .summary-card { background: #fff; padding: 12px; border-radius: 12px; text-align: center; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
        .summary-card small { color: #666; font-size: 0.75em; display: block; margin-bottom: 4px; }
        .summary-card div { font-size: 1.15em; font-weight: bold; }
        
        /* テーブルデザイン */
        .table-wrapper { background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        table { width: 100%; border-collapse: collapse; font-size: 0.78em; }
        th { background: #444; color: #fff; padding: 10px 4px; font-weight: normal; }
        td { padding: 12px 4px; border-bottom: 1px solid #f0f0f0; text-align: center; line-height: 1.4; }
        
        .name-col { text-align: left; padding-left: 8px; width: 25%; }
        .plus { color: #28a745; font-weight: bold; }
        .minus { color: #dc3545; font-weight: bold; }
        .small-text { font-size: 0.8em; color: #888; }
        
        .memo-row { text-align: left; padding: 15px; border-bottom: 1px solid #eee; }
        .refresh-btn { display: block; width: 160px; margin: 25px auto; padding: 10px; text-align: center; background: #007bff; color: white; text-decoration: none; border-radius: 25px; font-size: 0.85em; font-weight: bold; }
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
            <small>年間配当（実績）</small>
            <div style="color: #007bff;">¥{{ "{:,}".format(total_dividend_income) }}</div>
        </div>
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="openTab('assets')">資産一覧</button>
        <button class="tab-btn" onclick="openTab('memos')">銘柄メモ</button>
    </div>

    <div id="assets" class="tab-content active">
        <div class="table-wrapper">
            <table id="asset-table">
                <thead>
                    <tr>
                        <th>銘柄</th>
                        <th>現在値(前日)</th>
                        <th>評価損益</th>
                        <th>利回り</th>
                    </tr>
                </thead>
                <tbody>
                    {% for r in results %}
                    <tr>
                        <td class="name-col">
                            <strong>{{ r.name }}</strong><br>
                            <span class="small-text">{{ r.code }}</span>
                        </td>
                        <td>
                            {{ "{:,}".format(r.price|int) if r.price > 0 else '---' }}<br>
                            <span class="{{ 'plus' if r.change > 0 else 'minus' if r.change < 0 else '' }}" style="font-size:0.9em;">
                                {{ "{:+.0f}".format(r.change) }} ({{ r.change_pct }}%)
                            </span>
                        </td>
                        <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}">
                            {{ "{:+,}".format(r.profit) }}
                        </td>
                        <td>
                            <strong>{{ r.buy_yield }}%</strong><br>
                            <span class="small-text">現在:{{ r.current_yield }}%</span>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <div id="memos" class="tab-content">
        <div class="table-wrapper">
            {% for r in results %}
            <div class="memo-row">
                <strong>{{ r.full_name }} ({{ r.code }})</strong>
                <div style="margin-top:5px; color:#555; font-size:0.9em; white-space:pre-wrap;">{{ r.memo if r.memo else '（メモなし）' }}</div>
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
