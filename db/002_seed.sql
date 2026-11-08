\set ON_ERROR_STOP on
-- Opt-in fixture ONLY for a new, separate database named olist_test. Never run on olist.
BEGIN;
DO $$ BEGIN
    IF current_database() <> 'olist_test' THEN
        RAISE EXCEPTION 'Seed requires a separate database named olist_test';
    END IF;
    IF EXISTS (SELECT 1 FROM public.orders) OR EXISTS (SELECT 1 FROM public.order_items)
       OR EXISTS (SELECT 1 FROM public.products) OR EXISTS (SELECT 1 FROM public.order_reviews)
       OR EXISTS (SELECT 1 FROM public.sellers) OR EXISTS (SELECT 1 FROM public.customers) THEN
        RAISE EXCEPTION 'Seed requires empty fixture tables';
    END IF;
END $$;
INSERT INTO public.customers(customer_id,customer_unique_id,customer_state)
VALUES ('c1','u1','SP'),('c2','u2','RJ'),('c3','u3','SP');
INSERT INTO public.orders(order_id,customer_id,order_status,order_purchase_timestamp)
VALUES ('o1','c1','delivered','2018-01-10 10:00:00'),
       ('o2','c2','delivered','2018-02-11 11:00:00'),
       ('o3','c3','canceled','2018-02-12 12:00:00');
INSERT INTO public.products(product_id,product_category_name,product_weight_g)
VALUES ('p1','books',100),('p2','electronics',200),('p3','books',150);
INSERT INTO public.sellers(seller_id,seller_state) VALUES ('s1','SP'),('s2','RJ');
INSERT INTO public.order_items(order_id,order_item_id,product_id,seller_id,price,freight_value)
VALUES ('o1',1,'p1','s1',100.00,10.00),('o1',2,'p2','s2',50.00,5.00),
       ('o2',1,'p1','s1',200.00,20.00),('o2',2,'p3','s1',25.00,3.00),
       ('o3',1,'p2','s2',999.00,99.00);
INSERT INTO public.order_reviews(review_id,order_id,review_score,review_comment_message)
VALUES ('r1','o1',5,'Never expose this review body'),('r2','o2',3,'Private free text'),
       ('r2','o2',4,'Another review record');
-- Ground truth: product revenue p1=300, p2=50, p3=25; monthly revenue Jan=150, Feb=225.
COMMIT;
