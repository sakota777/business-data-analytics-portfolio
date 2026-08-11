from itertools import combinations
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

tx = pd.read_csv(DATA / "transactions.csv", parse_dates=["date"])
products = pd.read_csv(DATA / "products.csv")
tx = tx.merge(products, on="product_id", how="left")
tx["sales"] = tx["quantity"] * tx["unit_price_x"]
snapshot = tx["date"].max() + pd.Timedelta(days=1)

customer = tx.groupby("customer_id").agg(
    recency=("date", lambda s: (snapshot - s.max()).days),
    frequency=("transaction_id", "nunique"),
    monetary=("sales", "sum"),
    stores_used=("store", "nunique"),
).reset_index()
for column, ascending in [("recency", False), ("frequency", True), ("monetary", True)]:
    customer[column[0].upper() + "_score"] = pd.qcut(customer[column].rank(method="first"), 5, labels=range(1, 6) if ascending else range(5, 0, -1)).astype(int)
customer["RFM_score"] = customer[["R_score", "F_score", "M_score"]].sum(axis=1)
customer["segment"] = pd.cut(customer["RFM_score"], bins=[0, 7, 11, 15], labels=["休眠・育成", "一般", "優良"])
customer.to_csv(OUT / "rfm_segments.csv", index=False, encoding="utf-8-sig")

product = tx.groupby(["product_id", "product_name", "category"], as_index=False).agg(
    sales=("sales", "sum"), customers=("customer_id", "nunique"), transactions=("transaction_id", "nunique")
).sort_values("sales", ascending=False)
product["sales_share"] = product["sales"] / product["sales"].sum()
product["cumulative_share"] = product["sales_share"].cumsum()
product["ABC"] = np.select([product["cumulative_share"] <= 0.70, product["cumulative_share"] <= 0.90], ["A", "B"], default="C")

baskets = tx.groupby("transaction_id")["product_id"].apply(lambda s: sorted(set(s)))
pair_counts = {}
for basket in baskets:
    for pair in combinations(basket, 2):
        pair_counts[pair] = pair_counts.get(pair, 0) + 1
item_transactions = tx.groupby("product_id")["transaction_id"].nunique()
n_baskets = len(baskets)
pairs = []
for (a, b), count in pair_counts.items():
    if count < 15:
        continue
    support = count / n_baskets
    confidence = count / item_transactions[a]
    lift = confidence / (item_transactions[b] / n_baskets)
    pairs.append([a, b, count, support, confidence, lift])
pair_df = pd.DataFrame(pairs, columns=["product_a", "product_b", "pair_count", "support", "confidence", "lift"])
pair_df.sort_values(["lift", "pair_count"], ascending=False).head(100).to_csv(OUT / "basket_pairs.csv", index=False, encoding="utf-8-sig")

# 販促候補は売上規模だけでなく、到達率・反復購買・併買波及・伸長余地を合成して評価する。
repeat = tx.groupby(["product_id", "customer_id"])["transaction_id"].nunique().gt(1).groupby("product_id").mean()
lift_score = pair_df.groupby("product_a")["lift"].max().combine_first(pair_df.groupby("product_b")["lift"].max())
product["repeat_rate"] = product["product_id"].map(repeat).fillna(0)
product["max_pair_lift"] = product["product_id"].map(lift_score).fillna(1)
for col in ["customers", "repeat_rate", "max_pair_lift"]:
    lo, hi = product[col].min(), product[col].max()
    product[col + "_index"] = (product[col] - lo) / (hi - lo if hi > lo else 1)
product["growth_room"] = 1 - product["customers_index"]
product["flyer_score"] = (
    0.35 * product["customers_index"] + 0.25 * product["repeat_rate_index"]
    + 0.25 * product["max_pair_lift_index"] + 0.15 * product["growth_room"]
)
product.sort_values("flyer_score", ascending=False).to_csv(OUT / "flyer_candidates.csv", index=False, encoding="utf-8-sig")

weekday = tx.assign(weekday=tx["date"].dt.day_name()).groupby("weekday", as_index=False)["sales"].sum().sort_values("sales", ascending=False)
weekday.to_csv(OUT / "weekday_sales.csv", index=False, encoding="utf-8-sig")
fig, ax = plt.subplots(figsize=(9, 5))
top = product.nlargest(12, "flyer_score").sort_values("flyer_score")
ax.barh(top["product_name"], top["flyer_score"], color="#0f766e")
ax.set_xlabel("販促候補スコア")
ax.set_title("チラシ掲載候補（合成データ）")
plt.tight_layout()
plt.savefig(OUT / "flyer_candidates.png", dpi=160)
plt.close()

segment_order = ["優良", "一般", "休眠・育成"]
segment_counts = customer["segment"].value_counts().reindex(segment_order).fillna(0)
fig, ax = plt.subplots(figsize=(8, 5))
ax.bar(segment_counts.index, segment_counts.values, color=["#0f766e", "#38bdf8", "#f59e0b"])
ax.set_xlabel("顧客区分")
ax.set_ylabel("顧客数")
ax.set_title("RFM顧客区分の構成（合成データ）")
plt.tight_layout()
plt.savefig(OUT / "rfm_segment_distribution.png", dpi=160)
plt.close()

category_sales = tx.groupby("category", as_index=False)["sales"].sum().sort_values("sales")
fig, ax = plt.subplots(figsize=(9, 5))
ax.barh(category_sales["category"], category_sales["sales"], color="#2563eb")
ax.set_xlabel("売上金額")
ax.set_title("カテゴリ別売上構成（合成データ）")
plt.tight_layout()
plt.savefig(OUT / "category_sales.png", dpi=160)
plt.close()

weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
store_weekday = tx.assign(weekday_no=tx["date"].dt.dayofweek).pivot_table(
    index="store", columns="weekday_no", values="sales", aggfunc="sum", fill_value=0
).reindex(columns=range(7))
store_weekday_share = store_weekday.div(store_weekday.sum(axis=1), axis=0)
fig, ax = plt.subplots(figsize=(9, 6))
image = ax.imshow(store_weekday_share, aspect="auto", cmap="YlGnBu")
ax.set_xticks(range(7), weekday_names)
ax.set_yticks(range(len(store_weekday_share.index)), store_weekday_share.index)
ax.set_xlabel("曜日")
ax.set_ylabel("店舗")
ax.set_title("店舗別の曜日売上構成比（合成データ）")
fig.colorbar(image, ax=ax, label="店舗内売上構成比")
plt.tight_layout()
plt.savefig(OUT / "store_weekday_heatmap.png", dpi=160)
plt.close()

multi_store_rate = customer["stores_used"].gt(1).mean()
summary = f"""# 分析結果（合成データ）\n\n- {len(customer):,}人の顧客をRFMで3区分へ分類しました。\n- 複数店舗を利用する顧客は {multi_store_rate:.1%} でした。\n- {len(product):,}商品をABC評価し、到達率・反復購買・併買波及・伸長余地からチラシ候補を順位付けしました。\n- 候補選定後は、対象商品の売上だけでなく併買額と再来店率を検証します。\n\n※すべて合成データによる説明用の結果です。\n"""
(OUT / "analysis_summary.md").write_text(summary, encoding="utf-8")
print(summary)
