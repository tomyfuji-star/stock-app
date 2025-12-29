df = pd.read_csv(CSV_URL, skiprows=1)

results = []

for _, row in df.iterrows():
    try:
        code_raw = str(row["証券コード"]).strip()

        # 数字のみ → 東証プライムなど
        if code_raw.isdigit():
            code = code_raw + ".T"
        else:
            # 409A, 350A などは一旦スキップ（yfinance非対応）
            results.append({
                "code": code_raw,
                "buy_price": row["取得時"],
                "current_price": "対象外",
                "profit": "—"
            })
            continue

        buy_price = float(row["取得時"])

        ticker = yf.Ticker(code)
        price = ticker.info.get("regularMarketPrice")

        profit = (price - buy_price) / buy_price * 100 if price else None

        results.append({
            "code": code_raw,
            "buy_price": buy_price,
            "current_price": price,
            "profit": f"{profit:.2f}%" if profit else "取得失敗"
        })

    except Exception as e:
        results.append({
            "code": row.get("証券コード", "不明"),
            "buy_price": "エラー",
            "current_price": "エラー",
            "profit": str(e)
        })
