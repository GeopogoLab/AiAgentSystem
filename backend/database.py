"""SQLite 数据库操作"""
import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any
from .config import config
from .models import OrderState


class Database:
    """数据库管理类"""

    def __init__(self, db_path: str = None):
        """初始化数据库连接"""
        self.db_path = db_path or config.DATABASE_PATH
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 返回字典形式的行
        return conn

    def init_db(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 创建订单表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                drink_name TEXT NOT NULL,
                size TEXT,
                sugar TEXT,
                ice TEXT,
                toppings TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def save_order(self, session_id: str, order_state: OrderState) -> int:
        """
        保存订单到数据库

        Args:
            session_id: 会话 ID
            order_state: 订单状态对象

        Returns:
            订单 ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 将 toppings 列表转为 JSON 字符串
        toppings_json = json.dumps(order_state.toppings, ensure_ascii=False)

        cursor.execute("""
            INSERT INTO orders (session_id, drink_name, size, sugar, ice, toppings, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            order_state.drink_name,
            order_state.size,
            order_state.sugar,
            order_state.ice,
            toppings_json,
            order_state.notes
        ))

        order_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return order_id

    def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取订单

        Args:
            order_id: 订单 ID

        Returns:
            订单信息字典，不存在则返回 None
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            order = dict(row)
            # 将 toppings JSON 字符串转回列表
            order['toppings'] = json.loads(order['toppings']) if order['toppings'] else []
            return order

        return None

    def get_orders_by_session(self, session_id: str) -> list:
        """
        获取某个会话的所有订单

        Args:
            session_id: 会话 ID

        Returns:
            订单列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM orders WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        orders = []
        for row in rows:
            order = dict(row)
            order['toppings'] = json.loads(order['toppings']) if order['toppings'] else []
            orders.append(order)

        return orders

    def get_all_orders(self, limit: int = 100) -> list:
        """
        获取所有订单

        Args:
            limit: 返回数量限制

        Returns:
            订单列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()

        orders = []
        for row in rows:
            order = dict(row)
            order['toppings'] = json.loads(order['toppings']) if order['toppings'] else []
            orders.append(order)

        return orders


# 全局数据库实例
db = Database()
