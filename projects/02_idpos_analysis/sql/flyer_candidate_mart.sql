-- BigQuery Standard SQL
-- POS明細と商品マスタを結合し、ABC、反復購買、併買リフトを使って
-- チラシ掲載候補を順位付けする。

CREATE OR REPLACE TABLE `portfolio_demo.flyer_candidate_mart` AS
WITH enriched_transactions AS (
  SELECT
    transaction.transaction_id,
    transaction.customer_id,
    transaction.store,
    DATE(transaction.date) AS purchase_date,
    transaction.product_id,
    product.product_name,
    product.category,
    transaction.quantity,
    transaction.quantity * transaction.unit_price AS sales
  FROM `portfolio_demo.transactions` AS transaction
  INNER JOIN `portfolio_demo.products` AS product
    USING (product_id)
),
product_metrics AS (
  SELECT
    product_id,
    ANY_VALUE(product_name) AS product_name,
    ANY_VALUE(category) AS category,
    SUM(sales) AS sales,
    COUNT(DISTINCT customer_id) AS customers,
    COUNT(DISTINCT transaction_id) AS transactions,
    SAFE_DIVIDE(
      COUNT(DISTINCT IF(customer_purchase_count >= 2, customer_id, NULL)),
      COUNT(DISTINCT customer_id)
    ) AS repeat_rate
  FROM (
    SELECT
      *,
      COUNT(DISTINCT transaction_id) OVER (
        PARTITION BY product_id, customer_id
      ) AS customer_purchase_count
    FROM enriched_transactions
  )
  GROUP BY product_id
),
abc_ranked AS (
  SELECT
    *,
    SAFE_DIVIDE(
      SUM(sales) OVER (ORDER BY sales DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
      SUM(sales) OVER ()
    ) AS cumulative_sales_share
  FROM product_metrics
),
basket_pairs AS (
  SELECT
    left_item.product_id AS product_a,
    right_item.product_id AS product_b,
    COUNT(DISTINCT left_item.transaction_id) AS pair_count
  FROM enriched_transactions AS left_item
  INNER JOIN enriched_transactions AS right_item
    ON left_item.transaction_id = right_item.transaction_id
   AND left_item.product_id < right_item.product_id
  GROUP BY product_a, product_b
  HAVING pair_count >= 15
),
product_transaction_counts AS (
  SELECT
    product_id,
    COUNT(DISTINCT transaction_id) AS item_transactions
  FROM enriched_transactions
  GROUP BY product_id
),
pair_lift AS (
  SELECT
    pair.product_a,
    pair.product_b,
    pair.pair_count,
    SAFE_DIVIDE(pair.pair_count * total.total_baskets, count_a.item_transactions * count_b.item_transactions) AS lift
  FROM basket_pairs AS pair
  INNER JOIN product_transaction_counts AS count_a
    ON pair.product_a = count_a.product_id
  INNER JOIN product_transaction_counts AS count_b
    ON pair.product_b = count_b.product_id
  CROSS JOIN (
    SELECT COUNT(DISTINCT transaction_id) AS total_baskets
    FROM enriched_transactions
  ) AS total
),
product_lift AS (
  SELECT product_id, MAX(lift) AS max_pair_lift
  FROM (
    SELECT product_a AS product_id, lift FROM pair_lift
    UNION ALL
    SELECT product_b AS product_id, lift FROM pair_lift
  )
  GROUP BY product_id
),
candidate_base AS (
  SELECT
    product.*,
    CASE
      WHEN cumulative_sales_share <= 0.70 THEN 'A'
      WHEN cumulative_sales_share <= 0.90 THEN 'B'
      ELSE 'C'
    END AS abc_rank,
    COALESCE(product_lift.max_pair_lift, 1) AS max_pair_lift,
    PERCENT_RANK() OVER (ORDER BY customers) AS customer_reach_index,
    PERCENT_RANK() OVER (ORDER BY repeat_rate) AS repeat_index,
    PERCENT_RANK() OVER (ORDER BY COALESCE(product_lift.max_pair_lift, 1)) AS pair_lift_index
  FROM abc_ranked AS product
  LEFT JOIN product_lift
    USING (product_id)
)
SELECT
  *,
  ROUND(
    0.35 * customer_reach_index
    + 0.25 * repeat_index
    + 0.25 * pair_lift_index
    + 0.15 * (1 - customer_reach_index),
    4
  ) AS flyer_score,
  ROW_NUMBER() OVER (
    ORDER BY
      0.35 * customer_reach_index
      + 0.25 * repeat_index
      + 0.25 * pair_lift_index
      + 0.15 * (1 - customer_reach_index) DESC
  ) AS candidate_rank
FROM candidate_base
WHERE product_id IN (
  SELECT DISTINCT product_id
  FROM enriched_transactions
  WHERE purchase_date >= DATE_SUB((SELECT MAX(purchase_date) FROM enriched_transactions), INTERVAL 90 DAY)
);

