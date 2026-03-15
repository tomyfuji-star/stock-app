from flask import Flask, render_template_string, url_for, request
import pandas as pd
import yfinance as yf
import re
import os
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__, static_folder='.', static_url_path='')

# --- キャッシュ設定 ---
cache_storage = {
    "last_update": 0,
    "results": [],
    "total_profit": 0,
    "total_div": 0,
    "total_realized": 0
}

CACHE_TIMEOUT = 300 

# メイン資産シート (配当管理タブ)
SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

# 実現損益シート (損益計算タブ)
REALIZED_PROFIT_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1416973059"
)

def to_float(val):
    try:
        if pd.isna(val): return 0.0
        val = re.sub(r"[^\d.-]", "", str(val))
        return float(val) if val else 0.0
    except:
        return 0.0

@app.route("/")
def index():
    global cache_storage
    current_time = time.time()
    force_update = request.args.get('update_earnings') == '1'

    if not force_update and cache_storage["results"] and (current_time - cache_storage["last_update"] < CACHE_TIMEOUT):
        return render_template_string(HTML_TEMPLATE, **cache_storage, total_dividend_income=cache_storage["total_div"])

    try:
        # 1. 実現損益（損益計算シートのD2セル）の読み込み
        total_realized = 0
        try:
            # header=Noneで読み込み、座標で指定する
            df_realized = pd.read_csv(REALIZED_PROFIT_CSV_URL, header=None)
            
            # スプレッドシートの「D2」セル
            # 行: 2行目 -> インデックス 1
            # 列: D列 -> インデックス 3
            if df_realized.shape[0] >= 2 and df_realized.shape[1] >= 4:
                val_d2 = df_realized.iloc[1, 3] 
                total_realized = to_float(val_d2)
            else:
                # シートが想定より小さい場合は、B列などから探すバックアップ
                total_realized = to_float(df_realized.iloc[2, 1]) if df_realized.shape[0] >= 3 else 0
        except Exception as e:
            print(f"実現損益(D2)取得エラー: {e}")

        # 2. メイン資産シートの読み込み
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        df['証券コード'] = df['証券コード'].astype(str).str.strip().str.upper()
        valid_df = df[df['証券コード'].str.match(r'^[A-Z0-9]{4}$', na=False)].copy()
        codes = [f"{c}.T" for c in valid_df['証券コード']]

        # 3. yfinanceダウンロード
        data = yf.download(codes, period="1y", group_by='ticker', threads=True, timeout=20)

        def process_row(row):
            c = row['証券コード']
            ticker_code = f"{c}.T"
            price, day_change, day_change_pct, annual_div = 0.0, 0.0, 0.0, 0.0
            
            if ticker_code in data and not data[ticker_code].empty:
                ticker_df = data[ticker_code].dropna(subset=['Close'])
                if not ticker_df.empty:
                    price = float(ticker_df['Close'].iloc[-1])
                    if len(ticker_df) >= 2:
                        prev = float(ticker_df['Close'].iloc[-2])
                        day_change = price - prev
                        day_change_pct = (day_change / prev) * 100
                    if 'Dividends' in ticker_df.columns:
                        annual_div = ticker_df['Dividends'].sum()

            display_earnings = str(row.get("決算発表日", "---"))
            if display_earnings in ["nan", "", "None"]: display_earnings = "---"
            name = str(row.get("銘柄", ""))
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))
            profit = int((price - buy_price) * qty) if price > 0 else 0
            
            return {
                "code": c, "name": name[:4], "full_name": name,
                "price": price, "buy_price": buy_price, "qty": qty,
                "market_value": int(price * qty),
                "day_change": day_change, "day_change_pct": round(day_change_pct, 2),
                "profit": profit, "profit_pct": round(((price - buy_price) / buy_price * 100), 1) if buy_price > 0 else 0,
                "memo": str(row.get("メモ", "")) if not pd.isna(row.get("メモ")) else "",
                "earnings": display_earnings if "/" in display_earnings else "99/99", 
                "display_earnings": display_earnings,
                "buy_yield": round((annual_div / buy_price * 100), 2) if buy_price > 0 else 0,
                "cur_yield": round((annual_div / price * 100), 2) if price > 0 else 0,
                "div_amt": int(annual_div * qty)
            }

        with ThreadPoolExecutor(max_workers=20) as executor:
            current_results = list(executor.map(process_row, [row for _, row in valid_df.iterrows()]))

        total_profit = sum(r['profit'] for r in current_results)
        total_div = sum(r['div_amt'] for r in current_results)
        
        cache_storage = {
            "last_update": current_time, 
            "results": current_results, 
            "total_profit": total_profit, 
            "total_div": total_div,
            "total_realized": total_realized
        }
        
        return render_template_string(HTML_TEMPLATE, **cache_storage, total_dividend_income=total_div)

    except Exception as e:
        if cache_storage["results"]:
            return render_template_string(HTML_TEMPLATE, **cache_storage, total_dividend_income=cache_storage["total_div"])
        return f"更新中... ブラウザをリロードしてください: {e}"

