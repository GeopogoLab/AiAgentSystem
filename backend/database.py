"""SQLite 数据库操作"""
import sqlite3
import json
from typing import Optional, Dict, Any
from datetime import datetime
from .config import config
from .models import OrderState
from .time_utils import parse_timestamp


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
        with self.get_connection() as conn:
            cursor = conn.cursor()
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

    def save_order(self, session_id: str, order_state: OrderState) -> int:
        """
        保存订单到数据库

        Args:
            session_id: 会话 ID
            order_state: 订单状态对象

        Returns:
            订单 ID
        """
        missing_fields = [
            field for field in ("drink_name", "size", "sugar", "ice")
            if not getattr(order_state, field)
        ]
        if missing_fields:
            raise ValueError(f"订单信息不完整，缺少字段：{', '.join(missing_fields)}")

        toppings_json = json.dumps(order_state.toppings or [], ensure_ascii=False)

        with self.get_connection() as conn:
            cursor = conn.cursor()
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

            return cursor.lastrowid

    def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取订单

        Args:
            order_id: 订单 ID

        Returns:
            订单信息字典，不存在则返回 None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            row = cursor.fetchone()

        if row:
            return self._serialize_order(row)

        return None

    def get_orders_by_session(self, session_id: str) -> list:
        """
        获取某个会话的所有订单

        Args:
            session_id: 会话 ID

        Returns:
            订单列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders WHERE session_id = ? ORDER BY created_at DESC",
                (session_id,)
            )
            rows = cursor.fetchall()

        return [self._serialize_order(row) for row in rows]

    def get_all_orders(self, limit: int = 100) -> list:
        """
        获取所有订单

        Args:
            limit: 返回数量限制

        Returns:
            订单列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()

        return [self._serialize_order(row) for row in rows]

    def get_recent_orders(self, limit: int = 50) -> list:
        """
        获取最近的订单列表

        Args:
            limit: 返回数量

        Returns:
            订单列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()

        return [self._serialize_order(row) for row in rows]

    def _serialize_order(self, row: sqlite3.Row) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        order = dict(row)
        order['toppings'] = json.loads(order['toppings']) if order['toppings'] else []
        created_at = order.get('created_at')
        if created_at:
            dt = parse_timestamp(created_at)
            order['created_at'] = dt.strftime('%Y-%m-%d %H:%M:%S')
            order['created_at_iso'] = dt.isoformat()
        return order


# 全局数据库实例
db = Database()
