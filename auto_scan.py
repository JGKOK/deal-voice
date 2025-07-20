import os
import hashlib
import time
import requests
import pymysql
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '112233',
    'database': 'voice_processing',
    'charset': 'utf8mb4'
}

# API配置
API_URL = 'http://localhost:5000/recognize'


class FileProcessor:
    def __init__(self):
        self.db_conn = pymysql.connect(**DB_CONFIG)

    def __del__(self):
        if hasattr(self, 'db_conn') and self.db_conn:
            self.db_conn.close()

    def calculate_file_hash(self, file_path):
        """计算文件哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def file_exists_in_db(self, file_path, file_hash):
        """检查文件是否已存在于数据库中"""
        with self.db_conn.cursor() as cursor:
            sql = """
            SELECT id FROM audio_files 
            WHERE file_path = %s OR file_hash = %s
            """
            cursor.execute(sql, (file_path, file_hash))
            return cursor.fetchone() is not None

    def insert_file_record(self, file_path, file_hash):
        """插入新的文件记录"""
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        with self.db_conn.cursor() as cursor:
            sql = """
            INSERT INTO audio_files 
            (file_path, file_name, file_size, file_hash, status)
            VALUES (%s, %s, %s, %s, 'pending')
            """
            cursor.execute(sql, (file_path, file_name, file_size, file_hash))
            file_id = cursor.lastrowid

            # 插入日志
            log_sql = """
            INSERT INTO processing_logs 
            (audio_file_id, log_level, message)
            VALUES (%s, 'info', 'File discovered and recorded')
            """
            cursor.execute(log_sql, (file_id,))

            self.db_conn.commit()
            return file_id

    def update_file_status(self, file_id, status, message=None):
        """更新文件处理状态"""
        with self.db_conn.cursor() as cursor:
            # 更新状态
            sql = """
            UPDATE audio_files 
            SET status = %s 
            WHERE id = %s
            """
            cursor.execute(sql, (status, file_id))

            # 记录日志
            if message:
                log_level = 'error' if status == 'failed' else 'info'
                log_sql = """
                INSERT INTO processing_logs 
                (audio_file_id, log_level, message)
                VALUES (%s, %s, %s)
                """
                cursor.execute(log_sql, (file_id, log_level, message))

            self.db_conn.commit()

    def save_voice_results(self, file_id, results):
        """保存语音解析结果"""
        with self.db_conn.cursor() as cursor:
            # 先删除旧的结果(如果有)
            cursor.execute("DELETE FROM voice_results WHERE audio_file_id = %s", (file_id,))

            # 插入新结果
            sql = """
            INSERT INTO voice_results 
            (audio_file_id, speaker_id, text_content, start_time, end_time)
            VALUES (%s, %s, %s, %s, %s)
            """
            for result in results:
                cursor.execute(sql, (
                    file_id,
                    result['speaker'],
                    result['text'],
                    result['start'],
                    result['end']
                ))

            # 记录日志
            log_sql = """
            INSERT INTO processing_logs 
            (audio_file_id, log_level, message)
            VALUES (%s, 'info', 'Successfully processed voice results')
            """
            cursor.execute(log_sql, (file_id,))

            self.db_conn.commit()

    def process_file(self, file_path):
        """处理单个文件"""
        try:
            # 计算文件哈希
            file_hash = self.calculate_file_hash(file_path)

            # 检查是否已处理
            if self.file_exists_in_db(file_path, file_hash):
                print(f"File already processed: {file_path}")
                return

            # 插入数据库记录
            file_id = self.insert_file_record(file_path, file_hash)
            self.update_file_status(file_id, 'processing', 'Started processing')

            # 调用API处理
            response = requests.post(API_URL, json={'audio_path': file_path})

            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    # 保存结果
                    self.save_voice_results(file_id, data['data'])
                    self.update_file_status(file_id, 'completed', 'Processing completed successfully')
                    print(f"Successfully processed: {file_path}")
                else:
                    error_msg = data.get('message', 'Unknown API error')
                    self.update_file_status(file_id, 'failed', f"API error: {error_msg}")
                    print(f"API error processing {file_path}: {error_msg}")
            else:
                error_msg = response.text
                self.update_file_status(file_id, 'failed', f"API request failed: {error_msg}")
                print(f"Failed to process {file_path}: {error_msg}")

        except Exception as e:
            if 'file_id' in locals():
                self.update_file_status(file_id, 'failed', f"Processing error: {str(e)}")
            print(f"Error processing {file_path}: {str(e)}")


class NewFileHandler(FileSystemEventHandler):
    def __init__(self, processor):
        self.processor = processor

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.wav', '.mp3', '.ogg', '.flac')):
            print(f"New audio file detected: {event.src_path}")
            self.processor.process_file(event.src_path)


def scan_existing_files(directory, processor):
    """扫描目录中已存在的文件"""
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.wav', '.mp3', '.ogg', '.flac')):
                file_path = os.path.join(root, file)
                print(f"Processing existing file: {file_path}")
                processor.process_file(file_path)


def main():
    # 要监控的目录
    WATCH_DIRECTORY = "/home/ysz/FunASR/tests/demo/input/"

    # 初始化处理器
    processor = FileProcessor()

    # 先处理已存在的文件
    print("Scanning existing files...")
    scan_existing_files(WATCH_DIRECTORY, processor)

    # 设置文件系统监控
    print("Setting up filesystem watcher...")
    event_handler = NewFileHandler(processor)
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIRECTORY, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()