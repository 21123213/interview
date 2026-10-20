-- RAG系统重构 - 数据库迁移脚本 (MySQL版本)
-- 版本: 001
-- 日期: 2024-01
-- 说明: 添加新表以支持文档元素、切片、会话管理

-- ========================================
-- 1. 扩展 file_metadata 表
-- ========================================

-- 检查并添加新字段到 file_metadata
-- MySQL不支持 IF NOT EXISTS，使用存储过程或手动检查

-- 方案1: 直接添加（如果字段已存在会报错，忽略即可）
ALTER TABLE file_metadata 
ADD COLUMN total_elements INT DEFAULT 0 COMMENT '文档元素总数';

ALTER TABLE file_metadata 
ADD COLUMN total_chunks INT DEFAULT 0 COMMENT '切片总数';

ALTER TABLE file_metadata 
ADD COLUMN embedded_chunks INT DEFAULT 0 COMMENT '已向量化的切片数';

ALTER TABLE file_metadata 
ADD COLUMN elements_stats JSON COMMENT '元素类型统计';

ALTER TABLE file_metadata 
ADD COLUMN started_processing_time TIMESTAMP NULL COMMENT '开始处理时间';

ALTER TABLE file_metadata 
ADD COLUMN completed_processing_time TIMESTAMP NULL COMMENT '完成处理时间';

-- 如果需要修改status字段支持更多状态
-- ALTER TABLE file_metadata MODIFY status VARCHAR(20) DEFAULT 'pending';

-- ========================================
-- 2. 创建 document_elements 表
-- ========================================

CREATE TABLE IF NOT EXISTS document_elements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id BIGINT NOT NULL COMMENT '文件ID',
    element_index INT NOT NULL COMMENT '元素序号',
    element_type VARCHAR(50) NOT NULL COMMENT '元素类型(Title,NarrativeText等)',
    text_content TEXT COMMENT '文本内容',
    metadata JSON COMMENT '元数据(页码、坐标等)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_file_id (file_id),
    INDEX idx_element_type (element_type),
    UNIQUE KEY uk_file_element (file_id, element_index),
    
    -- 外键
    FOREIGN KEY (file_id) REFERENCES file_metadata(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档元素表';

-- ========================================
-- 3. 创建 document_chunks 表
-- ========================================

CREATE TABLE IF NOT EXISTS document_chunks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id BIGINT NOT NULL COMMENT '文件ID',
    chunk_index INT NOT NULL COMMENT '切片序号',
    chunk_text LONGTEXT NOT NULL COMMENT '切片内容',
    char_count INT NOT NULL COMMENT '字符数',
    element_count INT NOT NULL COMMENT '包含的元素数量',
    element_ids JSON COMMENT '包含的元素ID列表 [1,2,3]',
    page_numbers JSON COMMENT '涉及的页码 [1,2,3]',
    vector_id VARCHAR(100) COMMENT 'Milvus中的向量ID',
    is_embedded TINYINT(1) DEFAULT 0 COMMENT '是否已向量化 0=否 1=是',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    embedded_at TIMESTAMP NULL DEFAULT NULL COMMENT '向量化时间',
    
    -- 索引
    INDEX idx_file_id (file_id),
    INDEX idx_vector_id (vector_id),
    INDEX idx_is_embedded (is_embedded),
    UNIQUE KEY uk_file_chunk (file_id, chunk_index),
    
    -- 外键
    FOREIGN KEY (file_id) REFERENCES file_metadata(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档切片表';

-- ========================================
-- 4. 创建 chat_sessions 表
-- ========================================

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    title VARCHAR(255) DEFAULT '新会话' COMMENT '会话标题',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 索引
    UNIQUE KEY uk_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_updated_at (updated_at),
    
    -- 外键
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='聊天会话表';

-- ========================================
-- 5. 创建 chat_messages 表
-- ========================================

CREATE TABLE IF NOT EXISTS chat_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    role ENUM('user', 'assistant', 'system') NOT NULL COMMENT '角色',
    content LONGTEXT NOT NULL COMMENT '消息内容',
    sources JSON COMMENT '检索到的来源片段',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_session_id (session_id),
    INDEX idx_created_at (created_at),
    INDEX idx_role (role),
    
    -- 外键
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='聊天消息表';

-- ========================================
-- 6. 创建 processing_tasks 表 (可选)
-- ========================================

CREATE TABLE IF NOT EXISTS processing_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(100) NOT NULL COMMENT 'Celery任务ID',
    file_id BIGINT NOT NULL COMMENT '文件ID',
    task_type VARCHAR(50) NOT NULL COMMENT '任务类型',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '任务状态',
    progress INT DEFAULT 0 COMMENT '进度(0-100)',
    result JSON COMMENT '任务结果',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 索引
    UNIQUE KEY uk_task_id (task_id),
    INDEX idx_file_id (file_id),
    INDEX idx_status (status),
    
    -- 外键
    FOREIGN KEY (file_id) REFERENCES file_metadata(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务状态表';

-- ========================================
-- 迁移完成
-- ========================================

-- 查看新表
SHOW TABLES;

-- 验证表结构
DESCRIBE file_metadata;
DESCRIBE document_elements;
DESCRIBE document_chunks;
DESCRIBE chat_sessions;
DESCRIBE chat_messages;
DESCRIBE processing_tasks;
