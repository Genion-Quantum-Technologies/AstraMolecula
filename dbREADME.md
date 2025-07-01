GRANT ALL PRIVILEGES ON project1.*  TO 'vina_user'@'%' IDENTIFIED BY 'Aa7758258123';

#连接数据库
mysql -u vina_user -p -h 127.0.0.1 project1
Aa7758258123

CREATE TABLE `users` (
  `id` CHAR(36) NOT NULL,
  `username` VARCHAR(255) NOT NULL UNIQUE,
  `password_hash` VARCHAR(255) NOT NULL,
  `phone` VARCHAR(20) DEFAULT NULL,
  `email` VARCHAR(255) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

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

# Task table for tracking generate/docking jobs
CREATE TABLE tasks (
  id CHAR(36)            NOT NULL PRIMARY KEY,
  user_id CHAR(36)       NOT NULL,
  task_type VARCHAR(20)  NOT NULL,
  job_dir VARCHAR(1024)  NOT NULL,
  status VARCHAR(20)     NOT NULL DEFAULT 'pending',
  created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TIMESTAMP  NULL DEFAULT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;