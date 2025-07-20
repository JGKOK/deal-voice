# 文件名：deal_voice.py

## 技术依赖：
### 1、基于funASR 1.2.6版本
### 2、ubuntu 22.04 内核版本 5.15.0-143-generic
### 3、NVIDIA GeForce RTX 3060显卡

## 集成模型：
### 1、VAD模型 iic/speech_fsmn_vad_zh-cn-16k-common-pytorch
### 2、ASR模型iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch 
### 3、标点模型iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch
### 4、说话人验证模型iic/speech_campplus_sv_zh-cn_16k-common

## 实现功能
### 解析指定语音文件，分离语音文件中对话角色，完善时间戳及对话内容，构建对话双方完整对话信息

# 数据库容器部署

## 下载
### docker pull mysql:8.0

## 运行
### docker run --name mysql-container -e MYSQL_ROOT_PASSWORD=112233 -p 3306:3306 -d mysql:8.0

### mysql账号： root 密码：112233

## 数据库脚本
```shell
-- 创建数据库
CREATE DATABASE IF NOT EXISTS voice_processing;
USE voice_processing;

-- 语音文件表：记录扫描到的语音文件
CREATE TABLE IF NOT EXISTS audio_files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_path VARCHAR(512) NOT NULL COMMENT '语音文件绝对路径',
    file_name VARCHAR(255) NOT NULL COMMENT '语音文件名',
    file_size BIGINT COMMENT '文件大小(字节)',
    file_hash VARCHAR(64) COMMENT '文件哈希值(用于去重)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
    status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending' COMMENT '处理状态',
    UNIQUE KEY (file_path),
    UNIQUE KEY (file_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='语音文件记录表';

-- 语音解析结果表：记录API解析结果
CREATE TABLE IF NOT EXISTS voice_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    audio_file_id INT NOT NULL COMMENT '关联的语音文件ID',
    speaker_id VARCHAR(64) NOT NULL COMMENT '说话人ID',
    speaker_tag VARCHAR(64) COMMENT '说话人标签(可人工标记)',
    text_content TEXT NOT NULL COMMENT '解析出的文本内容',
    start_time FLOAT NOT NULL COMMENT '开始时间(秒)',
    end_time FLOAT NOT NULL COMMENT '结束时间(秒)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    FOREIGN KEY (audio_file_id) REFERENCES audio_files(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='语音解析结果表';

-- 处理日志表：记录处理过程
CREATE TABLE IF NOT EXISTS processing_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    audio_file_id INT COMMENT '关联的语音文件ID',
    log_level ENUM('info', 'warning', 'error') NOT NULL COMMENT '日志级别',
    message TEXT NOT NULL COMMENT '日志内容',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    FOREIGN KEY (audio_file_id) REFERENCES audio_files(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='处理日志表';
  
-- 新增retry_count字段用于记录重试次数
ALTER TABLE audio_files ADD COLUMN retry_count INT DEFAULT 0 COMMENT '重试次数';

-- 新增last_processed_at字段记录最后处理时间
ALTER TABLE audio_files ADD COLUMN last_processed_at TIMESTAMP NULL COMMENT '最后处理时间';
```

# 文件名：deal_voice_api.py
## 实现功能
### 提供api接口，解析制定绝对路径下的语音文件，保存解析结果和文件名进数据库

# 文件名：auto_scan.py
## 实现功能
### 扫描指定目录下的语音文件并且调用deal_voice_api.py的api接口进行语音文件解析


# 文件名： 


