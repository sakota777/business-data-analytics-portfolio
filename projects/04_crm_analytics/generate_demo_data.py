from pathlib import Path

import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)
rng = np.random.default_rng(219)

dates = pd.date_range("2025-04-01", periods=365, freq="D")
channels = ["検索広告", "SNS広告", "自然検索", "紹介"]
rows = []
for day_index, date in enumerate(dates):
    trend = 1 + day_index / 500
    for channel in channels:
        base = {"検索広告": 19000, "SNS広告": 15000, "自然検索": 4500, "紹介": 2500}[channel]
        spend = max(0, rng.normal(base, base * .16)) if channel in {"検索広告", "SNS広告"} else 0
        impressions = int(max(150, spend * rng.uniform(4.5, 7.5) if spend else rng.normal(2200, 300)))
        click_rate = {"検索広告": .043, "SNS広告": .028, "自然検索": .075, "紹介": .095}[channel]
        clicks = max(3, int(rng.binomial(impressions, min(.15, click_rate * trend))))
        registrations = rng.binomial(clicks, {"検索広告": .12, "SNS広告": .09, "自然検索": .16, "紹介": .23}[channel])
        consultations = rng.binomial(registrations, {"検索広告": .30, "SNS広告": .23, "自然検索": .34, "紹介": .42}[channel])
        applications = rng.binomial(consultations, .57)
        contracts = rng.binomial(applications, {"検索広告": .36, "SNS広告": .30, "自然検索": .40, "紹介": .49}[channel])
        rows.append([date.date(), channel, round(spend), impressions, clicks, registrations, consultations, applications, contracts])

pd.DataFrame(rows, columns=[
    "date", "channel", "ad_spend", "impressions", "clicks", "line_registrations",
    "consultations", "applications", "contracts",
]).to_csv(DATA / "daily_funnel.csv", index=False, encoding="utf-8-sig")
print("CRM分析のデモデータを生成しました。")
