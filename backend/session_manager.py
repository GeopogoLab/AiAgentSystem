"""会话状态管理"""
from typing import Dict, Optional, List
from .models import SessionState, OrderState, OrderStatus, ConversationMessage
from .config import config


class SessionManager:
    """会话管理器（内存存储）"""

    def __init__(self):
        """初始化会话管理器"""
        self.sessions: Dict[str, SessionState] = {}
        self.progress_histories: Dict[int, List[ConversationMessage]] = {}
        self.progress_session_histories: Dict[str, List[ConversationMessage]] = {}

    def get_session(self, session_id: str) -> SessionState:
        """
        获取会话状态，如果不存在则创建新会话

        Args:
            session_id: 会话 ID

        Returns:
            会话状态对象
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(session_id=session_id)

        return self.sessions[session_id]

    def update_session(self, session_id: str, session_state: SessionState):
        """
        更新会话状态

        Args:
            session_id: 会话 ID
            session_state: 新的会话状态
        """
        self.sessions[session_id] = session_state

    def add_message(self, session_id: str, role: str, content: str, mode: str = "online"):
        """
        添加对话消息到历史记录

        Args:
            session_id: 会话 ID
            role: 角色（user 或 assistant）
            content: 消息内容
        """
        session = self.get_session(session_id)
        session.history.append(ConversationMessage(role=role, content=content, mode=mode))

        # 限制历史记录长度
        if len(session.history) > config.MAX_HISTORY_LENGTH * 2:  # 每轮包含 user + assistant
            session.history = session.history[-config.MAX_HISTORY_LENGTH * 2:]

        self.update_session(session_id, session)

    def update_order_state(self, session_id: str, order_state: OrderState):
        """
        更新订单状态

        Args:
            session_id: 会话 ID
            order_state: 订单状态
        """
        session = self.get_session(session_id)
        session.order_state = order_state
        self.update_session(session_id, session)

    def update_status(self, session_id: str, status: OrderStatus):
        """
        更新会话状态

        Args:
            session_id: 会话 ID
            status: 订单状态
        """
        session = self.get_session(session_id)
        session.status = status
        self.update_session(session_id, session)

    def reset_session(self, session_id: str):
        """
        重置会话（开始新订单）

        Args:
            session_id: 会话 ID
        """
        self.sessions[session_id] = SessionState(session_id=session_id)

    def delete_session(self, session_id: str):
        """
        删除会话

        Args:
            session_id: 会话 ID
        """
        if session_id in self.sessions:
            del self.sessions[session_id]

    def get_all_sessions(self) -> Dict[str, SessionState]:
        """
        获取所有会话

        Returns:
            所有会话的字典
        """
        return self.sessions

    # --- 制作进度助手 ---

    def add_progress_message(self, order_id: int, role: str, content: str, mode: str = "online"):
        """记录某个订单的进度助手对话"""
        history = self.progress_histories.setdefault(order_id, [])
        history.append(ConversationMessage(role=role, content=content, mode=mode))
        if len(history) > config.MAX_HISTORY_LENGTH:
            self.progress_histories[order_id] = history[-config.MAX_HISTORY_LENGTH:]

    def get_progress_history(self, order_id: int) -> List[ConversationMessage]:
        """获取订单进度助手历史"""
        return self.progress_histories.get(order_id, [])

    def add_progress_session_message(self, session_id: str, role: str, content: str, mode: str = "online"):
        """记录制作进度助手的会话级对话"""
        history = self.progress_session_histories.setdefault(session_id, [])
        history.append(ConversationMessage(role=role, content=content, mode=mode))
        if len(history) > config.MAX_HISTORY_LENGTH:
            self.progress_session_histories[session_id] = history[-config.MAX_HISTORY_LENGTH:]

    def get_progress_session_history(self, session_id: str) -> List[ConversationMessage]:
        """获取会话级进度助手历史"""
        return self.progress_session_histories.get(session_id, [])

    def reset_progress_session(self, session_id: str):
        """清理会话级进度助手历史"""
        if session_id in self.progress_session_histories:
            del self.progress_session_histories[session_id]

    def add_order_to_history(self, session_id: str, order_id: int, max_orders: int = 5):
        """
        添加订单到历史记录，并清理超过限制的对话历史

        Args:
            session_id: 会话 ID
            order_id: 订单 ID
            max_orders: 保留的最大订单数量（默认 5）
        """
        session = self.get_session(session_id)

        # 添加订单 ID 到历史列表
        session.order_history.append(order_id)

        # 如果订单数量超过限制，需要清理旧的对话历史
        if len(session.order_history) > max_orders:
            # 计算需要删除的订单数量
            orders_to_remove = len(session.order_history) - max_orders

            # 移除最旧的订单 ID
            removed_orders = session.order_history[:orders_to_remove]
            session.order_history = session.order_history[orders_to_remove:]

            # 清理与这些订单相关的对话历史
            # 策略：找到第一个保留订单之前的所有对话，全部删除
            # 假设：每个订单确认时会在对话中包含订单号信息
            self._trim_history_before_orders(session, removed_orders)

        self.update_session(session_id, session)

    def _trim_history_before_orders(self, session: SessionState, removed_orders: List[int]):
        """
        清理与已移除订单相关的对话历史

        策略：保留从最早保留订单开始的所有对话
        如果无法精确定位，至少保留最近的对话

        Args:
            session: 会话状态
            removed_orders: 被移除的订单 ID 列表
        """
        if not session.order_history:
            # 如果没有保留订单，清空所有历史
            session.history = []
            return

        # 找到第一个保留订单的位置
        first_kept_order = session.order_history[0]
        order_marker = f"#{first_kept_order}"

        # 从后往前搜索，找到第一次提到该订单号的位置
        cutoff_index = 0
        for i in range(len(session.history) - 1, -1, -1):
            if order_marker in session.history[i].content:
                cutoff_index = max(0, i - 5)  # 保留订单确认前 5 条消息（上下文）
                break

        # 如果找不到订单号，保守策略：保留最近 20 条消息
        if cutoff_index == 0 and len(session.history) > 20:
            cutoff_index = len(session.history) - 20

        # 裁剪历史记录
        session.history = session.history[cutoff_index:]


# 全局会话管理器实例
session_manager = SessionManager()
