DROP TABLE IF EXISTS search_products;

CREATE TABLE search_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT, product_name TEXT NOT NULL,
    price REAL NOT NULL, category TEXT NOT NULL);

