from flask import Flask, render_template_string, url_for, request
import pandas as pd
import yfinance as yf
import re
import os
import time
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from curl_cffi import requests as cur_requests

app = Flask(__name__)

# --- キャッシュ設定 ---
cache_storage = {
    "last_update": 0,
    "results": None,
    "total_profit": 0,
    "total_div": 0
}
CACHE_TIMEOUT = 300 

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

def get_kabutan_earnings(code):
    """株探から決算発表予定日を抽出"""
    url = f"https://kabutan.jp/stock/finance?code={code}"
    try:
        res = cur_requests.get(url, impersonate="chrome110", timeout=5)
        if res.status_code != 200: return "制限"
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 発表予定日テーブルから抽出
        stat_table = soup.find("table", class_="stat_table2")
        if stat_table:
            target_td = stat_table.find("td", string=re.compile(r"発表予定"))
            if target_td:
                date_text = target_td.find_previous_sibling("td").get_text(strip=True)
                m = re.search(r'(\d{2})/(\d{2})/(\d{2})', date_text)
                if m: return f"{m.group(2)}/{m.group(3)}"
        
        # メインヘッダー付近から抽出
        info_text = soup.get_text()
        match = re.search(r'(\d{1,2})月(\d{1,2})日\s*発表予定', info_text)
        if match: return f"{match.group(1).zfill(2)}/{match.group(2).zfill(2)}"
        
        return "未定"
    except:
        return "---"

@app.route("/")
def index():
    global cache_storage
    current_time = time.time()
    fetch_earnings = request.args.get('fetch_earnings') == '1'

    # キャッシュがあれば即座に返す（起動直後のタイムアウト防止）
    if not fetch_earnings and cache_storage["results"] and (current_time - cache_storage["last_update"] < CACHE_TIMEOUT):
        return render_template_string(HTML_TEMPLATE, **cache_storage)

    try:
        # スプレッドシート読み込み
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        df['証券コード'] = df['証券コード'].astype(str).str.strip().str.upper()
        valid_df = df[df['証券コード'].str.match(r'^[A-Z0-9]{4}$', na=False)].copy()
        
        # yfinanceの取得（タイムアウトを短く設定）
        codes = [f"{c}.T" for c in valid_df['証券コード']]
        data = yf.download(codes, period="5d", group_by='ticker', threads=True, progress=False, timeout=10)

        def process_row(row):
            c = row['証券コード']
            ticker_code = f"{c}.T"
            name = str(row.get("銘柄", ""))[:4]
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))
            
            price, day_change, day_change_pct, annual_div = 0.0, 0.0, 0.0, 0.0
            
            if ticker_code in data and not data[ticker_code].dropna(subset=['Close']).empty:
                ticker_df = data[ticker_code].dropna(subset=['Close'])
                price = float(ticker_df['Close'].iloc[-1])
                if len(ticker_df) >= 2:
                    prev_price = float(ticker_df['Close'].iloc[-2])
                    day_change = price - prev_price
                    day_change_pct = (day_change / prev_price) * 100
                if 'Dividends' in ticker_df.columns:
                    annual_div = ticker_df['Dividends'].sum()

            # 決算情報の処理
            display_earnings = "---"
            if fetch_earnings:
                display_earnings = get_kabutan_earnings(c)
            elif cache_storage["results"]:
                prev = next((item for item in cache_storage["results"] if item["code"] == c), None)
                if prev: display_earnings = prev["display_earnings"]

            profit = int((price - buy_price) * qty) if price > 0 else 0
            
            return {
                "code": c, "name": name, "full_name": str(row.get("銘柄", "")),
                "price": price, "buy_price": buy_price, "qty": qty,
                "market_value": int(price * qty),
                "day_change": day_change, "day_change_pct": round(day_change_pct, 2),
                "profit": profit, "profit_pct": round(((price - buy_price) / buy_price * 100), 1) if buy_price > 0 else 0,
                "memo": str(row.get("メモ", "")) if not pd.isna(row.get("メモ")) else "",
                "display_earnings": display_earnings,
                "buy_yield": round((annual_div / buy_price * 100), 2) if buy_price > 0 else 0,
                "cur_yield": round((annual_div / price * 100), 2) if price > 0 else 0,
                "div_amt": int(annual_div * qty)
            }

        # 実行
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(process_row, [row for _, row in valid_df.iterrows()]))

        cache_storage = {
            "last_update": current_time,
            "results": results,
            "total_profit": sum(r['profit'] for r in results),
            "total_div": sum(r['div_amt'] for r in results)
        }

        return render_template_string(HTML_TEMPLATE, **cache_storage)
    except Exception as e:
        return f"システム起動中、またはエラーが発生しました。再読み込みしてください: {e}"

