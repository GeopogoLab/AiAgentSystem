#!/usr/bin/env python3
"""测试跨会话订单查询功能"""
import requests

BASE_URL = "http://localhost:8000"

def test_order_query():
    """测试查询不在当前会话中创建的订单"""

    # 使用一个新的 session_id，确保订单 #52 不是在这个会话中创建的
    new_session_id = "test_cross_session_query_v2"

    print("=" * 60)
    print("测试场景：用户在新会话中询问订单信息")
    print("=" * 60)

    # 测试0：询问"目前订单有哪些"（用户报告的问题）
    print("\n【测试0】用户问：目前订单有哪些")
    response = requests.post(
        f"{BASE_URL}/text",
        data={"session_id": new_session_id, "text": "目前订单有哪些"}
    )
    if response.ok:
        data = response.json()
        print(f"AI回复: {data['assistant_reply']}")
    else:
        print(f"请求失败: {response.status_code}")

    # 测试1：询问"现在有多少订单"
    print("\n【测试1】用户问：现在有多少订单")
    response = requests.post(
        f"{BASE_URL}/text",
        data={"session_id": new_session_id, "text": "现在有多少订单"}
    )
    if response.ok:
        data = response.json()
        print(f"AI回复: {data['assistant_reply']}")
    else:
        print(f"请求失败: {response.status_code}")

    # 测试2：询问"52呢"
    print("\n【测试2】用户问：52呢")
    response = requests.post(
        f"{BASE_URL}/text",
        data={"session_id": new_session_id, "text": "52呢"}
    )
    if response.ok:
        data = response.json()
        print(f"AI回复: {data['assistant_reply']}")
    else:
        print(f"请求失败: {response.status_code}")

    # 测试3：询问"订单52是什么"
    print("\n【测试3】用户问：订单52是什么")
    response = requests.post(
        f"{BASE_URL}/text",
        data={"session_id": new_session_id, "text": "订单52是什么"}
    )
    if response.ok:
        data = response.json()
        print(f"AI回复: {data['assistant_reply']}")
    else:
        print(f"请求失败: {response.status_code}")

    # 测试4：询问不存在的订单
    print("\n【测试4】用户问：订单999呢")
    response = requests.post(
        f"{BASE_URL}/text",
        data={"session_id": new_session_id, "text": "订单999呢"}
    )
    if response.ok:
        data = response.json()
        print(f"AI回复: {data['assistant_reply']}")
    else:
        print(f"请求失败: {response.status_code}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_order_query()
