\set ON_ERROR_STOP on
-- Run as the data owner (saianish), never as either API login.
BEGIN;
CREATE SCHEMA IF NOT EXISTS analytics;
REVOKE ALL ON SCHEMA analytics FROM PUBLIC;
CREATE OR REPLACE VIEW analytics.orders WITH (security_barrier=true) AS
SELECT order_id, order_status, order_purchase_timestamp FROM public.orders;
CREATE OR REPLACE VIEW analytics.order_items WITH (security_barrier=true) AS
SELECT order_id, order_item_id, product_id, seller_id, price, freight_value FROM public.order_items;
CREATE OR REPLACE VIEW analytics.products WITH (security_barrier=true) AS
SELECT product_id, product_category_name, product_weight_g FROM public.products;
CREATE OR REPLACE VIEW analytics.sellers WITH (security_barrier=true) AS
SELECT seller_id, seller_state FROM public.sellers;
CREATE OR REPLACE VIEW analytics.reviews WITH (security_barrier=true) AS
SELECT order_id, review_score FROM public.order_reviews;
REVOKE ALL ON ALL TABLES IN SCHEMA analytics FROM PUBLIC;
COMMENT ON VIEW analytics.order_items IS 'Item grain. Revenue uses price on delivered orders; excludes freight.';
COMMENT ON VIEW analytics.reviews IS 'Review-record grain; multiple records per order are possible. No review free text.';
COMMIT;