# --- HTML_TEMPLATE (前回のものと同一) ---
HTML_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <link rel="icon" href="{{ url_for('static', filename='favicon.svg') }}" type="image/svg+xml">
    <title>株主管理 Pro</title>
    <style>
        body { font-family: -apple-system, sans-serif; margin: 0; background: #f2f2f7; padding: 4px; font-size: 11px; color: #1c1c1e; }
        .summary { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-bottom: 6px; }
        .card { background: #fff; padding: 8px; border-radius: 8px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .card small { color: #8e8e83; font-size: 9px; display: block; }
        .card div { font-size: 13px; font-weight: bold; }
        .header-controls { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
        .tabs { display: flex; background: #e5e5ea; border-radius: 8px; padding: 2px; flex: 1; }
        .tab { flex: 1; padding: 8px 4px; border: none; background: none; font-size: 11px; font-weight: bold; border-radius: 6px; color: #8e8e93; cursor: pointer; }
        .tab.active { background: #fff; color: #007aff; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .btn-fetch { background: #007aff; color: #fff; border: none; padding: 8px 12px; border-radius: 8px; font-size: 10px; font-weight: bold; cursor: pointer; white-space: nowrap; }
        .content { display: none; }
        .content.active { display: block; }
        .table-wrap { background: #fff; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); width: 100%; overflow: hidden; }
        table { width: 100%; border-collapse: collapse; table-layout: fixed; }
        th { background: #f8f8f8; padding: 6px 2px; font-size: 9px; color: #8e8e93; border-bottom: 1px solid #eee; }
        td { padding: 8px 2px; border-bottom: 1px solid #f2f2f7; text-align: center; }
        .name-td { text-align: left; padding-left: 6px; width: 22%; font-weight: bold; }
        .plus { color: #34c759; font-weight: bold; }
        .minus { color: #ff3b30; font-weight: bold; }
        .small-gray { color: #8e8e93; font-size: 9px; font-weight: normal; }
        .memo-box { background: #fff; padding: 10px; border-radius: 8px; margin-bottom: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .memo-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; border-bottom: 1px solid #f2f2f7; padding-bottom: 4px; }
        .earnings-badge { background: #f0f7ff; color: #007aff; font-size: 9px; padding: 1px 6px; border-radius: 8px; font-weight: bold; border: 1px solid #cce5ff; }
        .memo-text { font-size: 11px; color: #3a3a3c; white-space: pre-wrap; background: #f9f9f9; padding: 6px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="summary">
        <div class="card"><small>評価損益</small><div class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</div></div>
        <div class="card"><small>年配当予想</small><div style="color: #007aff;">¥{{ "{:,}".format(total_div) }}</div></div>
    </div>
    <div class="header-controls">
        <div class="tabs">
            <button class="tab active" id="btn-tab-list" onclick="tab('list')">資産</button>
            <button class="tab" id="btn-tab-memo" onclick="tab('memo')">メモ/決算</button>
        </div>
        <button class="btn-fetch" onclick="fetchEarnings()">決算取得</button>
    </div>
    <div id="list" class="content active">
        <div class="table-wrap">
            <table id="stock-table">
                <thead><tr><th>銘柄</th><th>現在/取得</th><th>前日/比率</th><th>評価損益</th><th>取得/現利</th></tr></thead>
                <tbody>
                    {% for r in results %}
                    <tr>
                        <td class="name-td">{{ r.name }}<br><span class="small-gray">{{ r.code }}</span></td>
                        <td>{{ "{:,}".format(r.price|int) }}<br><span class="small-gray">{{ "{:,}".format(r.buy_price|int) }}</span></td>
                        <td class="{{ 'plus' if r.day_change >= 0 else 'minus' }}">{{ "{:+,}".format(r.day_change|int) }}<br>{{ r.day_change_pct }}%</td>
                        <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}">{{ "{:+,}".format(r.profit) }}<br>{{ r.profit_pct }}%</td>
                        <td>{{ r.buy_yield }}%<br><span class="small-gray">{{ r.cur_yield }}%</span></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    <div id="memo" class="content">
        {% for r in results %}
        <div class="memo-box">
            <div class="memo-header"><strong>{{ r.full_name }} ({{ r.code }})</strong><span class="earnings-badge">決算: {{ r.display_earnings }}</span></div>
            <div style="margin: 6px 0; font-size: 11px;">時価評価額: <strong>¥{{ "{:,}".format(r.market_value) }}</strong></div>
            <div class="memo-text">{{ r.memo if r.memo else '---' }}</div>
        </div>
        {% endfor %}
    </div>
    <script>
        function tab(id) {
            document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            document.getElementById('btn-tab-' + id).classList.add('active');
        }
        function fetchEarnings() {
            if(confirm("株探から決算予定日を取得します。")) {
                window.location.href = "/?fetch_earnings=1";
            }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
