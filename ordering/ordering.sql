DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS order_items;

-- splitting in to 2 tables for convenience 
CREATE TABLE orders (
    IDorder INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL,
    Tcost REAL NOT NULL, date_of_order DATETIME NOT NULL,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE order_items (
    IDitem INTEGER PRIMARY KEY AUTOINCREMENT, IDorder INTEGER NOT NULL,
    product_name TEXT NOT NULL, quantity INTEGER NOT NULL,
    FOREIGN KEY (IDorder) REFERENCES orders(IDorder)
);
