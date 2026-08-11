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

ALIASES = {
    "レジ": {"レジ", "会計", "キャッシャー", "POS対応"},
    "品出し": {"品出し", "商品補充", "棚補充", "補充作業"},
    "惣菜": {"惣菜", "デリカ", "惣菜調理", "弁当製造"},
    "清掃": {"清掃", "店内清掃", "クリンリネス"},
    "発注・在庫": {"発注", "在庫確認", "棚卸", "発注在庫"},
}
lookup = {alias: canonical for canonical, names in ALIASES.items() for alias in names}

operations = pd.read_csv(DATA / "operation_log.csv")
operations["standard_task"] = operations["raw_task_name"].map(lookup).fillna("その他")
task_summary = operations.groupby(["store", "standard_task"], as_index=False).agg(
    median_minutes=("minutes", "median"), records=("minutes", "size")
)
task_summary.to_csv(OUT / "normalized_task_summary.csv", index=False, encoding="utf-8-sig")

sales = pd.read_csv(DATA / "hourly_sales.csv", parse_dates=["date"])
shift = pd.read_csv(DATA / "current_shift.csv", parse_dates=["date"])
shift["weekday"] = shift["date"].dt.dayofweek
forecast = sales.groupby(["store", "weekday", "hour"], as_index=False).agg(
    predicted_visitors=("visitors", "mean"), predicted_sales_yen=("sales_yen", "mean")
)

# レジ・品出しは需要連動、惣菜・清掃・発注は固定業務として必要工数へ変換する。
forecast["demand_minutes"] = forecast["predicted_visitors"] * 2.7
forecast["fixed_minutes"] = np.where(forecast["hour"].isin([8, 9, 20, 21]), 105, 48)
forecast["required_staff"] = np.maximum(2, np.ceil((forecast["demand_minutes"] + forecast["fixed_minutes"]) / 50)).astype(int)
current = shift.groupby(["store", "weekday", "hour"], as_index=False)["current_staff"].mean()
plan = forecast.merge(current, on=["store", "weekday", "hour"])
plan["current_staff"] = plan["current_staff"].round().astype(int)
plan["staff_gap"] = plan["required_staff"] - plan["current_staff"]
plan.to_csv(OUT / "recommended_staffing.csv", index=False, encoding="utf-8-sig")

hourly = plan.groupby("hour", as_index=False).agg(
    predicted_visitors=("predicted_visitors", "mean"),
    current_staff=("current_staff", "mean"),
    required_staff=("required_staff", "mean"),
)
fig, ax1 = plt.subplots(figsize=(10, 5))
ax1.plot(hourly["hour"], hourly["predicted_visitors"], marker="o", color="#2563eb", label="予測来店数")
ax1.set_xlabel("時間帯")
ax1.set_ylabel("予測来店数")
ax2 = ax1.twinx()
ax2.plot(hourly["hour"], hourly["current_staff"], color="#9ca3af", label="現行人数")
ax2.plot(hourly["hour"], hourly["required_staff"], color="#dc2626", label="推奨人数")
ax2.set_ylabel("平均配置人数")
lines = ax1.lines + ax2.lines
ax1.legend(lines, [line.get_label() for line in lines], loc="upper left")
plt.title("時間帯別の需要予測と推奨人員（デモ）")
plt.tight_layout()
plt.savefig(OUT / "staffing_by_hour.png", dpi=160)
plt.close()

shortage = int((plan["staff_gap"] > 0).sum())
surplus = int((plan["staff_gap"] < 0).sum())
summary = f"""# デモ分析結果\n\n- 店舗別名を共通の5業務へ名寄せしました。\n- 店舗・曜日・時間帯別に {len(plan):,} 区分の推奨人数を算出しました。\n- 現行配置で人員不足となる区分は {shortage:,} 件、余剰となる区分は {surplus:,} 件でした。\n- 昼と夕方の需要ピークに加え、開店・閉店業務を必要工数へ反映しています。\n\n※すべて合成データによる説明用の結果です。\n"""
(OUT / "analysis_summary.md").write_text(summary, encoding="utf-8")
print(summary)
