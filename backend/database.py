"""SQLite database operations"""
import sqlite3
import json
from typing import Optional, Dict, Any
from datetime import datetime
from .config import config
from .models import OrderState
from .time_utils import parse_timestamp


class Database:
    """Database management class"""

    def __init__(self, db_path: str = None):
        """Initialize database connection"""
        self.db_path = db_path or config.DATABASE_PATH
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn

    def init_db(self):
        """Initialize database tables"""
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
        Save order to database

        Args:
            session_id: Session ID
            order_state: Order state object

        Returns:
            Order ID
        """
        missing_fields = [
            field for field in ("drink_name", "size", "sugar", "ice")
            if not getattr(order_state, field)
        ]
        if missing_fields:
            raise ValueError(f"Order information incomplete, missing fields: {', '.join(missing_fields)}")

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
        Get order by ID

        Args:
            order_id: Order ID

        Returns:
            Order information dictionary, or None if not found
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
        Get all orders for a session

        Args:
            session_id: Session ID

        Returns:
            List of orders
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
        Get all orders

        Args:
            limit: Return limit

        Returns:
            List of orders
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
        Get recent orders list

        Args:
            limit: Return count

        Returns:
            List of orders
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
        """Convert database row to dictionary"""
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
