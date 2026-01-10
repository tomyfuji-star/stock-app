from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import re
import os
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor # 並列処理用

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/favicon.svg')
def favicon():
    return app.send_static_file('favicon.svg')

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

def get_kabutan_earnings_date(code):
    """株探から決算発表予定日を抽出する（高速化のためタイムアウトを短めに設定）"""
    url = f"https://kabutan.jp/stock/finance?code={code}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0"}
    try:
        res = requests.get(url, headers=headers, timeout=3) # 3秒で諦める
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 複数の場所から日付を抽出
        for selector in ['dd', 'div.f_announcement_date', 'table.stock_table']:
            found = soup.find(string=re.compile(r'\d{2}/\d{2}'))
            if found:
                date_match = re.search(r'\d{2}/\d{2}', found)
                if date_match: return date_match.group()
        return "未定"
    except:
        return "---"

@app.route("/")
def index():
    try:
        # 1. スプレッドシート読み込み
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        df['証券コード'] = df['証券コード'].astype(str).str.strip().str.upper()
        valid_df = df[df['証券コード'].str.match(r'^[A-Z0-9]{4}$', na=False)].copy()
        codes = [f"{c}.T" for c in valid_df['証券コード']]

        # 2. yfinanceで株価を一括ダウンロード (これは元々速い)
        ydata = yf.download(codes, period="5d", group_by='ticker', threads=True)

        # 3. 各銘柄の詳細情報を並列で取得する関数
        def process_stock(row):
            c = row['証券コード']
            ticker_code = f"{c}.T"
            
            # 株価データの抽出
            price, day_change, day_change_pct, annual_div = 0.0, 0.0, 0.0, 0.0
            if ticker_code in ydata:
                ticker_df = ydata[ticker_code].dropna(subset=['Close'])
                if not ticker_df.empty:
                    price = float(ticker_df['Close'].iloc[-1])
                    if len(ticker_df) >= 2:
                        prev_price = float(ticker_df['Close'].iloc[-2])
                        day_change = price - prev_price
                        day_change_pct = (day_change / prev_price) * 100
                    # 配当は個別で取得すると遅いため、ここでは簡易的に0表示か
                    # 必要なら yf.Ticker(c).info を使うが、速度優先なら回避
            
            # 株探から決算日を取得
            display_earnings = get_kabutan_earnings_date(c)
            earnings_sort = display_earnings if "/" in display_earnings else "99/99"

            buy_price = to_float(row.get("取得時"))
            qty = int(to_float(row.get("株数")))
            profit = int((price - buy_price) * qty) if price > 0 else 0
            
            return {
                "code": c, "name": str(row.get("銘柄", ""))[:4], "full_name": str(row.get("銘柄", "")),
                "price": price, "buy_price": buy_price, "qty": qty,
                "market_value": int(price * qty),
                "day_change": day_change, "day_change_pct": round(day_change_pct, 2),
                "profit": profit, "profit_pct": round((profit / (buy_price * qty) * 100), 1) if buy_price > 0 else 0,
                "memo": str(row.get("メモ", "")) if not pd.isna(row.get("メモ")) else "",
                "earnings": earnings_sort, "display_earnings": display_earnings,
                "buy_yield": 0, # 速度重視のため一旦0。必要なら yf.Ticker の一括処理が必要
                "cur_yield": 0
            }

        # 【爆速ポイント】最大20個の並列作業員で一斉処理
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(process_stock, [row for _, row in valid_df.iterrows()]))

        # 合計計算
        total_profit = sum(r['profit'] for r in results)
        
        return render_template_string(HTML_TEMPLATE, results=results, total_profit=total_profit)

    except Exception as e:
        return f"エラー: {e}"

# HTML_TEMPLATE は前回と同じため省略（変数として定義して呼び出す形にしてください）
HTML_TEMPLATE = """
(ここに前回のHTMLコードをそのまま貼り付けてください)
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
