from flask import Flask, render_template_string, url_for, request
import pandas as pd
import yfinance as yf
import re
import os
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__, static_folder='.', static_url_path='')

# キャッシュ
cache_storage = {"last_update": 0, "results": [], "total_profit": 0, "total_div": 0, "total_realized": 0}
CACHE_TIMEOUT = 300 

SPREADSHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M/export?format=csv&gid=1052470389"
REALIZED_PROFIT_CSV_URL = "https://docs.google.com/spreadsheets/d/1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M/export?format=csv&gid=1416973059"

def clean_num(val):
    """カンマ、円、記号を含む文字列を純粋な数値に変換する"""
    if pd.isna(val): return 0.0
    s = str(val).replace(',', '').replace('¥', '').replace('円', '').strip()
    try:
        # 数字、ドット、マイナス記号以外を削除
        s = re.sub(r'[^0-9\.\-]', '', s)
        return float(s) if s else 0.0
    except:
        return 0.0

@app.route("/")
def index():
    global cache_storage
    current_time = time.time()
    force_update = request.args.get('update_earnings') == '1'

    if not force_update and cache_storage["results"] and (current_time - cache_storage["last_update"] < CACHE_TIMEOUT):
        return render_template_string(HTML_TEMPLATE, **cache_storage)

    try:
        # 1. 実現損益（D2セル）を確実に取得
        total_realized = 0
        try:
            # 損益計算シートを読み込み
            rdf = pd.read_csv(REALIZED_PROFIT_CSV_URL, header=None)
            # D2セルは [行1, 列3]
            if rdf.shape[0] >= 2 and rdf.shape[1] >= 4:
                total_realized = clean_num(rdf.iloc[1, 3])
        except Exception as e:
            print(f"Realized Load Error: {e}")

        # 2. メインシート読み込み
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        df['証券コード'] = df['証券コード'].astype(str).str.strip().str.upper()
        valid_df = df[df['証券コード'].str.match(r'^[A-Z0-9]{4}$', na=False)].copy()
        codes = [f"{c}.T" for c in valid_df['証券コード']]

        # 3. データ取得
        data = yf.download(codes, period="5d", interval="1d", group_by='ticker', threads=True, timeout=15)

        def process_row(row):
            c = row['証券コード']
            ticker_code = f"{c}.T"
            price, day_change, day_change_pct, annual_div = 0.0, 0.0, 0.0, 0.0
            
            if ticker_code in data and not data[ticker_code].empty:
                t_df = data[ticker_code].dropna(subset=['Close'])
                if not t_df.empty:
                    price = float(t_df['Close'].iloc[-1])
                    if len(t_df) >= 2:
                        prev = float(t_df['Close'].iloc[-2])
                        day_change = price - prev
                        day_change_pct = (day_change / prev) * 100
                
                # 配当情報の取得
                try:
                    t_obj = yf.Ticker(ticker_code)
                    annual_div = t_obj.info.get('trailingAnnualDividendRate', 0) or t_obj.info.get('dividendRate', 0) or 0
                except:
                    annual_div = 0

            buy_price = clean_num(row.get("取得時"))
            qty = int(clean_num(row.get("株数")))
            profit = int((price - buy_price) * qty) if price > 0 else 0
            
            return {
                "code": c, "name": str(row.get("銘柄", ""))[:4], "full_name": str(row.get("銘柄", "")),
                "price": price, "buy_price": buy_price, "qty": qty,
                "market_value": int(price * qty),
                "day_change": day_change, "day_change_pct": round(day_change_pct, 2),
                "profit": profit, "profit_pct": round(((price - buy_price) / buy_price * 100), 1) if buy_price > 0 else 0,
                "memo": str(row.get("メモ", "")) if not pd.isna(row.get("メモ")) else "",
                "display_earnings": str(row.get("決算発表日", "---")),
                "div_amt": int(annual_div * qty) if annual_div else 0,
                "buy_yield": round((annual_div / buy_price * 100), 2) if buy_price > 0 and annual_div else 0,
                "cur_yield": round((annual_div / price * 100), 2) if price > 0 and annual_div else 0,
            }

        with ThreadPoolExecutor(max_workers=10) as executor:
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
        return render_template_string(HTML_TEMPLATE, **cache_storage)

    except Exception as e:
        return f"システムエラー: {e}"

# HTML部分は変更なし（CSSと構造は維持）
HTML_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <title>株管理 Pro</title>
    <style>
        body { font-family: -apple-system, sans-serif; margin: 0; background: #f2f2f7; color: #1c1c1e; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 800px; padding: 8px; box-sizing: border-box; }
        .summary { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; margin-bottom: 10px; }
        .card { background: #fff; padding: 10px 4px; border-radius: 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .card.highlight { border: 1.5px solid #34c759; background: #fafffa; }
        .card small { color: #8e8e93; font-size: 9px; display: block; margin-bottom: 2px; }
        .card div { font-size: 13px; font-weight: bold; }
        .plus { color: #34c759; }
        .minus { color: #ff3b30; }
        .table-wrap { background: #fff; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
        table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 11px; }
        th { background: #f8f8f8; padding: 10px 2px; font-size: 10px; color: #8e8e93; border-bottom: 1px solid #eee; }
        td { padding: 10px 2px; border-bottom: 1px solid #f2f2f7; text-align: center; }
        .name-td { text-align: left; padding-left: 8px; width: 22%; font-weight: bold; }
        .small-gray { color: #8e8e93; font-size: 9px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="summary">
            <div class="card"><small>評価損益</small><div class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</div></div>
            <div class="card highlight"><small>トータル実利</small><div class="{{ 'plus' if (total_profit + total_realized) >= 0 else 'minus' }}">¥{{ "{:,}".format((total_profit + total_realized)|int) }}</div></div>
            <div class="card"><small>年配当予想</small><div style="color: #007aff;">¥{{ "{:,}".format(total_div) }}</div></div>
        </div>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr><th style="width:20%">銘柄</th><th style="width:20%">現在/取得</th><th style="width:20%">前日/比率</th><th style="width:20%">評価損益</th><th style="width:20%">取得/現利</th></tr>
                </thead>
                <tbody>
                    {% for r in results %}
                    <tr>
                        <td class="name-td">{{ r.name }}<br><span class="small-gray">{{ r.code }}</span></td>
                        <td><strong>{{ "{:,}".format(r.price|int) }}</strong><br><span class="small-gray">{{ "{:,}".format(r.buy_price|int) }}</span></td>
                        <td class="{{ 'plus' if r.day_change >= 0 else 'minus' }}">{{ "{:+.0f}".format(r.day_change) }}<br>{{ "{:+.2f}".format(r.day_change_pct) }}%</td>
                        <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}">{{ "{:+,}".format(r.profit) }}<br>{{ r.profit_pct }}%</td>
                        <td><strong>{{ r.buy_yield }}%</strong><br><span class="small-gray">{{ r.cur_yield }}%</span></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
