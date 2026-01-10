from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf
import re
import os
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

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

def get_irbank_earnings_date(code):
    """IR BANKから決算発表予定日を抽出する"""
    url = f"https://irbank.net/{code}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0"}
    try:
        # タイムアウトを短く設定して全体の遅延を防ぐ
        res = requests.get(url, headers=headers, timeout=3)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # IR BANKの「決算発表日」項目を探す
        # 通常 dt要素に「決算発表日」、次のdd要素に日付が入っている
        dt_tag = soup.find('dt', string=re.compile(r'決算発表日'))
        if dt_tag:
            dd_tag = dt_tag.find_next_sibling('dd')
            if dd_tag:
                date_text = dd_tag.get_text(strip=True)
                # "2024/05/10 (金)" のような形式から "05/10" を抽出
                match = re.search(r'(\d{1,2})/(\d{1,2})', date_text)
                if match:
                    return f"{match.group(1).zfill(2)}/{match.group(2).zfill(2)}"
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

        # 2. yfinanceで株価・配当データを一括ダウンロード
        data = yf.download(codes, period="1y", group_by='ticker', threads=True, actions=True)

        # 3. 各銘柄の処理を関数化（並列実行用）
        def process_stock(row):
            c = row['証券コード']
            ticker_code = f"{c}.T"
            name = str(row.get("銘柄", ""))
            
            price, day_change, day_change_pct, annual_div = 0.0, 0.0, 0.0, 0.0
            
            # yfinanceデータの抽出
            if ticker_code in data:
                ticker_df = data[ticker_code].dropna(subset=['Close'])
                if not ticker_df.empty:
                    price = float(ticker_df['Close'].iloc[-1])
                    if len(ticker_df) >= 2:
                        prev_price = float(ticker_df['Close'].iloc[-2])
                        day_change = price - prev_price
                        day_change_pct = (day_change / prev_price) * 100
                    if 'Dividends' in ticker_df.columns:
                        annual_div = ticker_df['Dividends'].sum()

            # IR BANKから決算日を取得（ここが爆速ポイント）
            display_earnings = get_irbank_earnings_date(c)
            earnings_sort = display_earnings if "/" in display_earnings else "99/99"

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
                "earnings": earnings_sort, "display_earnings": display_earnings,
                "buy_yield": round((annual_div / buy_price * 100), 2) if buy_price > 0 else 0,
                "cur_yield": round((annual_div / price * 100), 2) if price > 0 else 0,
                "annual_div_total": int(annual_div * qty)
            }

        # 【爆速】マルチスレッドでIR BANKとデータ集計を並列実行
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(process_stock, [row for _, row in valid_df.iterrows()]))

        # 合計値の計算
        total_profit = sum(r['profit'] for r in results)
        total_dividend_income = sum(r['annual_div_total'] for r in results)

        return render_template_string(HTML_TEMPLATE, results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

    except Exception as e:
        return f"エラー: {e}"

# HTMLテンプレート（変更なし）
HTML_TEMPLATE = """
<!doctype html>
... (中略: あなたが提示したHTMLコードをここにすべて貼り付けてください) ...
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
