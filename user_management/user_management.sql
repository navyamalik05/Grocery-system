DROP TABLE IF EXISTS users_info;

CREATE TABLE users_info (
    first_name TEXT NOT NULL, last_name TEXT NOT NULL, username TEXT NOT NULL UNIQUE,
    email_address TEXT NOT NULL UNIQUE, employee INTEGER NOT NULL, password TEXT NOT NULL,
    salt TEXT NOT NULL
);