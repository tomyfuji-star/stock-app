# VERSION 8.0 - PERSONAL STOCK CHECK ONLY (Perfect Multi-Currency Support)
from flask import Flask, render_template_string, url_for, request
import pandas as pd
import yfinance as yf
import re
import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__, static_folder='.', static_url_path='')

# --- キャッシュ設定（1秒に設定して、シートの変更を即時反映させます） ---
cache_storage = {
    "last_update": 0,
    "results": None,
    "total_profit": 0,
    "total_div": 0,
    "total_assets": 0,
    "realized_gain": 0,
    "trust_return": 0,
    "usdjpy": 160.0
}
CACHE_TIMEOUT = 1

# あなた専用のスプレッドシートURL（1vwvK6Q...）
SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

SPREADSHEET_REALIZED_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=679093275"
)

def to_float(val):
    try:
        val = re.sub(r"[^\d.-]", "", str(val))
        return float(val) if val else 0.0
    except:
        return 0.0

def get_stable_usdjpy():
    """安定した外部為替APIからドル円のリアルタイムレートを取得"""
    try:
        res = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        if res.status_code == 200:
            data = res.json()
            rate = data.get("rates", {}).get("JPY")
            if rate:
                return float(rate)
    except Exception as e:
        print(f"為替API取得エラー: {e}")
    return 160.25  # 万が一のバックアップ固定値

def get_extra_gains():
    try:
        df = pd.read_csv(SPREADSHEET_REALIZED_URL, header=None)
        realized_gain = to_float(df.iloc[1, 1])
        dividend      = to_float(df.iloc[1, 2])
        trust_return  = to_float(df.iloc[1, 4])
        return realized_gain, dividend, trust_return
    except Exception as e:
        print(f"実利シート取得エラー: {e}")
        return 0.0, 0.0, 0.0

@app.route("/")
def index():
    global cache_storage
    current_time = time.time()
    
    force_update = request.args.get('update_earnings') == '1'

    if not force_update and cache_storage["results"] and (current_time - cache_storage["last_update"] < CACHE_TIMEOUT):
        realized_gain, dividend, trust_return = get_extra_gains()
        return render_template_string(HTML_TEMPLATE,
                                     results=cache_storage["results"],
                                     total_profit=cache_storage["total_profit"],
                                     total_dividend_income=cache_storage["total_div"],
                                     total_assets=cache_storage["total_assets"],
                                     realized_gain=realized_gain,
                                     dividend=dividend,
                                     trust_return=trust_return,
                                     usdjpy=cache_storage.get("usdjpy", 160.0))

    try:
        # シートを読み込み
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        df.columns = df.columns.str.strip()
        df['証券コード'] = df['証券コード'].astype(str).str.strip().str.upper()
        
        valid_df = df[df['証券コード'].str.match(r'^[A-Z0-9.-]+$', na=False)].copy()
        
        # 為替APIから最新ドル円を取得
        usdjpy = get_stable_usdjpy()
        
        # 各銘柄のデータを個別に取得して処理（構造バグを完全に防ぐ）
        results = []
        for _, row in valid_df.iterrows():
            c = row['証券コード']
            is_us_stock = not (c.isdigit() and len(c) == 4)
            ticker_code = f"{c}.T" if not is_us_stock else c
            
            price, day_change, day_change_pct = 0.0, 0.0, 0.0
            
            try:
                # 1銘柄ずつ安全に取得
                t_data = yf.Ticker(ticker_code)
                history = t_data.history(period="2d")
                if not history.empty:
                    price = float(history['Close'].iloc[-1])
                    if len(history) >= 2:
                        prev = float(history['Close'].iloc[-2])
                        day_change = price - prev
                        day_change_pct = (day_change / prev) * 100
            except Exception as e:
                print(f"データ取得エラー ({ticker_code}): {e}")

            annual_div = to_float(row.get("予想配当金", 0))
            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))

            # 通貨レートの適用設定（米国株ならドル円を掛ける、日本株なら1のまま）
            rate = usdjpy if is_us_stock else 1.0
            
            price_jpy = price * rate
            buy_price_jpy = buy_price * rate
            annual_div_jpy = annual_div * rate
            day_change_jpy = day_change * rate

            profit = int((price_jpy - buy_price_jpy) * qty) if price > 0 else 0
            market_value = int(price_jpy * qty)
            div_amt = int(annual_div_jpy * qty)

            display_earnings = str(row.get("決算発表日", "---"))
            if display_earnings == "nan" or display_earnings == "":
                display_earnings = "---"

            earnings_sort = display_earnings if "/" in display_earnings else "99/99"
            name = str(row.get("銘柄", ""))
            
            link_url = f"https://finance.yahoo.com/quote/{c}" if is_us_stock else f"https://kabutan.jp/stock/?code={c}"
            
            results.append({
                "code": c, "name": name[:4], "full_name": name,
                "price": price_jpy, "buy_price": buy_price_jpy, "qty": qty,
                "market_value": market_value,
                "day_change": day_change_jpy, "day_change_pct": round(day_change_pct, 2),
                "profit": profit, "profit_pct": round(((price_jpy - buy_price_jpy) / buy_price_jpy * 100), 1) if buy_price_jpy > 0 else 0,
                "memo": str(row.get("メモ", "")) if not pd.isna(row.get("メモ")) else "",
                "earnings": earnings_sort, "display_earnings": display_earnings,
                "buy_yield": round((annual_div_jpy / buy_price_jpy * 100), 2) if buy_price_jpy > 0 else 0,
                "cur_yield": round((annual_div_jpy / price_jpy * 100), 2) if price_jpy > 0 else 0,
                "div_amt": div_amt,
                "link_url": link_url,
                "is_us": is_us_stock
            })

        total_profit = sum(r['profit'] for r in results)
        total_div = sum(r['div_amt'] for r in results)
        total_assets = sum(r['market_value'] for r in results)
        realized_gain, dividend, trust_return = get_extra_gains()

        cache_storage = {
            "last_update": current_time,
            "results": results,
            "total_profit": total_profit,
            "total_div": total_div,
            "total_assets": total_assets,
            "realized_gain": realized_gain,
            "dividend": dividend,
            "trust_return": trust_return,
            "usdjpy": usdjpy
        }
        return render_template_string(HTML_TEMPLATE, results=results, total_profit=total_profit,
                                      total_dividend_income=total_div, total_assets=total_assets,
                                      realized_gain=realized_gain, dividend=dividend, trust_return=trust_return,
                                      usdjpy=round(usdjpy, 2))
    except Exception as e:
        return f"システムエラー: {e}"

