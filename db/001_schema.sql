\set ON_ERROR_STOP on
-- Fresh databases only. Existing Olist tables are retained, never truncated or replaced.
BEGIN;
CREATE TABLE IF NOT EXISTS public.customers (
    customer_id TEXT PRIMARY KEY, customer_unique_id TEXT,
    customer_zip_code_prefix TEXT, customer_city TEXT, customer_state TEXT
);
CREATE TABLE IF NOT EXISTS public.geolocation (
    geolocation_zip_code_prefix TEXT, geolocation_lat DOUBLE PRECISION,
    geolocation_lng DOUBLE PRECISION, geolocation_city TEXT, geolocation_state TEXT
);
CREATE TABLE IF NOT EXISTS public.orders (
    order_id TEXT PRIMARY KEY, customer_id TEXT, order_status TEXT,
    order_purchase_timestamp TIMESTAMP, order_approved_at TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP, order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP
);
CREATE TABLE IF NOT EXISTS public.order_items (
    order_id TEXT, order_item_id INTEGER, product_id TEXT, seller_id TEXT,
    shipping_limit_date TIMESTAMP, price NUMERIC(12,2), freight_value NUMERIC(12,2),
    PRIMARY KEY (order_id, order_item_id)
);
CREATE TABLE IF NOT EXISTS public.order_payments (
    order_id TEXT, payment_sequential INTEGER, payment_type TEXT,
    payment_installments INTEGER, payment_value NUMERIC(12,2)
);
CREATE TABLE IF NOT EXISTS public.order_reviews (
    review_id TEXT, order_id TEXT, review_score INTEGER, review_comment_title TEXT,
    review_comment_message TEXT, review_creation_date TIMESTAMP, review_answer_timestamp TIMESTAMP
);
CREATE TABLE IF NOT EXISTS public.products (
    product_id TEXT PRIMARY KEY, product_category_name TEXT, product_name_lenght INTEGER,
    product_description_lenght INTEGER, product_photos_qty INTEGER, product_weight_g INTEGER,
    product_length_cm INTEGER, product_height_cm INTEGER, product_width_cm INTEGER
);
CREATE TABLE IF NOT EXISTS public.sellers (
    seller_id TEXT PRIMARY KEY, seller_zip_code_prefix TEXT, seller_city TEXT, seller_state TEXT
);
CREATE TABLE IF NOT EXISTS public.product_category_name_translation (
    product_category_name TEXT PRIMARY KEY, product_category_name_english TEXT
);
COMMIT;
