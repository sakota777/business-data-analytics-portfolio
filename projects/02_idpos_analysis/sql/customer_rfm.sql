-- BigQuery Standard SQL
-- ID・POS明細から顧客別RFM指標と五分位スコアを作成する。

CREATE OR REPLACE TABLE `portfolio_demo.customer_rfm` AS
WITH customer_metrics AS (
  SELECT
    customer_id,
    DATE_DIFF(MAX(MAX(DATE(date))) OVER (), MAX(DATE(date)), DAY) AS recency_days,
    COUNT(DISTINCT transaction_id) AS purchase_frequency,
    SUM(quantity * unit_price) AS purchase_amount,
    COUNT(DISTINCT store) AS stores_used
  FROM `portfolio_demo.transactions`
  GROUP BY customer_id
),
scored AS (
  SELECT
    *,
    6 - NTILE(5) OVER (ORDER BY recency_days) AS r_score,
    NTILE(5) OVER (ORDER BY purchase_frequency) AS f_score,
    NTILE(5) OVER (ORDER BY purchase_amount) AS m_score
  FROM customer_metrics
)
SELECT
  *,
  r_score + f_score + m_score AS rfm_score,
  CASE
    WHEN r_score + f_score + m_score >= 12 THEN '優良'
    WHEN r_score + f_score + m_score >= 8 THEN '一般'
    ELSE '休眠・育成'
  END AS customer_segment
FROM scored;
