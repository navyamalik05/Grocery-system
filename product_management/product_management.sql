DROP TABLE IF EXISTS products_info;

CREATE TABLE products_info(
    name TEXT PRIMARY KEY, price REAL NOT NULL, category TEXT NOT NULL);