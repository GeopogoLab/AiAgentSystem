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
        self.progress_sessions: Dict[str, List[ConversationMessage]] = {}

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

    def add_progress_message(self, order_id: int, role: str, content: str, mode: str = "online"):
        """记录制作进度助手对话历史"""
        history = self.progress_histories.setdefault(order_id, [])
        history.append(ConversationMessage(role=role, content=content, mode=mode))
        max_len = config.MAX_HISTORY_LENGTH * 2
        if len(history) > max_len:
            self.progress_histories[order_id] = history[-max_len:]

    def get_progress_history(self, order_id: int) -> List[ConversationMessage]:
        """获取指定订单的进度助手对话历史"""
        return self.progress_histories.get(order_id, [])

    def add_progress_session_message(self, session_id: str, role: str, content: str, mode: str = "online"):
        """记录会话级别的进度助手对话历史"""
        history = self.progress_sessions.setdefault(session_id, [])
        history.append(ConversationMessage(role=role, content=content, mode=mode))
        max_len = config.MAX_HISTORY_LENGTH * 2
        if len(history) > max_len:
            self.progress_sessions[session_id] = history[-max_len:]

    def get_progress_session_history(self, session_id: str) -> List[ConversationMessage]:
        """获取会话级别的进度助手对话历史"""
        return self.progress_sessions.get(session_id, [])

    def reset_progress_session(self, session_id: str):
        """重置会话级别的进度助手历史"""
        if session_id in self.progress_sessions:
            del self.progress_sessions[session_id]

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
        self.reset_progress_session(session_id)

    def delete_session(self, session_id: str):
        """
        删除会话

        Args:
            session_id: 会话 ID
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
        self.reset_progress_session(session_id)

    def get_all_sessions(self) -> Dict[str, SessionState]:
        """
        获取所有会话

        Returns:
            所有会话的字典
        """
        return self.sessions


# 全局会话管理器实例
session_manager = SessionManager()
