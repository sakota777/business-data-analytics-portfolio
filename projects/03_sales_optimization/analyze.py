from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent
DATA, OUT = BASE / "data", BASE / "outputs"
OUT.mkdir(exist_ok=True)
available_fonts = {font.name for font in font_manager.fontManager.ttflist}
for font_name in ["Yu Gothic", "Meiryo", "Noto Sans CJK JP", "IPAexGothic"]:
    if font_name in available_fonts:
        plt.rcParams["font.family"] = font_name
        break
plt.rcParams["axes.unicode_minus"] = False
df = pd.read_csv(DATA / "salesforce_demo.csv")

# 説明可能性を優先し、過去契約率を平滑化したカテゴリ得点を合成する。
global_rate = df["contracted"].mean()
score = pd.Series(np.zeros(len(df)), index=df.index)
detail = []
for column in ["industry", "company_size", "lead_source", "inquiry_type"]:
    stats = df.groupby(column)["contracted"].agg(["sum", "count"])
    stats["smoothed_rate"] = (stats["sum"] + 20 * global_rate) / (stats["count"] + 20)
    score += df[column].map(stats["smoothed_rate"]).fillna(global_rate)
    view = stats.reset_index().rename(columns={column: "category_value"})
    view.insert(0, "feature", column)
    detail.append(view)
score = score / 4
activity_adjustment = np.minimum(df["contact_count"], 5) * .025 - np.minimum(df["days_since_contact"], 90) * .0008
df["prospect_score"] = (100 * np.clip(score + activity_adjustment, 0, 1)).round(1)
df["priority"] = pd.qcut(df["prospect_score"].rank(method="first"), 3, labels=["低", "中", "高"])
df["recommended_action"] = np.select(
    [
        (df["priority"] == "高") & (df["days_since_contact"] >= 14),
        (df["priority"] == "高"),
        (df["priority"] == "中") & (df["contact_count"] == 0),
    ],
    ["優先フォロー", "商談状況を確認", "初回接触"],
    default="定期情報提供",
)
targets = df[df["contracted"] == 0].sort_values(["prospect_score", "days_since_contact"], ascending=[False, False])
targets.head(300).to_csv(OUT / "priority_customer_list.csv", index=False, encoding="utf-8-sig")
pd.concat(detail, ignore_index=True).to_csv(OUT / "conversion_by_attribute.csv", index=False, encoding="utf-8-sig")

df["score_band"] = pd.cut(df["prospect_score"], bins=[0, 15, 20, 25, 30, 40, 100], include_lowest=True)
validation = df.groupby("score_band", observed=True).agg(customers=("customer_id", "size"), contract_rate=("contracted", "mean")).reset_index()
validation["score_band"] = validation["score_band"].astype(str)
validation.to_csv(OUT / "score_validation.csv", index=False, encoding="utf-8-sig")

fig, ax = plt.subplots(figsize=(9, 5))
ax.bar(validation["score_band"], validation["contract_rate"], color="#7c3aed")
ax.set_xlabel("見込みスコア帯")
ax.set_ylabel("契約率")
ax.set_title("見込みスコア帯別の契約率（合成データ）")
ax.tick_params(axis="x", rotation=25)
plt.tight_layout()
plt.savefig(OUT / "conversion_by_score.png", dpi=160)
plt.close()

source_rate = df.groupby("lead_source", as_index=False).agg(
    customers=("customer_id", "size"), contract_rate=("contracted", "mean")
).sort_values("contract_rate")
fig, ax = plt.subplots(figsize=(8, 5))
ax.barh(source_rate["lead_source"], source_rate["contract_rate"], color="#2563eb")
ax.set_xlabel("契約率")
ax.set_title("流入経路別の契約率（合成データ）")
ax.xaxis.set_major_formatter(lambda value, position: f"{value:.0%}")
plt.tight_layout()
plt.savefig(OUT / "conversion_by_source.png", dpi=160)
plt.close()

contact_rate = df.groupby("contact_count", as_index=False).agg(
    customers=("customer_id", "size"), contract_rate=("contracted", "mean")
)
contact_rate = contact_rate[contact_rate["customers"] >= 25]
fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(contact_rate["contact_count"], contact_rate["contract_rate"], marker="o", color="#7c3aed")
ax.set_xlabel("営業接触回数")
ax.set_ylabel("契約率")
ax.set_title("営業接触回数と契約率（25件以上の区分・合成データ）")
ax.yaxis.set_major_formatter(lambda value, position: f"{value:.0%}")
ax.grid(alpha=0.25)
plt.tight_layout()
plt.savefig(OUT / "conversion_by_contacts.png", dpi=160)
plt.close()

priority_summary = df.groupby("priority", observed=True).agg(
    customers=("customer_id", "size"), contract_rate=("contracted", "mean")
).reindex(["低", "中", "高"])
fig, ax1 = plt.subplots(figsize=(8, 5))
ax1.bar(priority_summary.index, priority_summary["customers"], color="#c4b5fd", label="顧客数")
ax1.set_xlabel("営業優先度")
ax1.set_ylabel("顧客数")
ax2 = ax1.twinx()
ax2.plot(priority_summary.index, priority_summary["contract_rate"], marker="o", color="#dc2626", label="契約率")
ax2.set_ylabel("契約率")
ax2.yaxis.set_major_formatter(lambda value, position: f"{value:.0%}")
ax1.set_title("営業優先度別の顧客数と契約率（合成データ）")
ax1.legend([ax1.patches[0], ax2.lines[0]], ["顧客数", "契約率"], loc="upper left")
plt.tight_layout()
plt.savefig(OUT / "priority_performance.png", dpi=160)
plt.close()

high_rate = df.loc[df["priority"] == "高", "contracted"].mean()
summary = f"""# 分析結果（合成データ）\n\n- {len(df):,}件の営業データから、説明可能な見込みスコアを算出しました。\n- 全体契約率は {global_rate:.1%}、高優先度群の契約率は {high_rate:.1%} でした。\n- 未契約顧客から優先対応300件と推奨アクションを出力しました。\n- 実運用では営業結果を定期的に取り込み、得点と閾値を見直します。\n\n※すべて合成データによる説明用の結果です。\n"""
(OUT / "analysis_summary.md").write_text(summary, encoding="utf-8")
print(summary)