HTML_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <link rel="icon" href="{{ url_for('static', filename='favicon.svg') }}" type="image/svg+xml">
    <title>個人ポートフォリオ 管理 Pro</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/tablesort.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/tablesort/5.2.1/sorts/tablesort.number.min.js"></script>
    <style>
        body { font-family: -apple-system, sans-serif; margin: 0; background: #f2f2f7; color: #1c1c1e; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 800px; padding: 8px; box-sizing: border-box; }
        @media (min-width: 801px) { .container { width: 50%; } }
        .summary { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px; }
        .card { background: #fff; padding: 12px; border-radius: 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .card small { color: #8e8e93; font-size: 10px; display: block; margin-bottom: 2px; }
        .card div { font-size: 16px; font-weight: bold; }
        .tabs { display: flex; background: #e5e5ea; border-radius: 8px; padding: 2px; margin-bottom: 10px; }
        .tab { flex: 1; padding: 8px; border: none; background: none; font-size: 12px; font-weight: bold; border-radius: 6px; color: #8e8e93; cursor: pointer; }
        .tab.active { background: #fff; color: #007aff; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .content { display: none; }
        .content.active { display: block; }
        .ctrl-panel { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; gap: 8px; }
        #memo-sort { font-size: 12px; padding: 8px; border-radius: 6px; border: 1px solid #ccc; background: #fff; flex-grow: 1; }
        .btn-update { background: #007aff; color: #fff; border: none; padding: 8px 14px; border-radius: 6px; font-size: 11px; font-weight: bold; text-decoration: none; white-space: nowrap; }
        .table-wrap { background: #fff; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
        table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 11px; }
        th { background: #f8f8f8; padding: 10px 2px; font-size: 10px; color: #8e8e93; border-bottom: 1px solid #eee; cursor: pointer; }
        td { padding: 10px 2px; border-bottom: 1px solid #f2f2f7; text-align: center; }
        .name-td { text-align: left; padding-left: 8px; width: 22%; }
        .name-td a { color: #1c1c1e; text-decoration: none; font-weight: bold; }
        .plus { color: #34c759; }
        .minus { color: #ff3b30; }
        .small-gray { color: #8e8e93; font-size: 9px; font-weight: normal; }
        .us-badge { background: #ff9500; color: #fff; font-size: 8px; padding: 1px 3px; border-radius: 3px; font-weight: bold; margin-left: 2px; vertical-align: middle; }
        .breakdown-row { display: flex; justify-content: space-between; align-items: center; gap: 6px; margin-bottom: 3px; }
        .breakdown-label { color: #8e8e93; font-size: 10px; }
        .breakdown-val { font-size: 12px; font-weight: bold; }
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
        {% set actual_profit = total_profit + realized_gain + dividend + trust_return %}
        <div class="summary">
            <div class="card"><small>評価損益</small><div class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</div></div>
            <div class="card"><small>年配当予想</small><div style="color: #007aff;">¥{{ "{:,}".format(total_dividend_income) }}</div></div>
        </div>
        <div class="summary">
            <div class="card">
                <div class="breakdown-row"><span class="breakdown-label">実利</span><span class="{{ 'plus' if realized_gain >= 0 else 'minus' }} breakdown-val">¥{{ "{:,}".format(realized_gain|int) }}</span></div>
                <div class="breakdown-row"><span class="breakdown-label">配当金</span><span style="color:#007aff;" class="breakdown-val">¥{{ "{:,}".format(dividend|int) }}</span></div>
                <div class="breakdown-row"><span class="breakdown-label">投信リターン</span><span class="{{ 'plus' if trust_return >= 0 else 'minus' }} breakdown-val">¥{{ "{:,}".format(trust_return|int) }}</span></div>
            </div>
            <div class="card">
                <small>総資産合計</small>
                <div style="color: #1c1c1e; margin-bottom: 6px;">¥{{ "{:,}".format(total_assets) }}</div>
                <hr style="border: 0; border-top: 1px solid #f2f2f7; margin: 4px 0;">
                <small style="margin-top: 4px;">実利（全損益合計）</small>
                <div class="{{ 'plus' if actual_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(actual_profit|int) }}</div>
            </div>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="tab('list')">資産状況</button>
            <button class="tab" onclick="tab('memo')">メモ / 決算日</button>
        </div>

        <div id="list" class="content active">
            <div class="table-wrap">
                <table id="stock-table">
                    <thead>
                        <tr>
                            <th style="width:20%">銘柄</th>
                            <th style="width:20%">現在/取得</th>
                            <th style="width:20%">前日/比率</th>
                            <th style="width:20%">評価損益</th>
                            <th style="width:20%">取得/現利</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for r in results %}
                        <tr>
                            <td class="name-td">
                                <a href="{{ r.link_url }}" target="_blank">{{ r.name }}</a>{% if r.is_us %}<span class="us-badge">米</span>{% endif %}<br>
                                <span class="small-gray">{{ r.qty }}株</span>
                            </td>
                            <td><strong>{{ "{:,}".format(r.price|int) }}</strong><br><span class="small-gray">{{ "{:,}".format(r.buy_price|int) }}</span></td>
                            <td class="{{ 'plus' if r.day_change >= 0 else 'minus' }}" data-sort="{{ r.day_change }}">
                                {{ "{:+,}".format(r.day_change|int) }}<br><span>{{ "{:+.2f}".format(r.day_change_pct) }}%</span>
                            </td>
                            <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}" data-sort="{{ r.profit }}">
                                {{ "{:+,}".format(r.profit) }}<br><span>{{ r.profit_pct }}%</span>
                            </td>
                            <td data-sort="{{ r.buy_yield }}"><strong>{{ r.buy_yield }}%</strong><br><span class="small-gray">{{ r.cur_yield }}%</span></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div id="memo" class="content">
            <div class="ctrl-panel">
                <select id="memo-sort" onchange="sortMemos()">
                    <option value="code">コード順</option>
                    <option value="earnings">決算日順</option>
                    <option value="profit">損益(多)順</option>
                    <option value="market_value">評価額(大)順</option>
                </select>
                <a href="/?update_earnings=1" class="btn-update" onclick="this.innerText='更新中...'">シート反映</a>
            </div>
            <div id="memo-container">
                {% for r in results %}
                <div class="memo-box" data-code="{{ r.code }}" data-earnings="{{ r.earnings }}" data-profit="{{ r.profit }}" data-market_value="{{ r.market_value }}">
                    <div class="memo-header">
                        <span class="memo-title">
                            <a href="{{ r.link_url }}" target="_blank">{{ r.full_name }} ({{ r.code }})</a>{% if r.is_us %}<span class="us-badge">米国株</span>{% endif %}
                        </span>
                        <span class="earnings-badge">決算: {{ r.display_earnings }}</span>
                    </div>
                    <div class="memo-market-val">
                        <span>評価額: <strong>¥{{ "{:,}".format(r.market_value) }}</strong> <small class="small-gray">({{ r.qty }}株)</small></span>
                        <span class="{{ 'plus' if r.profit >= 0 else 'minus' }}">{{ "{:+,}".format(r.profit) }} ({{ r.profit_pct }}%)</span>
                    </div>
                    <div class="memo-text">{{ r.memo if r.memo else '---' }}</div>
                </div>
                {% endfor %}
            </div>
        </div>

        <p style="text-align:center; margin-top: 20px; color:#8e8e93; font-size:11px;">
            適用為替レート: 1ドル = ￥{{ usdjpy }}<br>
            <a href="/" style="color:#007aff; text-decoration:none; font-weight:bold; font-size:12px; display:inline-block; margin-top:8px;">最新の情報に更新</a>
        </p>
    </div>

    <script>
        function tab(id) {
            document.querySelectorAll('.content').forEach(c => c.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            event.currentTarget.classList.add('active');
        }
        function sortMemos() {
            const container = document.getElementById('memo-container');
            const memos = Array.from(container.getElementsByClassName('memo-box'));
            const sortBy = document.getElementById('memo-sort').value;
            memos.sort((a, b) => {
                let valA = a.getAttribute('data-' + sortBy);
                let valB = b.getAttribute('data-' + sortBy);
                if (sortBy === 'profit' || sortBy === 'market_value') { return parseFloat(valB) - parseFloat(valA); }
                return valA.localeCompare(valB);
            });
            memos.forEach(m => container.appendChild(m));
        }
        new Tablesort(document.getElementById('stock-table'));
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
