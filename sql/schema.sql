-- BookNook Books - schema.sql (PostgreSQL)
-- Plain-SQL equivalent of etl/models.py. Optional: `python -m etl.pipeline --reset`
-- creates the same tables for you.
--   createdb booknook
--   psql -d booknook -f sql/schema.sql

CREATE TABLE customers (
    customer_id  SERIAL PRIMARY KEY,
    first_name   VARCHAR(50)  NOT NULL,
    last_name    VARCHAR(50)  NOT NULL,
    email        VARCHAR(100) NOT NULL UNIQUE,
    phone        VARCHAR(20),
    city         VARCHAR(50)  NOT NULL,
    signup_date  DATE         NOT NULL
);

CREATE TABLE products (
    product_id    SERIAL PRIMARY KEY,
    product_name  VARCHAR(100)  NOT NULL,
    category      VARCHAR(50)   NOT NULL,
    author        VARCHAR(100),
    unit_price    NUMERIC(10,2) NOT NULL,
    CONSTRAINT ck_products_unit_price CHECK (unit_price >= 0)
);

CREATE TABLE orders (
    order_id        SERIAL PRIMARY KEY,
    order_ref       VARCHAR(20) NOT NULL UNIQUE,   -- ID from the source export, e.g. B5001
    customer_id     INTEGER     NOT NULL REFERENCES customers(customer_id),
    order_date      DATE        NOT NULL,
    status          VARCHAR(20) NOT NULL,
    payment_method  VARCHAR(30) NOT NULL,
    CONSTRAINT ck_orders_status CHECK (status IN ('Completed','Cancelled','Pending','Returned'))
);

CREATE TABLE order_items (
    order_item_id  SERIAL PRIMARY KEY,
    order_id       INTEGER       NOT NULL REFERENCES orders(order_id),
    product_id     INTEGER       NOT NULL REFERENCES products(product_id),
    quantity       INTEGER       NOT NULL,
    unit_price     NUMERIC(10,2) NOT NULL,
    CONSTRAINT ck_order_items_quantity   CHECK (quantity > 0),
    CONSTRAINT ck_order_items_unit_price CHECK (unit_price >= 0)
);

CREATE INDEX ix_orders_order_date    ON orders(order_date);
CREATE INDEX ix_orders_customer_id   ON orders(customer_id);
CREATE INDEX ix_order_items_order_id ON order_items(order_id);
CREATE INDEX ix_order_items_product  ON order_items(product_id);
