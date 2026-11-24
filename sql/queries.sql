-- 1. How many orders are in each status?
SELECT status, COUNT(*) AS orders
FROM orders
GROUP BY status
ORDER BY orders DESC;

-- 2. What is total revenue from completed orders (PKR)?
SELECT SUM(oi.quantity * oi.unit_price) AS completed_revenue_pkr
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'Completed';

-- 3. How does completed revenue change month by month?


SELECT DATE_TRUNC('month', o.order_date)::date AS month,
       COUNT(DISTINCT o.order_id) AS orders,
       SUM(oi.quantity * oi.unit_price) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'Completed'
GROUP BY 1
ORDER BY 1;

-- 4. What is the month-over-month revenue growth?

WITH monthly AS (
    SELECT DATE_TRUNC('month', o.order_date)::date AS month,
           SUM(oi.quantity * oi.unit_price) AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'Completed'
    GROUP BY 1
)
SELECT month,
       revenue,
       LAG(revenue) OVER (ORDER BY month) AS previous_month,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
             / LAG(revenue) OVER (ORDER BY month), 1) AS growth_pct
FROM monthly
ORDER BY month;

-- 5. Which genres drive the most revenue?

SELECT p.category,
       SUM(oi.quantity) AS units_sold,
       SUM(oi.quantity * oi.unit_price) AS revenue,
       ROUND(100.0 * SUM(oi.quantity * oi.unit_price)
             / SUM(SUM(oi.quantity * oi.unit_price)) OVER (), 1) AS revenue_share_pct
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status = 'Completed'
GROUP BY p.category
ORDER BY revenue DESC;

-- 6. Which 10 books earn the most revenue?

SELECT RANK() OVER (ORDER BY SUM(oi.quantity * oi.unit_price) DESC) AS rank,
       p.product_name,
       p.category,
       SUM(oi.quantity) AS units_sold,
       SUM(oi.quantity * oi.unit_price) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status = 'Completed'
GROUP BY p.product_id, p.product_name, p.category
ORDER BY rank
LIMIT 10;

-- 7. Which cities bring in the most revenue, and how much per customer?

SELECT c.city,
       COUNT(DISTINCT c.customer_id) AS buying_customers,
       COUNT(DISTINCT o.order_id) AS orders,
       SUM(oi.quantity * oi.unit_price) AS revenue,
       ROUND(SUM(oi.quantity * oi.unit_price)
             / COUNT(DISTINCT c.customer_id), 0) AS revenue_per_customer
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.status = 'Completed'
GROUP BY c.city
ORDER BY revenue DESC;

-- 8. How much revenue comes from repeat buyers vs one-time buyers?

WITH per_customer AS (
    SELECT o.customer_id,
           COUNT(DISTINCT o.order_id) AS orders,
           SUM(oi.quantity * oi.unit_price) AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'Completed'
    GROUP BY o.customer_id
)
SELECT CASE WHEN orders = 1 THEN 'One-time buyer'
            ELSE 'Repeat buyer (2+ orders)' END AS segment,
       COUNT(*) AS customers,
       SUM(revenue) AS revenue,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 1) AS revenue_share_pct
FROM per_customer
GROUP BY 1
ORDER BY customers DESC;

-- 9. Which genres grew most from July to August (back-to-school effect)?

WITH pivot AS (
    SELECT p.category,
           SUM(oi.quantity * oi.unit_price)
               FILTER (WHERE EXTRACT(MONTH FROM o.order_date) = 7) AS july,
           SUM(oi.quantity * oi.unit_price)
               FILTER (WHERE EXTRACT(MONTH FROM o.order_date) = 8) AS august
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    JOIN products p ON p.product_id = oi.product_id
    WHERE o.status = 'Completed'
    GROUP BY p.category
)
SELECT category,
       july,
       august,
       ROUND(100.0 * (august - july) / july, 1) AS change_pct
FROM pivot
ORDER BY change_pct DESC;