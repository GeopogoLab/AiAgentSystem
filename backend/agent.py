"""LLM Agent 点单逻辑"""
import json
from openai import AsyncOpenAI
from typing import List, Dict
from .config import config
from .models import (
    OrderState,
    AgentResponse,
    AgentAction,
    TEA_MENU,
    SIZE_OPTIONS,
    SUGAR_OPTIONS,
    ICE_OPTIONS,
    TOPPING_OPTIONS
)


class TeaOrderAgent:
    """奶茶点单 Agent"""

    def __init__(self):
        """初始化 Agent"""
        self.client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.OPENAI_MODEL

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        menu_list = "\n".join([f"- {item.name}（{item.category}）: {item.description}, ¥{item.base_price}" for item in TEA_MENU])

        return f"""你是一个专业的奶茶店接待员，负责帮助顾客点单。你的任务是：

1. **角色定位**：
   - 使用友好、热情的中文与顾客对话
   - 态度专业，帮助顾客做出选择
   - 每次只问 1-2 个关键问题，不要一次问太多

2. **菜单信息**：
{menu_list}

3. **配置选项**：
   - 杯型：{', '.join(SIZE_OPTIONS)}
   - 甜度：{', '.join(SUGAR_OPTIONS)}
   - 冰块：{', '.join(ICE_OPTIONS)}
   - 加料：{', '.join(TOPPING_OPTIONS)}

4. **收集信息**：
   你需要收集以下订单信息：
   - drink_name: 饮品名称（必须）
   - size: 杯型（必须）
   - sugar: 甜度（必须）
   - ice: 冰块（必须）
   - toppings: 加料列表（可选，默认为空）
   - notes: 备注（可选）

5. **对话规则**：
   - 如果顾客说的饮品不在菜单上，礼貌地提示并推荐菜单上的饮品
   - 如果信息不完整，继续询问缺失的字段
   - 如果有歧义，复述确认
   - 当所有必填信息收集齐全时，向顾客总结订单并询问是否确认
   - 顾客确认后，明确表示订单已完成

6. **输出格式**：
   你必须返回 JSON 格式，包含三个字段：
   - assistant_reply: 给顾客的回复（中文字符串）
   - order_state: 当前订单状态（JSON 对象）
   - action: 下一步动作（字符串）

   action 的可能值：
   - "ask_more": 信息未收集齐全，继续询问
   - "confirm": 信息已齐全，复述订单等待顾客确认
   - "save_order": 顾客已确认，可以保存订单

   order_state 的格式：
   {{
       "drink_name": "饮品名称或null",
       "size": "杯型或null",
       "sugar": "甜度或null",
       "ice": "冰块或null",
       "toppings": ["加料1", "加料2"],
       "notes": "备注或null",
       "is_complete": true/false
   }}

7. **示例对话**：

   顾客："我要一杯奶茶"
   回复：
   {{
       "assistant_reply": "好的！请问您想要哪一款呢？我们有乌龙奶茶、茉莉奶绿、红茶拿铁等。",
       "order_state": {{"drink_name": null, "size": null, "sugar": null, "ice": null, "toppings": [], "notes": null, "is_complete": false}},
       "action": "ask_more"
   }}

   顾客："乌龙奶茶"
   回复：
   {{
       "assistant_reply": "好的，乌龙奶茶！请问您要什么杯型？我们有小杯、中杯、大杯。甜度和冰块呢？",
       "order_state": {{"drink_name": "乌龙奶茶", "size": null, "sugar": null, "ice": null, "toppings": [], "notes": null, "is_complete": false}},
       "action": "ask_more"
   }}

   顾客："大杯，三分糖，去冰"
   回复：
   {{
       "assistant_reply": "好的！为您确认一下：大杯乌龙奶茶，三分糖，去冰。请问需要加料吗？比如珍珠、布丁、仙草等。",
       "order_state": {{"drink_name": "乌龙奶茶", "size": "大杯", "sugar": "三分糖", "ice": "去冰", "toppings": [], "notes": null, "is_complete": false}},
       "action": "ask_more"
   }}

   顾客："加珍珠"
   回复：
   {{
       "assistant_reply": "好的！为您下单：大杯乌龙奶茶，三分糖，去冰，加珍珠。请问确认下单吗？",
       "order_state": {{"drink_name": "乌龙奶茶", "size": "大杯", "sugar": "三分糖", "ice": "去冰", "toppings": ["珍珠"], "notes": null, "is_complete": true}},
       "action": "confirm"
   }}

   顾客："确认"
   回复：
   {{
       "assistant_reply": "好的，订单已确认！您的订单是：大杯乌龙奶茶，三分糖，去冰，加珍珠。请稍等，马上为您准备！",
       "order_state": {{"drink_name": "乌龙奶茶", "size": "大杯", "sugar": "三分糖", "ice": "去冰", "toppings": ["珍珠"], "notes": null, "is_complete": true}},
       "action": "save_order"
   }}

请严格按照上述格式返回 JSON。"""

    async def process(
        self,
        user_text: str,
        history: List[Dict[str, str]],
        current_order_state: OrderState
    ) -> AgentResponse:
        """
        处理用户输入，返回 Agent 响应

        Args:
            user_text: 用户输入的文本
            history: 对话历史
            current_order_state: 当前订单状态

        Returns:
            Agent 响应
        """
        # 构建消息列表
        messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]

        # 添加历史对话
        messages.extend(history)

        # 添加当前订单状态上下文
        context = f"当前订单状态：{current_order_state.model_dump_json(indent=2, exclude_none=False)}"
        messages.append({
            "role": "system",
            "content": context
        })

        # 添加用户消息
        messages.append({
            "role": "user",
            "content": user_text
        })

        # 调用 OpenAI API
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=config.OPENAI_TEMPERATURE,
                response_format={"type": "json_object"}  # 强制返回 JSON
            )

            # 解析响应
            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            # 构建 AgentResponse
            agent_response = AgentResponse(
                assistant_reply=result["assistant_reply"],
                order_state=OrderState(**result["order_state"]),
                action=AgentAction(result["action"])
            )

            return agent_response

        except Exception as e:
            # 如果出错，返回默认响应
            return AgentResponse(
                assistant_reply=f"抱歉，我遇到了一些问题。请您再说一次？（错误：{str(e)}）",
                order_state=current_order_state,
                action=AgentAction.ASK_MORE
            )


# 全局 Agent 实例
tea_agent = TeaOrderAgent()
