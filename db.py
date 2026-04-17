# -*- coding: utf-8 -*-
# Copyright (c) 2026 Li Rui
# This project is licensed under CC BY-NC 4.0.
# Commercial use is strictly prohibited without prior authorization.
# For commercial licensing, please contact: [lr298977887@gmail.com]
"""
db.py - MoCli 配置数据库管理
================================
职责：
  - 提供线程安全的 SQLite 键值对配置存储
  - 单例模式，全局共享同一实例
  - 使用脚本所在目录存放数据库文件，不依赖工作目录
"""

import os
import logging
import sqlite3
import threading

logger = logging.getLogger(__name__)

# 项目根目录（db.py 所在目录）
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class DBManager:
    """轻量级键值对配置数据库（线程安全单例）"""
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                # 双重检查锁定，防止多线程同时创建
                if cls._instance is None:
                    cls._instance = super(DBManager, cls).__new__(cls)
                    cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        """初始化数据库连接和默认配置"""
        self._db_lock = threading.Lock()
        db_path = os.path.join(_BASE_DIR, 'mocli.db')
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")  # WAL 模式提升并发性能
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            '''CREATE TABLE IF NOT EXISTS settings
               (key TEXT PRIMARY KEY, value TEXT)'''
        )
        # 聊天记录表（持久化所有对话，语音 + 文字统一存储）
        self.cursor.execute(
            '''CREATE TABLE IF NOT EXISTS chat_messages (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   role TEXT NOT NULL,
                   content TEXT NOT NULL,
                   timestamp REAL NOT NULL
               )'''
        )
        self.conn.commit()

        # 默认配置项
        defaults = {
            "base_url": "http://127.0.0.1:1234/v1/chat/completions",
            "model": "qwen/qwen2.5-vl-7b",
            "api_key": "lm-studio",
            "tts_url": "http://localhost:8100/v1/audio/speech",
            "tts_model": "model-base",
            "wakeup_enabled": "true",
            "tts_enabled": "true",
            "wakeup_keyword": "贾维斯",
            "memory_size": "10",
            "offset_x": "0",
            "offset_y": "0",
            # 拼音行（仅带声调版本，sherpa-onnx tokens.txt 中无不带声调的韵母）
            "keyword_lines": "j iǎ w éi s ī @贾维斯",
            # 自定义系统提示词（空则使用内置默认值）
            "custom_system_prompt": "",
        }
        for k, v in defaults.items():
            self._set_default(k, v)

        logger.info("数据库初始化完成: %s", db_path)

    def _set_default(self, key, value):
        """仅当 key 不存在时写入默认值"""
        with self._db_lock:
            self.cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
            if not self.cursor.fetchone():
                self.cursor.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)", (key, value)
                )
                self.conn.commit()

    def get(self, key, default=""):
        """获取配置值（线程安全）"""
        with self._db_lock:
            self.cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = self.cursor.fetchone()
            return row[0] if row else default

    def set(self, key, value):
        """设置配置值（立即持久化，线程安全）"""
        with self._db_lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value))
            )
            self.conn.commit()

    def get_bool(self, key, default=True):
        """获取布尔配置值"""
        val = self.get(key, str(default).lower())
        return val.lower() in ("true", "1", "yes")

    def get_int(self, key, default=10):
        """获取整数配置值"""
        try:
            return int(self.get(key, str(default)))
        except ValueError:
            return default

    # ==========================================
    # 聊天记录持久化
    # ==========================================

    def save_chat_message(self, role: str, content: str) -> None:
        """保存一条聊天消息到数据库（线程安全）"""
        import time
        with self._db_lock:
            self.cursor.execute(
                "INSERT INTO chat_messages (role, content, timestamp) VALUES (?, ?, ?)",
                (role, content, time.time())
            )
            self.conn.commit()

    def get_chat_history(self, limit: int = 200) -> list:
        """获取最近的聊天记录（按时间正序返回）"""
        with self._db_lock:
            self.cursor.execute(
                "SELECT role, content, timestamp FROM chat_messages "
                "ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = self.cursor.fetchall()
        # 翻转为时间正序（旧 → 新）
        return [
            {"role": r[0], "content": r[1], "timestamp": r[2]}
            for r in reversed(rows)
        ]

    def clear_chat_history(self) -> None:
        """清空所有聊天记录（线程安全）"""
        with self._db_lock:
            self.cursor.execute("DELETE FROM chat_messages")
            self.conn.commit()
        logger.info("聊天记录已清空")
