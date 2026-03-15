from flask import Flask, render_template_string, request
import pandas as pd
import yfinance as yf
import re
import os
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# キャッシュ管理
cache_storage = {"last_update": 0, "results": [], "total_profit": 0, "total_div": 0, "total_realized": 0}
CACHE_TIMEOUT = 300 

# CSV URL
SPREADSHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M/export?format=csv&gid=1052470389"
REALIZED_PROFIT_CSV_URL = "https://docs.google.com/spreadsheets/d/1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M/export?format=csv&gid=1416973059"

def to_f(val):
    """どんな形式の文字でも数値に変換する"""
    if pd.isna(val): return 0.0
    try:
        s = str(val).replace(',', '').replace('¥', '').replace('円', '').strip()
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
        # 1. 実現損益（損益計算シート D2セル）
        realized_val = 0
        try:
            # header=Noneで読み、[行1, 列3] が D2
            rdf = pd.read_csv(REALIZED_PROFIT_CSV_URL, header=None)
            if rdf.shape[0] >= 2 and rdf.shape[1] >= 4:
                realized_val = +to_f(rdf.iloc[1, 3])
        except Exception as e:
            print(f"D2読み取り失敗: {e}")

        # 2. メイン資産シート
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        df['証券コード'] = df['証券コード'].astype(str).str.strip()
        # 4桁の数字（証券コード）がある行だけ抽出
        valid_df = df[df['証券コード'].str.match(r'^\d{4}$', na=False)].copy()
        codes = [f"{c}.T" for c in valid_df['証券コード']]

        # 3. 株価一括取得
        data = yf.download(codes, period="5d", group_by='ticker', threads=True, timeout=15)

        def process_row(row):
            code_t = f"{row['証券コード']}.T"
            price, day_chg, day_chg_pct, annual_div = 0.0, 0.0, 0.0, 0.0
            
            if code_t in data and not data[code_t].empty:
                t_df = data[code_t].dropna(subset=['Close'])
                if not t_df.empty:
                    price = float(t_df['Close'].iloc[-1])
                    if len(t_df) >= 2:
                        prev = float(t_df['Close'].iloc[-2])
                        day_chg = price - prev
                        day_chg_pct = (day_chg / prev) * 100
                    
                    # 配当金の取得（複数のプロパティを試す）
                    try:
                        ticker_info = yf.Ticker(code_t).info
                        annual_div = ticker_info.get('dividendRate') or ticker_info.get('trailingAnnualDividendRate') or 0.0
                    except:
                        annual_div = 0.0

            buy_p = to_f(row.get("取得時"))
            qty = int(to_f(row.get("株数")))
            profit = int((price - buy_p) * qty) if price > 0 else 0
            
            return {
                "code": row['証券コード'],
                "name": str(row.get("銘柄", ""))[:4],
                "price": price, "buy_p": buy_p, "qty": qty,
                "day_chg": day_chg, "day_chg_pct": day_chg_pct,
                "profit": profit,
                "profit_pct": round(((price - buy_p) / buy_p * 100), 1) if buy_p > 0 else 0,
                "div_amt": int(annual_div * qty)
            }

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(process_row, [row for _, row in valid_df.iterrows()]))

        total_profit = sum(r['profit'] for r in results)
        total_div = sum(r['div_amt'] for r in results)
        
        cache_storage = {
            "last_update": current_time, 
            "results": results, 
            "total_profit": total_profit, 
            "total_div": total_div,
            "total_realized": realized_val
        }
        return render_template_string(HTML_TEMPLATE, **cache_storage)

    except Exception as e:
        return f"エラーが発生しました。スプレッドシートの形式を確認してください: {e}"

HTML_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>株管理 Pro</title>
    <style>
        body { font-family: sans-serif; margin: 0; background: #f2f2f7; font-size: 13px; }
        .container { max-width: 600px; margin: 0 auto; padding: 10px; }
        .summary { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 15px; }
        .card { background: #fff; padding: 12px 5px; border-radius: 12px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .card small { color: #8e8e93; font-size: 10px; display: block; }
        .card div { font-size: 14px; font-weight: bold; margin-top: 4px; }
        .highlight { border: 2px solid #34c759; }
        .plus { color: #34c759; } .minus { color: #ff3b30; }
        .table-wrap { background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        table { width: 100%; border-collapse: collapse; }
        th { background: #f8f8f8; padding: 10px; font-size: 10px; color: #8e8e93; border-bottom: 1px solid #eee; }
        td { padding: 12px 5px; border-bottom: 1px solid #f2f2f7; text-align: center; }
        .name { text-align: left; padding-left: 10px; font-weight: bold; }
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
                    <tr><th>銘柄</th><th>現在値</th><th>前日比</th><th>損益</th></tr>
                </thead>
                <tbody>
                    {% for r in results %}
                    <tr>
                        <td class="name">{{ r.name }}<br><span style="color:#8e8e93;font-size:9px;">{{ r.code }}</span></td>
                        <td>{{ "{:,}".format(r.price|int) }}</td>
                        <td class="{{ 'plus' if r.day_chg >= 0 else 'minus' }}">{{ "{:+.1f}".format(r.day_chg_pct) }}%</td>
                        <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}">{{ "{:+,}".format(r.profit) }}</td>
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
