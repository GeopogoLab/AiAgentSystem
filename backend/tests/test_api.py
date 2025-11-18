"""测试API端点"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import db
from backend.models import OrderState


class TestAPI:
    """API端点测试类"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    def test_root_endpoint(self, client):
        """测试根路径"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Tea Order Agent System API"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data

    def test_health_endpoint(self, client):
        """测试健康检查"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_get_orders_empty(self, client):
        """测试获取订单（空列表）"""
        response = client.get("/orders")

        assert response.status_code == 200
        data = response.json()
        assert "orders" in data
        assert "total" in data
        assert isinstance(data["orders"], list)

    def test_get_nonexistent_order(self, client):
        """测试获取不存在的订单"""
        response = client.get("/orders/99999")

        assert response.status_code == 404

    def test_get_session(self, client):
        """测试获取会话状态"""
        session_id = "test_api_session"
        response = client.get(f"/session/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert "history" in data
        assert "order_state" in data
        assert "status" in data

    def test_reset_session(self, client):
        """测试重置会话"""
        session_id = "test_reset_session"
        response = client.post(f"/reset/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "会话已重置"
        assert data["session_id"] == session_id

    def test_order_status_and_progress_chat(self, client):
        """制作进度接口"""
        order_state = OrderState(
            drink_name="乌龙奶茶",
            size="大杯",
            sugar="三分糖",
            ice="少冰",
            toppings=[],
            is_complete=True,
        )
        order_id = db.save_order("status_test", order_state)

        status_resp = client.get(f"/orders/{order_id}/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["order_id"] == order_id

        chat_resp = client.post(
            f"/orders/{order_id}/progress-chat",
            json={"question": "还要多久？"},
        )
        assert chat_resp.status_code == 200
        chat_data = chat_resp.json()
        assert "orders" not in chat_data
        assert chat_data["progress"]["order_id"] == order_id
        history_resp = client.get(f"/orders/{order_id}/progress-history")
        assert history_resp.status_code == 200
        history_data = history_resp.json()
        assert history_data["order_id"] == order_id
        assert len(history_data["history"]) == 2
        assert history_data["history"][0]["role"] == "user"
        queue_resp = client.get("/production/queue")
        assert queue_resp.status_code == 200
        queue_data = queue_resp.json()
        assert "active_orders" in queue_data

    def test_progress_chat_session_endpoint(self, client):
        """会话级别进度助手"""
        session_id = "progress_session_test"
        order_state = OrderState(
            drink_name="红茶拿铁",
            size="中杯",
            sugar="七分糖",
            ice="正常冰",
            toppings=["珍珠"],
            is_complete=True,
        )
        order_id = db.save_order("progress_session", order_state)

        resp = client.post(
            "/progress/chat",
            json={"session_id": session_id, "question": f"订单 #{order_id} 还有多久？"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["order_id"] == order_id
        assert data["answer"]

        history_resp = client.get(f"/progress/history/{session_id}")
        assert history_resp.status_code == 200
        history_data = history_resp.json()
        assert history_data["session_id"] == session_id
        assert len(history_data["history"]) == 2

    def test_text_endpoint_without_api_key(self, client):
        """测试文本端点（无有效API key）"""
        response = client.post(
            "/text",
            data={
                "session_id": "test_text_session",
                "text": "我要一杯奶茶"
            }
        )

        # 即使API key无效，也应该返回200并有错误处理
        assert response.status_code == 200
        data = response.json()
        assert "assistant_reply" in data
        assert "order_state" in data
        assert "order_status" in data

    def test_cors_headers(self, client):
        """测试CORS头"""
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )

        # CORS应该允许跨域请求
        assert "access-control-allow-origin" in [h.lower() for h in response.headers.keys()]

    def test_tts_without_api_key(self, client):
        """TTS 未配置 key 时自动使用 gTTS"""
        from backend.config import config

        prev_key = config.ASSEMBLYAI_API_KEY
        prev_provider = config.TTS_PROVIDER
        config.ASSEMBLYAI_API_KEY = ""
        config.TTS_PROVIDER = "gtts"
        try:
            response = client.post("/tts", json={"text": "hello world"})
            assert response.status_code == 200
            data = response.json()
            assert data["audio_base64"]
            assert data["format"] == "mp3"
        finally:
            config.ASSEMBLYAI_API_KEY = prev_key
            config.TTS_PROVIDER = prev_provider


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
