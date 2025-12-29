from flask import Flask, render_template_string
import pandas as pd
import yfinance as yf

print("===== VERSION 2025-12-29 FIXED pd import =====")

app = Flask(__name__)

# GoogleスプレッドシートCSV
CSV_URL = "https://docs.google.com/spreadsheets/d/1vwvK6QfG9LUL5CsR9jSbjNvE4CGjwtk03kjxNiEmR_M/export?format=csv&gid=1052470389"

@app.route("/")
def index():
    df = pd.read_csv(CSV_URL)

    print("Columns:", df.columns.tolist())

    results = []

    for _, row in df.iterrows():
        try:
            code_raw = str(row["証券コード"]).strip()
            buy_price = float(row["取得時"])

            # 数字のみ（通常銘柄）
            if code_raw.isdigit():
                ticker = code_raw + ".T"
            else:
                # 409A, 350A など
                ticker = code_raw + ".T"

            stock = yf
