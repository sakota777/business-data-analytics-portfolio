-- BigQuery Standard SQL
-- 広告、Lステップ、Notion相当の別ソースをイベント形式へ統合し、
-- 日次・チャネル別のファネルマートを作成する。

CREATE OR REPLACE TABLE `portfolio_demo.crm_funnel_mart` AS
WITH source_events AS (
  SELECT DATE(date) AS event_date, channel, '表示' AS stage, impressions AS event_count
  FROM `portfolio_demo.ad_daily`
  UNION ALL
  SELECT DATE(date), channel, 'クリック', clicks
  FROM `portfolio_demo.ad_daily`
  UNION ALL
  SELECT DATE(date), channel, 'LINE登録', line_registrations
  FROM `portfolio_demo.line_daily`
  UNION ALL
  SELECT DATE(date), channel, '相談', consultations
  FROM `portfolio_demo.sales_daily`
  UNION ALL
  SELECT DATE(date), channel, '申込', applications
  FROM `portfolio_demo.sales_daily`
  UNION ALL
  SELECT DATE(date), channel, '契約', contracts
  FROM `portfolio_demo.sales_daily`
),
daily_stage AS (
  SELECT
    event_date,
    channel,
    stage,
    SUM(event_count) AS event_count
  FROM source_events
  GROUP BY event_date, channel, stage
),
daily_funnel AS (
  SELECT
    event_date,
    channel,
    SUM(IF(stage = '表示', event_count, 0)) AS impressions,
    SUM(IF(stage = 'クリック', event_count, 0)) AS clicks,
    SUM(IF(stage = 'LINE登録', event_count, 0)) AS line_registrations,
    SUM(IF(stage = '相談', event_count, 0)) AS consultations,
    SUM(IF(stage = '申込', event_count, 0)) AS applications,
    SUM(IF(stage = '契約', event_count, 0)) AS contracts
  FROM daily_stage
  GROUP BY event_date, channel
),
ad_cost AS (
  SELECT
    DATE(date) AS event_date,
    channel,
    SUM(ad_spend) AS ad_spend
  FROM `portfolio_demo.ad_daily`
  GROUP BY event_date, channel
),
joined AS (
  SELECT
    funnel.*,
    COALESCE(cost.ad_spend, 0) AS ad_spend
  FROM daily_funnel AS funnel
  LEFT JOIN ad_cost AS cost
    USING (event_date, channel)
)
SELECT
  *,
  SAFE_DIVIDE(clicks, impressions) AS click_rate,
  SAFE_DIVIDE(line_registrations, clicks) AS registration_cvr,
  SAFE_DIVIDE(consultations, line_registrations) AS consultation_cvr,
  SAFE_DIVIDE(contracts, line_registrations) AS contract_cvr,
  SAFE_DIVIDE(ad_spend, line_registrations) AS cost_per_registration,
  SAFE_DIVIDE(ad_spend, contracts) AS cost_per_contract,
  SUM(contracts) OVER (
    PARTITION BY channel
    ORDER BY event_date
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS contracts_7day,
  LAG(contracts) OVER (
    PARTITION BY channel
    ORDER BY event_date
  ) AS previous_day_contracts
FROM joined;

