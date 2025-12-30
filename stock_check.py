from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import re
import os
from functools import lru_cache
from datetime import date

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

def to_int(val):
    return int(round(to_float(val)))

# 修正ポイント：引数に today を追加してキャッシュが毎日更新されるようにします
@lru_cache(maxsize=128)
def get_current_price(code, today_str):
    try:
        # 日本株の場合、コードに .T を付与
        ticker_code = f"{code}.T"
        t = yf.Ticker(ticker_code)

        # 履歴データから直近の終値を取得（infoより安定しています）
        hist = t.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        
        # 1日で取れない場合は5日で再試行
        hist = t.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].dropna().iloc[-1])

        return 0.0
    except Exception as e:
        print(f"PRICE ERROR for {code}: {e}")
        return 0.0

@app.route("/")
def index():
    try:
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        results = []
        # キャッシュキーとして使うための今日の日付（文字列）
        today_str = str(date.today())

        for _, row in df.iterrows():
            code = str(row.get("証券コード", "")).strip()
            # 証券コードが空、または数値でない（見出しなど）場合はスキップ
            if not code or code.lower() == "nan" or not code.isdigit():
                continue

            name = str(row.get("銘柄", "")).strip()
            buy_price = to_float(row.get("取得時"))
            qty = to_int(row.get("株数"))

            # 修正ポイント：関数定義に合わせて呼び出し
            price = get_current_price(code, today_str)
            profit = int((price - buy_price) * qty)

            results.append({
                "code": code,
                "name": name,
                "buy": f"{int(buy_price):,}",
                "qty": f"{qty:,}",
                "price": f"{int(price):,}",
                "profit": f"{profit:,}",
                "profit_raw": profit
            })
    except Exception as e:
        return f"CSV読み込みエラー: {e}"

    return render_template_string("""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>保有株一覧</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 10px; background-color: #f8f9fa; }
h2 { text-align: center; color: #333; }
table { width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
th, td { padding: 10px; border: 1px solid #dee2e6; text-align: center; }
th { background: #e9ecef; }
td.num { text-align: right; font-family: monospace; }
.plus { color: #28a745; font-weight: bold; }
.minus { color: #dc3545; font-weight: bold; }
</style>
</head>
<body>
<h2>保有株一覧</h2>
<table>
<tr>
<th>コード</th>
<th>銘柄</th>
<th>取得単価</th>
<th>株数</th>
<th>現在価格</th>
<th>評価損益</th>
</tr>
{% for r in results %}
<tr>
<td>{{ r.code }}</td>
<td>{{ r.name }}</td>
<td class="num">{{ r.buy }}</td>
<td class="num">{{ r.qty }}</td>
<td class="num">{{ r.price }}</td>
<td class="num">
<span class="{{ 'plus' if r.profit_raw >= 0 else 'minus' }}">
{{ r.profit }}
</span>
</td>
</tr>
{% endfor %}
</table>
</body>
</html>
""", results=results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
