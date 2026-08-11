from pathlib import Path

import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)
rng = np.random.default_rng(42)

stores = [f"店舗{i:02d}" for i in range(1, 9)]
dates = pd.date_range("2026-01-05", periods=56, freq="D")
hours = range(8, 22)

sales_rows = []
shift_rows = []
for store_no, store in enumerate(stores):
    store_factor = 0.85 + store_no * 0.05
    for date in dates:
        weekend = 1.22 if date.dayofweek >= 5 else 1.0
        for hour in hours:
            peak = 1 + 0.75 * np.exp(-((hour - 12) / 2.2) ** 2) + 0.95 * np.exp(-((hour - 18) / 2.0) ** 2)
            visitors = max(8, int(rng.normal(24 * store_factor * weekend * peak, 4)))
            basket = rng.normal(2_350, 180)
            sales_rows.append([store, date.date(), date.dayofweek, hour, visitors, round(visitors * basket)])
            baseline = 3 + int(visitors >= 38) + int(visitors >= 65)
            current_staff = max(2, baseline + int(rng.choice([-1, 0, 0, 1])))
            shift_rows.append([store, date.date(), hour, current_staff])

pd.DataFrame(
    sales_rows,
    columns=["store", "date", "weekday", "hour", "visitors", "sales_yen"],
).to_csv(DATA / "hourly_sales.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(
    shift_rows,
    columns=["store", "date", "hour", "current_staff"],
).to_csv(DATA / "current_shift.csv", index=False, encoding="utf-8-sig")

aliases = {
    "レジ": ["レジ", "会計", "キャッシャー", "POS対応"],
    "品出し": ["品出し", "商品補充", "棚補充", "補充作業"],
    "惣菜": ["惣菜", "デリカ", "惣菜調理", "弁当製造"],
    "清掃": ["清掃", "店内清掃", "クリンリネス"],
    "発注・在庫": ["発注", "在庫確認", "棚卸", "発注在庫"],
}
operation_rows = []
for store in stores:
    for canonical, names in aliases.items():
        base_minutes = {"レジ": 160, "品出し": 210, "惣菜": 260, "清掃": 95, "発注・在庫": 110}[canonical]
        for _ in range(35):
            operation_rows.append([
                store,
                rng.choice(names),
                round(max(20, rng.normal(base_minutes, base_minutes * 0.16)), 1),
            ])
pd.DataFrame(operation_rows, columns=["store", "raw_task_name", "minutes"]).to_csv(
    DATA / "operation_log.csv", index=False, encoding="utf-8-sig"
)

print("シフト最適化のデモデータを生成しました。")
