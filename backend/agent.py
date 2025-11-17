"""LLM Agent 点单逻辑"""
import json
import logging
from typing import List, Dict, Optional
from openai import AsyncOpenAI
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

logger = logging.getLogger(__name__)


class TeaOrderAgent:
    """奶茶点单 Agent"""

    def __init__(self):
        """初始化 Agent"""
        api_key = (config.OPENROUTER_API_KEY or "").strip()
        if api_key:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=config.OPENROUTER_BASE_URL,
                default_headers=self._build_default_headers()
            )
        else:
            logger.warning("未配置 OPENROUTER_API_KEY，AI 接待员将使用离线规则引擎。")
            self.client = None
        self.model = config.OPENROUTER_MODEL

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

        if not self.client:
            return self._offline_response(
                user_text=user_text,
                current_order_state=current_order_state,
                reason="未配置 OPENROUTER_API_KEY，暂时使用规则引擎协助点单"
            )

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
                action=AgentAction(result["action"]),
                mode="online"
            )

            return agent_response

        except Exception as e:
            logger.warning("LLM 调用失败，切换离线模式：%s", e)
            return self._offline_response(
                user_text=user_text,
                current_order_state=current_order_state,
                reason=f"LLM 调用失败：{str(e)}"
            )

    def _build_default_headers(self) -> Dict[str, str]:
        """构建 OpenRouter 默认请求头"""
        headers: Dict[str, str] = {}
        if config.OPENROUTER_SITE_URL:
            headers["HTTP-Referer"] = config.OPENROUTER_SITE_URL
        if config.OPENROUTER_SITE_NAME:
            headers["X-Title"] = config.OPENROUTER_SITE_NAME
        return headers

    def _offline_response(
        self,
        user_text: str,
        current_order_state: OrderState,
        reason: Optional[str] = None
    ) -> AgentResponse:
        """
        当 LLM 不可用时的降级策略
        """
        state = current_order_state.model_copy(deep=True)
        text = user_text or ""
        normalized_text = text.replace("，", " ").replace("。", " ")

        # 推断饮品名称
        for item in TEA_MENU:
            if item.name in normalized_text:
                state.drink_name = item.name
                break

        # 推断杯型/甜度/冰块
        state.size = state.size or self._match_option(normalized_text, SIZE_OPTIONS)
        state.sugar = state.sugar or self._match_option(normalized_text, SUGAR_OPTIONS)
        state.ice = state.ice or self._match_option(normalized_text, ICE_OPTIONS)

        # 处理加料
        if any(keyword in normalized_text for keyword in ["不要加料", "不加料", "不用加料"]):
            state.toppings = []
        else:
            for topping in TOPPING_OPTIONS:
                if topping in normalized_text and topping not in state.toppings:
                    state.toppings.append(topping)

        # 更新完成状态
        required_fields = ["drink_name", "size", "sugar", "ice"]
        state.is_complete = all(getattr(state, field) for field in required_fields)

        confirm_keywords = ["确认", "可以", "没问题", "下单", "就这样", "好的", "没了"]
        action = AgentAction.ASK_MORE
        reply_body: str

        missing_field = next((field for field in required_fields if not getattr(state, field)), None)

        if missing_field:
            reply_body = self._build_missing_field_prompt(missing_field, state)
        elif state.is_complete and any(keyword in normalized_text for keyword in confirm_keywords):
            action = AgentAction.SAVE_ORDER
            reply_body = f"已确认：{self._build_order_summary(state)}。稍等片刻，我们马上为您准备。"
        elif state.is_complete:
            action = AgentAction.CONFIRM
            reply_body = f"{self._build_order_summary(state)}。请确认是否需要调整。"
        else:
            reply_body = "我还需要更多信息，请告诉我想要的饮品、杯型、甜度以及冰块。"

        notice = "【离线模式】"
        if reason:
            notice += f"{reason}。"
            logger.warning("触发离线模式，原因：%s", reason)

        return AgentResponse(
            assistant_reply=f"{notice}{reply_body}",
            order_state=state,
            action=action,
            mode="offline"
        )

    def _match_option(self, text: str, options: List[str]) -> Optional[str]:
        """根据文本匹配预定义选项"""
        for option in options:
            if option in text:
                return option
        return None

    def _build_missing_field_prompt(self, field: str, state: OrderState) -> str:
        """根据缺失字段构建提示语"""
        menu_names = "、".join(item.name for item in TEA_MENU)
        if field == "drink_name":
            return f"请告诉我您想喝的饮品，可以选择：{menu_names}。"
        if field == "size":
            drink = state.drink_name or "这杯饮品"
            return f"已记录{drink}，请告诉我杯型（{'、'.join(SIZE_OPTIONS)}）。"
        if field == "sugar":
            return f"杯型已记录，请选择甜度（{'、'.join(SUGAR_OPTIONS)}）。"
        if field == "ice":
            return f"好的，再告诉我冰块偏好（{'、'.join(ICE_OPTIONS)}）。"
        return "请继续完善订单信息。"

    def _build_order_summary(self, state: OrderState) -> str:
        """构建订单摘要"""
        parts = []
        if state.size and state.drink_name:
            parts.append(f"{state.size}{state.drink_name}")
        elif state.drink_name:
            parts.append(state.drink_name)
        if state.sugar:
            parts.append(state.sugar)
        if state.ice:
            parts.append(state.ice)
        if state.toppings:
            parts.append(f"加料：{'、'.join(state.toppings)}")
        return "，".join(parts)


# 全局 Agent 实例
tea_agent = TeaOrderAgent()
