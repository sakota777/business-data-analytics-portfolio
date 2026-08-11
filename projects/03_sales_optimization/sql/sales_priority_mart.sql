-- BigQuery Standard SQL
-- Salesforce相当の顧客・活動・商談テーブルを結合し、営業優先リストを作成する。

CREATE OR REPLACE TABLE `portfolio_demo.sales_priority_mart` AS
WITH activity_ranked AS (
  SELECT
    customer_id,
    DATE(activity_date) AS activity_date,
    activity_type,
    COUNT(*) OVER (PARTITION BY customer_id) AS contact_count,
    ROW_NUMBER() OVER (
      PARTITION BY customer_id
      ORDER BY DATE(activity_date) DESC, activity_id DESC
    ) AS activity_recency_rank
  FROM `portfolio_demo.activities`
),
latest_activity AS (
  SELECT
    customer_id,
    activity_date AS latest_activity_date,
    activity_type AS latest_activity_type,
    contact_count
  FROM activity_ranked
  QUALIFY activity_recency_rank = 1
),
attribute_rates AS (
  SELECT
    account.industry,
    account.company_size,
    COUNT(DISTINCT account.customer_id) AS customers,
    AVG(opportunity.contracted) AS historical_contract_rate
  FROM `portfolio_demo.accounts` AS account
  INNER JOIN `portfolio_demo.opportunities` AS opportunity
    USING (customer_id)
  GROUP BY account.industry, account.company_size
),
customer_base AS (
  SELECT
    account.customer_id,
    account.industry,
    account.company_size,
    account.lead_source,
    account.inquiry_type,
    opportunity.stage,
    opportunity.contracted,
    COALESCE(activity.contact_count, 0) AS contact_count,
    activity.latest_activity_date,
    activity.latest_activity_type,
    opportunity.days_since_contact,
    rate.historical_contract_rate
  FROM `portfolio_demo.accounts` AS account
  LEFT JOIN `portfolio_demo.opportunities` AS opportunity
    USING (customer_id)
  LEFT JOIN latest_activity AS activity
    USING (customer_id)
  LEFT JOIN attribute_rates AS rate
    USING (industry, company_size)
),
scored AS (
  SELECT
    *,
    ROUND(
      100 * LEAST(
        1,
        COALESCE(historical_contract_rate, 0)
        + IF(lead_source = '紹介', 0.08, 0)
        + IF(inquiry_type = '見積依頼', 0.10, IF(inquiry_type = 'サンプル依頼', 0.05, 0))
        + LEAST(contact_count, 5) * 0.02
        - LEAST(days_since_contact, 90) * 0.0008
      ),
      1
    ) AS prospect_score
  FROM customer_base
)
SELECT
  *,
  CASE
    WHEN NTILE(3) OVER (ORDER BY prospect_score) = 3 THEN '高'
    WHEN NTILE(3) OVER (ORDER BY prospect_score) = 2 THEN '中'
    ELSE '低'
  END AS priority,
  CASE
    WHEN prospect_score >= 25 AND days_since_contact >= 14 THEN '優先フォロー'
    WHEN prospect_score >= 25 THEN '商談状況を確認'
    WHEN contact_count = 0 THEN '初回接触'
    ELSE '定期情報提供'
  END AS recommended_action
FROM scored
WHERE contracted = 0;

