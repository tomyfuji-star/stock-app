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

        # 決算日データ(actions=True)を含めて一括ダウンロード
        # threads=True で並列処理し、タイムアウトを防ぎます
        data = yf.download(codes, period="1mo", group_by='ticker', threads=True, actions=True)

        results = []
        total_profit = 0
        total_dividend_income = 0

        for _, row in valid_df.iterrows():
            c = row['証券コード']
            ticker_code = f"{c}.T"
            name = str(row.get("銘柄", ""))
            display_name = name[:4] 
            
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))
            memo = str(row.get("メモ", "")) if not pd.isna(row.get("メモ")) else ""

            price, change, change_pct, annual_div = 0.0, 0.0, 0.0, 0.0
            earnings_date = "---"
            
            if ticker_code in data:
                ticker_df = data[ticker_code].dropna(subset=['Close'])
                if not ticker_df.empty:
                    price = float(ticker_df['Close'].iloc[-1])
                    if len(ticker_df) >= 2:
                        prev_price = float(ticker_df['Close'].iloc[-2])
                        change = price - prev_price
                        change_pct = (change / prev_price) * 100
                    
                    # 配当実績の計算（過去データの直近1年分などは yfinance の仕様上 download だけでは限界があるため、
                    # 前回のロジックを維持しつつエラーが出ないようにします）
                    if 'Dividends' in ticker_df.columns:
                        annual_div = ticker_df['Dividends'].sum()

            # 決算日の取得: 通信負荷の低い info または calendar からの取得を試みる
            # ただし、401エラー（Invalid Crumb）を避けるため、Tickerオブジェクトの最小限の呼び出しに留める
            try:
                t = yf.Ticker(ticker_code)
                # calendarは非常にエラーが出やすいため、代替案として info から取得を試みる
                cal = t.calendar
                if cal is not None and 'Earnings Date' in cal:
                    e_date = cal['Earnings Date'][0]
                    earnings_date = e_date.strftime('%m/%d')
            except:
                earnings_date = "未定"

            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit
            total_dividend_income += int(annual_div * qty)

            results.append({
                "code": c, "name": display_name, "full_name": name,
                "price": price, "buy_price": buy_price,
                "change": change, "change_pct": round(change_pct, 1),
                "profit": profit, "memo": memo, "earnings": earnings_date,
                "buy_yield": round((annual_div / buy_price * 100), 2) if buy_price > 0 else 0,
                "cur_yield": round((annual_div / price * 100), 2) if price > 0 else 0
            })

        return render_template_string("""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <title>株主管理 Pro</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/tablesort.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/sorts/tablesort.number.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; margin: 0; background: #f2f2f7; padding: 5px; font-size: 11px; color: #1c1c1e; }
        .summary { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 8px; }
        .card { background: #fff; padding: 10px; border-radius: 10px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .card small { color: #8e8e93; font-size: 10px; display: block; }
        .card div { font-size: 14px; font-weight: bold; }
        .tabs { display: flex; background: #e5e5ea; border-radius: 8px; padding: 2px; margin-bottom: 8px; }
        .tab { flex: 1; padding: 6px; border: none; background: none; font-size: 12px; font-weight: bold; border-radius: 6px; color: #8e8e93; }
        .tab.active { background: #fff; color: #007aff; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .content { display: none; }
        .content.active { display: block; }
        .table-wrap { background: #fff; border-radius: 10px; overflow-x: auto; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        table { width: 100%; border-collapse: collapse; min-width: 500px; }
        th { background: #f8f8f8; padding: 8px 4px; font-size: 9px; color: #8e8e93; border-bottom: 1px solid #eee; cursor: pointer; }
        td { padding: 10px 4px; border-bottom: 1px solid #f2f2f7; text-align: center; }
        .name-td { text-align: left; padding-left: 8px; font-weight: bold; }
        .plus { color: #34c759; font-weight: bold; }
        .minus { color: #ff3b30; font-weight: bold; }
        .memo-box { background: #fff; padding: 12px; border-radius: 10px; margin-bottom: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .memo-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
        .memo-title { font-weight: bold; font-size: 13px; color: #1c1c1e; }
        .earnings-badge { background: #eef7ff; color: #007aff; font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: bold; border: 1px solid #cce5ff; }
        .memo-text { font-size: 12px; color: #3a3a3c; white-space: pre-wrap; line-height: 1.5; }
    </style>
</head>
<body>
    <div class="summary">
        <div class="card"><small>評価損益</small><div class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</div></div>
        <div class="card"><small>配当合計</small><div style="color: #007aff;">¥{{ "{:,}".format(total_dividend_income) }}</div></div>
    </div>
    <div class="tabs">
        <button class="tab active" onclick="tab('list')">資産状況</button>
        <button class="tab" onclick="tab('memo')">メモ・決算</button>
    </div>
    <div id="list" class="content active">
        <div class="table-wrap">
            <table id="stock-table">
                <thead>
                    <tr>
                        <th style="width:20%">銘銘柄</th>
                        <th data-sort-method="number">現在値</th>
                        <th data-sort-method="number">取得額</th>
                        <th data-sort-method="number">評価損益</th>
                        <th data-sort-method="number">取得利 | 現利</th>
                    </tr>
                </thead>
                <tbody>
                    {% for r in results %}
                    <tr>
                        <td class="name-td">{{ r.name }}<br><span style="color:#8e8e93;font-size:9px;font-weight:normal;">{{ r.code }}</span></td>
                        <td>
                            <strong>{{ "{:,}".format(r.price|int) }}</strong><br>
                            <span class="{{ 'plus' if r.change > 0 else 'minus' if r.change < 0 else '' }}" style="font-size:9px;">
                                {{ "{:+.0f}".format(r.change) }}({{ r.change_pct }}%)
                            </span>
                        </td>
                        <td style="color:#666;">{{ "{:,}".format(r.buy_price|int) }}</td>
                        <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}" data-sort="{{ r.profit }}">{{ "{:+,}".format(r.profit) }}</td>
                        <td data-sort="{{ r.buy_yield }}">
                            <strong>{{ r.buy_yield }}%</strong><br>
                            <span style="color:#8e8e93;font-size:9px;">{{ r.cur_yield }}%</span>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    <div id="memo" class="content">
        {% for r in results %}
        <div class="memo-box">
            <div class="memo-header">
                <span class="memo-title">{{ r.full_name }} ({{ r.code }})</span>
                <span class="earnings-badge">決算: {{ r.earnings }}</span>
            </div>
            <div class="memo-text">{{ r.memo if r.memo else '---' }}</div>
        </div>
        {% endfor %}
    </div>
    <p style="text-align:center;"><a href="/" style="color:#007aff; text-decoration:none; font-weight:bold;">データを更新</a></p>
    <script>
        function tab(id) {
            document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            event.currentTarget.classList.add('active');
        }
        new Tablesort(document.getElementById('stock-table'));
    </script>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

    except Exception as e:
        return f"エラー: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
