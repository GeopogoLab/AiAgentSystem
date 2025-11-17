"""测试会话管理模块"""
import pytest
from backend.session_manager import SessionManager
from backend.models import OrderState, OrderStatus


class TestSessionManager:
    """会话管理器测试类"""

    @pytest.fixture
    def manager(self):
        """创建会话管理器实例"""
        return SessionManager()

    def test_get_new_session(self, manager):
        """测试获取新会话"""
        session = manager.get_session("test_session_1")

        assert session.session_id == "test_session_1"
        assert len(session.history) == 0
        assert session.status == OrderStatus.COLLECTING
        assert session.order_state.drink_name is None

    def test_get_existing_session(self, manager):
        """测试获取已存在的会话"""
        # 第一次获取
        session_id = "test_session_2"
        manager.add_message(session_id, "user", "你好")

        # 第二次获取
        session2 = manager.get_session(session_id)

        assert session2.session_id == session_id
        assert len(session2.history) == 1
        assert session2.history[0].content == "你好"

    def test_add_message(self, manager):
        """测试添加消息"""
        session_id = "test_session_3"

        manager.add_message(session_id, "user", "我要奶茶")
        manager.add_message(session_id, "assistant", "好的")

        session = manager.get_session(session_id)

        assert len(session.history) == 2
        assert session.history[0].role == "user"
        assert session.history[0].content == "我要奶茶"
        assert session.history[1].role == "assistant"
        assert session.history[1].content == "好的"

    def test_update_order_state(self, manager):
        """测试更新订单状态"""
        session_id = "test_session_4"

        order_state = OrderState(
            drink_name="乌龙奶茶",
            size="大杯",
            sugar="三分糖",
            ice="去冰",
            toppings=["珍珠"],
            is_complete=False
        )

        manager.update_order_state(session_id, order_state)
        session = manager.get_session(session_id)

        assert session.order_state.drink_name == "乌龙奶茶"
        assert session.order_state.size == "大杯"
        assert "珍珠" in session.order_state.toppings

    def test_update_status(self, manager):
        """测试更新会话状态"""
        session_id = "test_session_5"

        manager.update_status(session_id, OrderStatus.CONFIRMING)
        session = manager.get_session(session_id)

        assert session.status == OrderStatus.CONFIRMING

    def test_reset_session(self, manager):
        """测试重置会话"""
        session_id = "test_session_6"

        # 先添加一些数据
        manager.add_message(session_id, "user", "你好")
        order_state = OrderState(drink_name="奶茶", is_complete=False)
        manager.update_order_state(session_id, order_state)

        # 重置
        manager.reset_session(session_id)
        session = manager.get_session(session_id)

        assert len(session.history) == 0
        assert session.order_state.drink_name is None
        assert session.status == OrderStatus.COLLECTING
        assert session.last_order_total is None

    def test_delete_session(self, manager):
        """测试删除会话"""
        session_id = "test_session_7"

        # 创建会话
        manager.get_session(session_id)
        assert session_id in manager.sessions

        # 删除会话
        manager.delete_session(session_id)
        assert session_id not in manager.sessions

    def test_get_all_sessions(self, manager):
        """测试获取所有会话"""
        # 创建多个会话
        for i in range(3):
            manager.get_session(f"session_{i}")

        sessions = manager.get_all_sessions()

        assert len(sessions) >= 3
        assert "session_0" in sessions
        assert "session_1" in sessions
        assert "session_2" in sessions

    def test_message_history_limit(self, manager):
        """测试消息历史记录限制"""
        session_id = "test_session_8"

        # 添加超过限制的消息
        for i in range(25):  # 假设限制是10轮(20条消息)
            manager.add_message(session_id, "user", f"消息{i}")
            manager.add_message(session_id, "assistant", f"回复{i}")

        session = manager.get_session(session_id)

        # 应该只保留最新的20条消息（10轮）
        assert len(session.history) == 20

    def test_progress_history(self, manager):
        """测试进度助手历史"""
        order_id = 42
        manager.add_progress_message(order_id, "user", "多久好？")
        manager.add_progress_message(order_id, "assistant", "约两分钟", mode="online")

        history = manager.get_progress_history(order_id)
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].mode == "online"

    def test_progress_session_history(self, manager):
        """测试进度助手会话历史"""
        session_id = "progress_session"
        manager.add_progress_session_message(session_id, "user", "你好")
        manager.add_progress_session_message(session_id, "assistant", "请提供订单号", mode="offline")

        history = manager.get_progress_session_history(session_id)
        assert len(history) == 2
        assert history[0].content == "你好"
        assert history[1].mode == "offline"

        manager.reset_progress_session(session_id)
        assert manager.get_progress_session_history(session_id) == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
