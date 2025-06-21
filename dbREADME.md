GRANT ALL PRIVILEGES ON project1.* 
  TO 'vina_user'@'%' IDENTIFIED BY 'Aa7758258123';

#连接数据库
mysql -u vina_user -p -h 127.0.0.1 project1
Aa7758258123

CREATE TABLE user_uploads (
  id CHAR(36)                NOT NULL PRIMARY KEY DEFAULT (UUID()),
  user_id CHAR(36)           NOT NULL,
  filename VARCHAR(255)      NOT NULL,
  file_path VARCHAR(1024)    NOT NULL,
  uploaded_at TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) 
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;
