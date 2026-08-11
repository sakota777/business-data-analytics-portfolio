from pathlib import Path

import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)
rng = np.random.default_rng(77)

categories = ["青果", "精肉", "鮮魚", "惣菜", "乳製品", "飲料", "菓子", "調味料"]
products = pd.DataFrame({
    "product_id": [f"P{i:03d}" for i in range(1, 81)],
    "category": np.repeat(categories, 10),
})
products["product_name"] = products["category"] + products.groupby("category").cumcount().add(1).astype(str)
base_prices = {"青果": 260, "精肉": 580, "鮮魚": 520, "惣菜": 390, "乳製品": 230, "飲料": 170, "菓子": 210, "調味料": 340}
products["unit_price"] = [int(max(80, rng.normal(base_prices[c], base_prices[c] * 0.2))) for c in products["category"]]
products.to_csv(DATA / "products.csv", index=False, encoding="utf-8-sig")

customers = [f"C{i:05d}" for i in range(1, 2001)]
stores = [f"店舗{i:02d}" for i in range(1, 11)]
dates = pd.date_range("2025-04-01", "2026-03-31", freq="D")
weights = np.array([1.35 if c in {"惣菜", "乳製品", "青果"} else 0.85 for c in products["category"]])
weights = weights / weights.sum()

rows = []
transaction_no = 1
for date in dates:
    n_transactions = int(rng.normal(105 if date.dayofweek < 5 else 135, 12))
    for _ in range(max(70, n_transactions)):
        customer = rng.choice(customers)
        home = int(customer[1:]) % len(stores)
        store_index = home if rng.random() < 0.985 else int(rng.integers(0, len(stores)))
        store = stores[store_index]
        basket_size = int(np.clip(rng.poisson(3.2) + 1, 1, 9))
        chosen = rng.choice(products.index, size=basket_size, replace=False, p=weights)
        for product_index in chosen:
            product = products.iloc[product_index]
            quantity = int(rng.choice([1, 1, 1, 2, 2, 3]))
            price = int(round(product["unit_price"] * rng.uniform(0.88, 1.05)))
            rows.append([f"T{transaction_no:07d}", customer, store, date.date(), product["product_id"], quantity, price])
        transaction_no += 1

pd.DataFrame(
    rows,
    columns=["transaction_id", "customer_id", "store", "date", "product_id", "quantity", "unit_price"],
).to_csv(DATA / "transactions.csv", index=False, encoding="utf-8-sig")
print("ID・POS分析のデモデータを生成しました。")
