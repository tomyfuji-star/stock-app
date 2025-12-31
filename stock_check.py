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

        # 通信はこれ一回だけ！(高速化のキモ)
        data = yf.download(codes, period="1y", group_by='ticker', threads=True, actions=True)

        results = []
        total_profit = 0
        total_dividend_income = 0

        for _, row in valid_df.iterrows():
            c = row['証券コード']
            ticker_code = f"{c}.T"
            # 銘柄名をさらに短く(全角3〜4文字程度)してスマホ対応
            name = str(row.get("銘柄", ""))
            display_name = name[:4] + ".." if len(name) > 4 else name
            
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))
            memo = str(row.get("メモ", "")) if not pd.isna(row.get("メモ")) else ""

            price, change, change_pct, annual_div = 0.0, 0.0, 0.0, 0.0
            
            if ticker_code in data:
                ticker_df = data[ticker_code].dropna(subset=['Close'])
                if not ticker_df.empty:
                    price = float(ticker_df['Close'].iloc[-1])
                    if len(ticker_df) >= 2:
                        prev_price = float(ticker_df['Close'].iloc[-2])
                        change = price - prev_price
                        change_pct = (change / prev_price) * 100
                    if 'Dividends' in ticker_df.columns:
                        annual_div = ticker_df['Dividends'].sum()
            
            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit
            total_dividend_income += int(annual_div * qty)

            results.append({
                "code": c, "name": display_name, "full_name": name,
                "price": price, "change": change, "change_pct": round(change_pct, 1),
                "profit": profit, "memo": memo,
                "buy_yield": round((annual_div / buy_price * 100), 2) if buy_price > 0 else 0
            })

        return render_template_string("""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <title>株主管理</title>
    <style>
        body { font-family: -apple-system, sans-serif; margin: 0; background: #f2f2f7; padding: 8px; font-size: 14px; }
        .summary { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
        .card { background: #fff; padding: 10px; border-radius: 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .card small { color: #888; font-size: 11px; }
        .card div { font-size: 16px; font-weight: bold; }
        
        .tabs { display: flex; background: #e5e5ea; border-radius: 8px; padding: 2px; margin-bottom: 10px; }
        .tab { flex: 1; padding: 8px; border: none; background: none; font-size: 13px; font-weight: bold; border-radius: 6px; }
        .tab.active { background: #fff; color: #007aff; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .content { display: none; }
        .content.active { display: block; }

        table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; table-layout: fixed; }
        th { background: #f8f8f8; padding: 8px 4px; font-size: 11px; color: #666; }
        td { padding: 10px 4px; border-bottom: 1px solid #eee; text-align: center; overflow: hidden; }
        .plus { color: #34c759; font-weight: bold; }
        .minus { color: #ff3b30; font-weight: bold; }
        .name-td { text-align: left; padding-left: 8px; width: 22%; }
        
        .memo-box { background: #fff; padding: 12px; border-radius: 10px; margin-bottom: 8px; }
        .memo-title { font-weight: bold; font-size: 13px; margin-bottom: 4px; display: flex; justify-content: space-between; }
        .memo-text { font-size: 12px; color: #444; line-height: 1.4; }
    </style>
</head>
<body>
    <div class="summary">
        <div class="card"><small>損益</small><div class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</div></div>
        <div class="card"><small>配当予定</small><div style="color: #007aff;">¥{{ "{:,}".format(total_dividend_income) }}</div></div>
    </div>

    <div class="tabs">
        <button class="tab active" onclick="tab('list')">資産</button>
        <button class="tab" onclick="tab('memo')">メモ</button>
    </div>

    <div id="list" class="content active">
        <table>
            <thead><tr><th style="width:25%">銘柄</th><th>現在値</th><th>損益</th><th style="width:18%">利回</th></tr></thead>
            <tbody>
                {% for r in results %}
                <tr>
                    <td class="name-td"><strong>{{ r.name }}</strong><br><small style="color:#999">{{ r.code }}</small></td>
                    <td>{{ "{:,}".format(r.price|int) }}<br><small class="{{ 'plus' if r.change > 0 else 'minus' }}">{{ r.change_pct }}%</small></td>
                    <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}">{{ "{:+,}".format(r.profit) }}</td>
                    <td style="font-weight:bold;">{{ r.buy_yield }}%</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <div id="memo" class="content">
        {% for r in results %}
        <div class="memo-box">
            <div class="memo-title"><span>{{ r.full_name }}</span><small style="color:#007bff">{{ r.code }}</small></div>
            <div class="memo-text">{{ r.memo if r.memo else '---' }}</div>
        </div>
        {% endfor %}
    </div>

    <p style="text-align:center;"><a href="/" style="color:#007aff; text-decoration:none; font-size:12px;">最新に更新</a></p>

    <script>
        function tab(id) {
            document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            event.currentTarget.classList.add('active');
        }
    </script>
</body>
</html>
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

    except Exception as e:
        return f"エラー: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
