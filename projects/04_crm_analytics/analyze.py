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
df = pd.read_csv(DATA / "daily_funnel.csv", parse_dates=["date"])

channel = df.groupby("channel", as_index=False).agg(
    ad_spend=("ad_spend", "sum"), impressions=("impressions", "sum"), clicks=("clicks", "sum"),
    line_registrations=("line_registrations", "sum"), consultations=("consultations", "sum"),
    applications=("applications", "sum"), contracts=("contracts", "sum"),
)
channel["click_rate"] = channel["clicks"] / channel["impressions"]
channel["registration_cvr"] = channel["line_registrations"] / channel["clicks"]
channel["consultation_cvr"] = channel["consultations"] / channel["line_registrations"]
channel["contract_cvr"] = channel["contracts"] / channel["line_registrations"]
channel["cost_per_registration"] = channel["ad_spend"] / channel["line_registrations"].replace(0, np.nan)
channel["cost_per_contract"] = channel["ad_spend"] / channel["contracts"].replace(0, np.nan)
channel.to_csv(OUT / "channel_funnel.csv", index=False, encoding="utf-8-sig")

# 標準化した説明変数で、LINE登録数との関係を比較する。
features = ["ad_spend", "impressions", "clicks"]
x = df[features].astype(float)
x_standard = (x - x.mean()) / x.std(ddof=0)
y = (df["line_registrations"] - df["line_registrations"].mean()) / df["line_registrations"].std(ddof=0)
matrix = np.column_stack([np.ones(len(x_standard)), x_standard.to_numpy()])
coef = np.linalg.lstsq(matrix, y.to_numpy(), rcond=None)[0][1:]
regression = pd.DataFrame({"feature": features, "standardized_coefficient": coef}).sort_values("standardized_coefficient", ascending=False)
regression.to_csv(OUT / "registration_regression.csv", index=False, encoding="utf-8-sig")

monthly = df.assign(month=df["date"].dt.to_period("M").astype(str)).groupby("month", as_index=False).agg(
    registrations=("line_registrations", "sum"), consultations=("consultations", "sum"), contracts=("contracts", "sum")
)
monthly.to_csv(OUT / "monthly_funnel.csv", index=False, encoding="utf-8-sig")

fig, ax = plt.subplots(figsize=(9, 5))
stages = ["clicks", "line_registrations", "consultations", "applications", "contracts"]
labels = ["クリック", "LINE登録", "相談", "申込", "契約"]
totals = df[stages].sum()
ax.bar(labels, totals.values, color=["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd"])
ax.set_yscale("log")
ax.set_ylabel("件数（対数表示）")
ax.set_title("広告流入から契約までのファネル（合成データ）")
plt.tight_layout()
plt.savefig(OUT / "funnel.png", dpi=160)
plt.close()

channel_order = channel.sort_values("contract_cvr", ascending=False)
positions = np.arange(len(channel_order))
width = 0.36
fig, ax = plt.subplots(figsize=(9, 5))
ax.bar(positions - width / 2, channel_order["registration_cvr"], width, label="クリック→LINE登録")
ax.bar(positions + width / 2, channel_order["contract_cvr"], width, label="LINE登録→契約")
ax.set_xticks(positions, channel_order["channel"])
ax.set_ylabel("転換率")
ax.yaxis.set_major_formatter(lambda value, position: f"{value:.0%}")
ax.set_title("チャネル別の転換率（合成データ）")
ax.legend()
plt.tight_layout()
plt.savefig(OUT / "channel_conversion.png", dpi=160)
plt.close()

fig, ax1 = plt.subplots(figsize=(10, 5))
ax1.plot(monthly["month"], monthly["registrations"], marker="o", color="#2563eb", label="LINE登録")
ax1.plot(monthly["month"], monthly["consultations"], marker="o", color="#0f766e", label="相談")
ax1.set_ylabel("LINE登録・相談件数")
ax2 = ax1.twinx()
ax2.plot(monthly["month"], monthly["contracts"], marker="o", color="#dc2626", label="契約")
ax2.set_ylabel("契約件数")
ax1.tick_params(axis="x", rotation=45)
lines = ax1.lines + ax2.lines
ax1.legend(lines, [line.get_label() for line in lines], loc="upper left")
ax1.set_title("月次ファネル推移（合成データ）")
plt.tight_layout()
plt.savefig(OUT / "monthly_funnel_trend.png", dpi=160)
plt.close()

paid = channel[channel["ad_spend"] > 0].sort_values("cost_per_contract")
fig, ax = plt.subplots(figsize=(8, 5))
positions = np.arange(len(paid))
ax.bar(positions - width / 2, paid["cost_per_registration"], width, label="LINE登録単価")
ax.bar(positions + width / 2, paid["cost_per_contract"], width, label="契約獲得単価")
ax.set_xticks(positions, paid["channel"])
ax.set_ylabel("獲得単価")
ax.set_title("有料チャネル別の獲得単価（合成データ）")
ax.legend()
plt.tight_layout()
plt.savefig(OUT / "channel_acquisition_cost.png", dpi=160)
plt.close()

best = channel.sort_values("contract_cvr", ascending=False).iloc[0]
summary = f"""# 分析結果（合成データ）\n\n- 4チャネルについて、広告流入から契約までのファネルと獲得単価を算出しました。\n- LINE登録後の契約率が最も高いチャネルは「{best['channel']}」で、{best['contract_cvr']:.1%} でした。\n- 回帰分析では因果を断定せず、次に検証する施策仮説の優先順位付けに利用します。\n- 実運用では週次で離脱率と獲得単価を確認し、広告・LP・追客の変更へ接続します。\n\n※すべて合成データによる説明用の結果です。\n"""
(OUT / "analysis_summary.md").write_text(summary, encoding="utf-8")
print(summary)