# HTML_TEMPLATE は前回から変更なし
HTML_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <title>管理 Pro</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/tablesort.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/sorts/tablesort.number.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; margin: 0; background: #f2f2f7; color: #1c1c1e; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 800px; padding: 8px; box-sizing: border-box; }
        @media (min-width: 801px) { .container { width: 50%; } }
        .summary { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; margin-bottom: 10px; }
        .card { background: #fff; padding: 10px 4px; border-radius: 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .card.highlight { border: 1.5px solid #34c759; background: #fafffa; }
        .card small { color: #8e8e93; font-size: 9px; display: block; margin-bottom: 2px; }
        .card div { font-size: 13px; font-weight: bold; }
        .tabs { display: flex; background: #e5e5ea; border-radius: 8px; padding: 2px; margin-bottom: 10px; }
        .tab { flex: 1; padding: 8px; border: none; background: none; font-size: 12px; font-weight: bold; border-radius: 6px; color: #8e8e93; cursor: pointer; }
        .tab.active { background: #fff; color: #007aff; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .content { display: none; }
        .content.active { display: block; }
        .table-wrap { background: #fff; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
        table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 11px; }
        th { background: #f8f8f8; padding: 10px 2px; font-size: 10px; color: #8e8e93; border-bottom: 1px solid #eee; cursor: pointer; }
        td { padding: 10px 2px; border-bottom: 1px solid #f2f2f7; text-align: center; }
        .name-td { text-align: left; padding-left: 8px; width: 22%; }
        .name-td a { color: #1c1c1e; text-decoration: none; font-weight: bold; }
        .plus { color: #34c759; }
        .minus { color: #ff3b30; }
        .small-gray { color: #8e8e93; font-size: 9px; font-weight: normal; }
        .memo-box { background: #fff; padding: 12px; border-radius: 10px; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .memo-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; border-bottom: 1px solid #f2f2f7; padding-bottom: 6px; }
        .memo-title { font-weight: bold; font-size: 13px; }
        .memo-title a { color: #007aff; text-decoration: none; }
        .earnings-badge { background: #f0f7ff; color: #007aff; font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: bold; border: 1px solid #cce5ff; }
        .memo-market-val { margin: 8px 0; font-size: 12px; display: flex; justify-content: space-between; }
        .memo-text { font-size: 12px; color: #3a3a3c; white-space: pre-wrap; line-height: 1.5; background: #f9f9f9; padding: 10px; border-radius: 6px; border: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="summary">
            <div class="card"><small>評価損益</small><div class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</div></div>
            <div class="card highlight"><small>トータル実利</small><div class="{{ 'plus' if (total_profit + total_realized) >= 0 else 'minus' }}">¥{{ "{:,}".format((total_profit + total_realized)|int) }}</div></div>
            <div class="card"><small>年配当予想</small><div style="color: #007aff;">¥{{ "{:,}".format(total_dividend_income) }}</div></div>
        </div>
        <div class="tabs">
            <button class="tab active" onclick="tab('list')">資産状況</button>
            <button class="tab" onclick="tab('memo')">メモ / 決算日</button>
        </div>
        <div id="list" class="content active">
            <div class="table-wrap">
                <table id="stock-table">
                    <thead>
                        <tr><th style="width:20%">銘柄</th><th style="width:20%">現在/取得</th><th style="width:20%">前日/比率</th><th style="width:20%">評価損益</th><th style="width:20%">取得/現利</th></tr>
                    </thead>
                    <tbody>
                        {% for r in results %}
                        <tr>
                            <td class="name-td"><a href="https://kabutan.jp/stock/?code={{ r.code }}" target="_blank">{{ r.name }}</a><br><span class="small-gray">{{ r.code }}</span></td>
                            <td><strong>{{ "{:,}".format(r.price|int) }}</strong><br><span class="small-gray">{{ "{:,}".format(r.buy_price|int) }}</span></td>
                            <td class="{{ 'plus' if r.day_change >= 0 else 'minus' }}" data-sort="{{ r.day_change }}">{{ "{:+,}".format(r.day_change|int) }}<br><span>{{ "{:+.2f}".format(r.day_change_pct) }}%</span></td>
                            <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}" data-sort="{{ r.profit }}">{{ "{:+,}".format(r.profit) }}<br><span>{{ r.profit_pct }}%</span></td>
                            <td data-sort="{{ r.buy_yield }}"><strong>{{ r.buy_yield }}%</strong><br><span class="small-gray">{{ r.cur_yield }}%</span></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        <div id="memo" class="content">
            <div id="memo-container">
                {% for r in results %}
                <div class="memo-box">
                    <div class="memo-header"><span class="memo-title"><a href="https://kabutan.jp/stock/?code={{ r.code }}" target="_blank">{{ r.full_name }} ({{ r.code }})</a></span><span class="earnings-badge">決算: {{ r.display_earnings }}</span></div>
                    <div class="memo-market-val"><span>評価額: <strong>¥{{ "{:,}".format(r.market_value) }}</strong></span><span class="{{ 'plus' if r.profit >= 0 else 'minus' }}">{{ "{:+,}".format(r.profit) }} ({{ r.profit_pct }}%)</span></div>
                    <div class="memo-text">{{ r.memo if r.memo else '---' }}</div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
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
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
