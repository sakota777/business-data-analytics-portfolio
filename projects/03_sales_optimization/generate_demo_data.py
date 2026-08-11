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

pd.DataFrame({
    "customer_id": [f"A{i:05d}" for i in range(1, n + 1)],
    "industry": industry,
    "company_size": company_size,
    "lead_source": source,
    "inquiry_type": inquiry,
    "contact_count": contacts,
    "days_since_contact": days_since_contact,
    "stage": stage,
    "contracted": contracted,
}).to_csv(DATA / "salesforce_demo.csv", index=False, encoding="utf-8-sig")
print("営業最適化のデモデータを生成しました。")
