from flask import Flask, render_template_string, request, redirect, url_for
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

@lru_cache(maxsize=128)
def get_stock_data(code, today_str):
    try:
        ticker_code = f"{code}.T"
        t = yf.Ticker(ticker_code)
        
        # 修正ポイント：2日分で取れない場合を考慮し5日分取得して最新の2行を使う
        hist = t.history(period="5d")
        
        if not hist.empty and len(hist) >= 1:
            price = float(hist["Close"].iloc[-1])
            # 前日比計算用
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0.0
        else:
            # 最終手段として info から取得を試みる
            price = t.info.get("regularMarketPrice") or t.info.get("previousClose") or 0.0
            change, change_pct = 0.0, 0.0
            
        dividend = t.info.get("dividendRate") or t.info.get("trailingAnnualDividendRate") or 0.0
        
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
            
            # priceが0の場合は計算をスキップして異常を知らせる
            profit = int((price - buy_price) * qty) if price > 0 else 0
            total_profit += profit
            total_dividend_income += int(dividend * qty)
            
            yield_at_cost = (dividend / buy_price * 100) if buy_price > 0 else 0.0
            current_yield = (dividend / price * 100) if price > 0 else 0.0

            results.append({
                "code": code,
                "name": name,
                "buy": buy_price,
                "qty": qty,
                "price": price,
                "change": change,
                "change_pct": round(change_pct, 2),
                "profit": profit,
                "yield_at_cost": round(yield_at_cost, 2),
                "current_yield": round(current_yield, 2)
            })
    except Exception as e:
        return f"エラーが発生しました: {e}"

    return render_template_string("""
""", results=results, total_profit=total_profit, total_dividend_income=total_dividend_income)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
