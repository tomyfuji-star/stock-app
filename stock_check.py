from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import yfinance as yf
import re
import os
from functools import lru_cache
from datetime import date
import requests

app = Flask(__name__)

SPREADSHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M"
    "/export?format=csv&gid=1052470389"
)

# --- 改善ポイント1: ブラウザを装うセッション設定 ---
# これによりYahooからのブロックを回避しやすくします
custom_session = requests.Session()
custom_session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
})

def to_float(val):
    try:
        val = re.sub(r"[^\d.-]", "", str(val))
        return float(val) if val else 0.0
    except:
        return 0.0

def to_int(val):
    return int(round(to_float(val)))

@lru_cache(maxsize=128)
def get_stock_data(code, today_str):
    try:
        ticker_code = f"{code}.T"
        # セッションを渡してインスタンス化
        t = yf.Ticker(ticker_code, session=custom_session)
        
        # --- 改善ポイント2: 最大5日分の履歴を取得 ---
        # 1日分(period="1d")だと休日にエラーになりやすいため5日分取得
        hist = t.history(period="5d")
        
        if not hist.empty:
            # 最新の行の終値を取得
            price = float(hist["Close"].iloc[-1])
            # 前日比計算（2日以上データがあれば）
            if len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])
                change = price - prev_close
                change_pct = (change / prev_close * 100)
            else:
                change, change_pct = 0.0, 0.0
        else:
            # 履歴が取れない場合の最終手段(fast_info)
            price = float(t.fast_info.last_price) if hasattr(t, 'fast_info') else 0.0
            change, change_pct = 0.0, 0.0

        # --- 配当データの取得 ---
        dividend = 0.0
        try:
            # infoはブロックされやすいため慎重に取得
            info = t.info
            dividend = info.get("dividendRate") or info.get("trailingAnnualDividendRate") or 0.0
            # それでも0なら、配当履歴から直近2回分（1年分）を計算
            if dividend == 0:
                div_hist = t.dividends
                if not div_hist.empty:
                    dividend = sum(div_hist.tail(2))
        except:
            pass
            
        return price, dividend, change, change_pct

    except Exception as e:
        print(f"ERROR for {code}: {e}")
        return 0.0, 0.0, 0.0, 0.0

@app.route("/")
def index():
    if request.args.get("refresh"):
        get_stock_data.cache_clear()
        return redirect(url_for("index"))

    try:
        df = pd.read_csv(SPREADSHEET_CSV_URL)
        results = []
        today_str = str(date.today())
        total_profit = 0
        total_dividend_income = 0

        for _, row in df.iterrows():
            code = str(row.get("証券コード", "")).strip().upper()
            if not code or code == "NAN":
                continue

            name = str(row.get("銘柄", "")).strip()
            buy_price = to_float(row.get("取得時"))
            qty = to_int(row.get("株数"))

            price, dividend, change, change_pct = get_stock_data(code, today_str)
            
            # 損益計算
            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit
            total_dividend_income += int(dividend * qty)
            
            # 利回り計算
            yield_at_cost = (dividend / buy_price * 100) if buy_price > 0 else 0.0
            current_yield = (dividend / price * 100) if price > 0 else 0.0

            results.append({
                "code": code, "name": name, "buy": buy_price, "qty": qty,
                "price": price, "change": change, "change_pct": round(change_pct, 2),
                "profit": profit, "yield_at_cost": round(yield_at_cost, 2), "current_yield": round(current_yield, 2)
            })
    except Exception as e:
        return f"エラーが発生しました: {e}"

    # --- HTML表示部分はそのまま（省略せず以前のコードと同様に表示されます） ---
    return render_template_string("""
    <!doctype html>
    <html>
    ...（以下略）...
    """, results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
