CREATE DATABASE IF NOT EXISTS xiaxia_factory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE xiaxia_factory;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(200) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 超级管理员账户 (密码: admin123456)
INSERT INTO users (username, email, password_hash, created_at)
VALUES ('admin', 'admin@xiaxia.factory', '$2b$12$cDbtbODl7aAN9jHNjlchkOGowo8ccvq8sPb2/Lug1wvLh3ap1doZK', NOW())
ON DUPLICATE KEY UPDATE username=username;
