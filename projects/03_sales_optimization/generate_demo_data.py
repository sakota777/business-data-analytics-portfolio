from pathlib import Path

import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)
rng = np.random.default_rng(103)
n = 3000

industry = rng.choice(["化粧品", "食品", "日用品", "研究開発", "その他"], n, p=[.28, .23, .18, .16, .15])
company_size = rng.choice(["小規模", "中規模", "大規模"], n, p=[.48, .37, .15])
source = rng.choice(["紹介", "展示会", "Web問い合わせ", "営業開拓"], n, p=[.16, .25, .34, .25])
inquiry = rng.choice(["見積依頼", "サンプル依頼", "資料請求", "情報収集"], n, p=[.17, .25, .31, .27])
contacts = np.clip(rng.poisson(2.5, n), 0, 10)
days_since_contact = rng.integers(0, 121, n)

logit = (
    -3.1
    + 0.65 * (industry == "化粧品")
    + 0.45 * (company_size == "大規模")
    + 0.75 * (source == "紹介")
    + 0.85 * (inquiry == "見積依頼")
    + 0.50 * (inquiry == "サンプル依頼")
    + 0.22 * np.minimum(contacts, 5)
    - 0.008 * days_since_contact
)
probability = 1 / (1 + np.exp(-logit))
contracted = rng.binomial(1, probability)
stage = np.where(contracted == 1, "契約", np.where(probability > .28, "商談", np.where(contacts > 0, "接触済", "未接触")))

demo = pd.DataFrame({
    "customer_id": [f"A{i:05d}" for i in range(1, n + 1)],
    "industry": industry,
    "company_size": company_size,
    "lead_source": source,
    "inquiry_type": inquiry,
    "contact_count": contacts,
    "days_since_contact": days_since_contact,
    "stage": stage,
    "contracted": contracted,
})
demo.to_csv(DATA / "salesforce_demo.csv", index=False, encoding="utf-8-sig")

# SQL例で複数テーブルの結合を再現できるよう、Salesforceの主要オブジェクト相当に分割する。
demo[["customer_id", "industry", "company_size", "lead_source", "inquiry_type"]].to_csv(
    DATA / "accounts.csv", index=False, encoding="utf-8-sig"
)
activity_rows = []
for row in demo.itertuples(index=False):
    for activity_no in range(row.contact_count):
        activity_rows.append([
            f"ACT-{row.customer_id}-{activity_no + 1}",
            row.customer_id,
            f"2026-03-{max(1, 28 - min(row.days_since_contact + activity_no * 3, 27)):02d}",
            ["電話", "メール", "商談", "資料送付"][activity_no % 4],
        ])
pd.DataFrame(activity_rows, columns=["activity_id", "customer_id", "activity_date", "activity_type"]).to_csv(
    DATA / "activities.csv", index=False, encoding="utf-8-sig"
)
demo[["customer_id", "stage", "contracted", "days_since_contact"]].assign(
    opportunity_id=lambda frame: "OPP-" + frame["customer_id"]
)[["opportunity_id", "customer_id", "stage", "contracted", "days_since_contact"]].to_csv(
    DATA / "opportunities.csv", index=False, encoding="utf-8-sig"
)
print("営業最適化のデモデータを生成しました。")
