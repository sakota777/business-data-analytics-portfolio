-- BigQuery Standard SQL
-- 合成CSVを portfolio_demo.operation_log / hourly_sales / current_shift として
-- 読み込んだ想定で、店舗・曜日・時間帯別の推奨人員マートを作成する。

CREATE OR REPLACE TABLE `portfolio_demo.shift_staffing_mart` AS
WITH task_name_map AS (
  SELECT 'レジ' AS raw_task_name, 'レジ' AS standard_task UNION ALL
  SELECT '会計', 'レジ' UNION ALL
  SELECT 'キャッシャー', 'レジ' UNION ALL
  SELECT 'POS対応', 'レジ' UNION ALL
  SELECT '品出し', '品出し' UNION ALL
  SELECT '商品補充', '品出し' UNION ALL
  SELECT '棚補充', '品出し' UNION ALL
  SELECT '補充作業', '品出し' UNION ALL
  SELECT '惣菜', '惣菜' UNION ALL
  SELECT 'デリカ', '惣菜' UNION ALL
  SELECT '惣菜調理', '惣菜' UNION ALL
  SELECT '弁当製造', '惣菜' UNION ALL
  SELECT '清掃', '清掃' UNION ALL
  SELECT '店内清掃', '清掃' UNION ALL
  SELECT 'クリンリネス', '清掃' UNION ALL
  SELECT '発注', '発注・在庫' UNION ALL
  SELECT '在庫確認', '発注・在庫' UNION ALL
  SELECT '棚卸', '発注・在庫' UNION ALL
  SELECT '発注在庫', '発注・在庫'
),
normalized_operations AS (
  SELECT
    operation.store,
    COALESCE(mapping.standard_task, 'その他') AS standard_task,
    operation.minutes
  FROM `portfolio_demo.operation_log` AS operation
  LEFT JOIN task_name_map AS mapping
    USING (raw_task_name)
),
operation_summary AS (
  SELECT
    store,
    standard_task,
    APPROX_QUANTILES(minutes, 100)[OFFSET(50)] AS median_minutes,
    COUNT(*) AS measurement_count
  FROM normalized_operations
  GROUP BY store, standard_task
),
daily_demand AS (
  SELECT
    store,
    DATE(date) AS sales_date,
    weekday,
    hour,
    SUM(visitors) AS visitors,
    SUM(sales_yen) AS sales_yen
  FROM `portfolio_demo.hourly_sales`
  GROUP BY store, sales_date, weekday, hour
),
demand_forecast AS (
  SELECT
    store,
    sales_date,
    weekday,
    hour,
    AVG(visitors) OVER (
      PARTITION BY store, weekday, hour
      ORDER BY sales_date
      ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
    ) AS predicted_visitors,
    AVG(sales_yen) OVER (
      PARTITION BY store, weekday, hour
      ORDER BY sales_date
      ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
    ) AS predicted_sales_yen
  FROM daily_demand
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY store, weekday, hour
    ORDER BY sales_date DESC
  ) = 1
),
current_staffing AS (
  SELECT
    store,
    EXTRACT(DAYOFWEEK FROM DATE(date)) - 1 AS weekday,
    hour,
    ROUND(AVG(current_staff), 1) AS current_staff
  FROM `portfolio_demo.current_shift`
  GROUP BY store, weekday, hour
),
fixed_workload AS (
  SELECT
    store,
    SUM(IF(standard_task IN ('清掃', '発注・在庫'), median_minutes, 0)) AS fixed_minutes_per_day
  FROM operation_summary
  GROUP BY store
)
SELECT
  forecast.store,
  forecast.weekday,
  forecast.hour,
  ROUND(forecast.predicted_visitors, 1) AS predicted_visitors,
  ROUND(forecast.predicted_sales_yen) AS predicted_sales_yen,
  staffing.current_staff,
  CEIL(
    (
      forecast.predicted_visitors * 2.7
      + IF(forecast.hour IN (8, 9, 20, 21), workload.fixed_minutes_per_day / 4, 48)
    ) / 50
  ) AS required_staff,
  CEIL(
    (
      forecast.predicted_visitors * 2.7
      + IF(forecast.hour IN (8, 9, 20, 21), workload.fixed_minutes_per_day / 4, 48)
    ) / 50
  ) - staffing.current_staff AS staff_gap
FROM demand_forecast AS forecast
LEFT JOIN current_staffing AS staffing
  USING (store, weekday, hour)
LEFT JOIN fixed_workload AS workload
  USING (store);

