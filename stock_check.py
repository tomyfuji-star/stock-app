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
    "results": None,
    "total_profit": 0,
    "total_div": 0,
    "total_realized": 0
}

CACHE_TIMEOUT = 300 

# メイン資産シート
SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

# 損益計算シート (D2セル取得用)
REALIZED_PROFIT_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1416973059"
)

def to_float(val):
    try:
        val = re.sub(r"[^\d.-]", "", str(val))
        return float(val) if val else 0.0
    except:
        return 0.0

@app.route("/")
def index():
    global cache_storage
    current_time = time.time()
    force_update = request.args.get('update_earnings') == '1'

    # キャッシュ有効チェック
    if not force_update and cache_storage["results"] and (current_time - cache_storage["last_update"] < CACHE_TIMEOUT):
        return render_template_string(HTML_TEMPLATE, **cache_storage)

    try:
        # 1. 損益計算シートのD2セルを取得（最優先）
        current_realized = 0
        try:
            # header=None で読み込み、確実に2行目・4列目を指定
            rdf = pd.read_csv(REALIZED_PROFIT_CSV_URL, header=None)
            if rdf.shape[0] >= 2 and rdf.shape[1] >= 4:
                # [1, 3] がスプレッドシート上の D2 (2行目4列目)
                current_realized = to_float(rdf.iloc[1, 3])
        except Exception as e:
            print(f"D2取得エラー: {e}")

        # 2. メイン資産シート読み込み
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        df['証券コード'] = df['証券コード'].astype(str).str.strip().str.upper()
        valid_df = df[df['証券コード'].str.match(r'^[A-Z0-9]{4}$', na=False)].copy()
        codes = [f"{c}.T" for c in valid_df['証券コード']]

        # 3. yfinanceで株価取得
        data = yf.download(codes, period="1y", group_by='ticker', threads=True)

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

            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))
            profit = int((price - buy_price) * qty) if price > 0 else 0
            
            return {
                "code": c, "name": str(row.get("銘柄", ""))[:4],
                "price": price, "buy_price": buy_price, "qty": qty,
                "day_change": day_change, "day_change_pct": round(day_change_pct, 2),
                "profit": profit, 
                "profit_pct": round(((price - buy_price) / buy_price * 100), 1) if buy_price > 0 else 0,
                "div_amt": int(annual_div * qty),
                "display_earnings": str(row.get("決算発表日", "---")),
                "memo": str(row.get("メモ", "")) if not pd.isna(row.get("メモ")) else ""
            }

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(process_row, [row for _, row in valid_df.iterrows()]))

        # 4. 合計の計算
        total_profit = sum(r['profit'] for r in results)
        total_div = sum(r['div_amt'] for r in results)
        
        # 5. キャッシュ保存
        cache_storage = {
            "results": results, 
            "total_profit": total_profit, 
            "total_div": total_div,
            "total_realized": current_realized,
            "last_update": current_time
        }
        
        # 6. 画面表示（ここで total_realized を渡す）
        return render_template_string(HTML_TEMPLATE, 
                                     results=results, 
                                     total_profit=total_profit, 
                                     total_dividend_income=total_div,
                                     total_realized=current_realized)

    except Exception as e:
        return f"システムエラーが発生しました: {e}"

HTML_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <title>資産管理 Pro</title>
    <style>
        body { font-family: -apple-system, sans-serif; margin: 0; background: #f2f2f7; color: #1c1c1e; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 800px; padding: 10px; box-sizing: border-box; }
        .summary { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 15px; }
        .card { background: #fff; padding: 12px 4px; border-radius: 12px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .card.highlight { border: 2px solid #34c759; background: #fafffa; }
        .card small { color: #8e8e93; font-size: 10px; display: block; margin-bottom: 4px; }
        .card div { font-size: 14px; font-weight: bold; }
        .plus { color: #34c759; }
        .minus { color: #ff3b30; }
        .table-wrap { background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th { background: #f8f8f8; padding: 10px; color: #8e8e93; font-size: 11px; border-bottom: 1px solid #eee; }
        td { padding: 12px 8px; border-bottom: 1px solid #f2f2f7; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="summary">
            <div class="card"><small>評価損益</small><div class="{{ 'plus' if total_profit >= 0 else 'minus' }}">¥{{ "{:,}".format(total_profit) }}</div></div>
            
            <div class="card highlight">
                <small>トータル実利</small>
                <div class="{{ 'plus' if (total_profit + total_realized) >= 0 else 'minus' }}">
                    ¥{{ "{:,}".format((total_profit + total_realized)|int) }}
                </div>
            </div>

            <div class="card"><small>年配当予想</small><div style="color: #007aff;">¥{{ "{:,}".format(total_dividend_income) }}</div></div>
        </div>

        <div class="table-wrap">
            <table>
                <thead>
                    <tr><th>銘柄</th><th>現在値</th><th>評価損益</th><th>利回り</th></tr>
                </thead>
                <tbody>
                    {% for r in results %}
                    <tr>
                        <td style="text-align:left;"><strong>{{ r.name }}</strong><br><small style="color:#8e8e93">{{ r.code }}</small></td>
                        <td>{{ "{:,}".format(r.price|int) }}</td>
                        <td class="{{ 'plus' if r.profit >= 0 else 'minus' }}">{{ "{:+,}".format(r.profit) }}<br><small>{{ r.profit_pct }}%</small></td>
                        <td>{{ r.display_earnings }}</td>
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
