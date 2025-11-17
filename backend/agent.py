"""LLM Agent 点单逻辑"""
import json
import logging
from typing import List, Dict, Optional, Any
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
from .database import db
from .production import build_order_progress, build_queue_snapshot

logger = logging.getLogger(__name__)


class TeaOrderAgent:
    """奶茶点单 Agent（支持 Function Calling）"""

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
        self.tools = self._build_tools()

    def _build_tools(self) -> List[Dict[str, Any]]:
        """构建 Function Calling 工具定义"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_order_status",
                    "description": "查询指定订单的制作进度、预计完成时间（ETA）和订单详情（饮品名、规格等）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "integer",
                                "description": "订单编号，例如 5 表示订单 #5"
                            }
                        },
                        "required": ["order_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_all_orders_queue",
                    "description": "查看当前所有订单的排队和制作状态，包括各订单的编号、阶段、预计完成时间和订单内容（饮品、规格）",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        menu_list = "\n".join([f"- {item.name}（{item.category}）: {item.description}, ¥{item.base_price}" for item in TEA_MENU])

        return f"""你是一个专业的奶茶店接待员，负责帮助顾客点单和查询订单进度。

⚠️ **重要：你必须严格按照 JSON 格式回复，任何回复都必须是有效的 JSON 对象！**

你的任务是：

1. **角色定位**：
   - 使用友好、热情的中文与顾客对话
   - 态度专业，帮助顾客做出选择
   - 每次只问 1-2 个关键问题，不要一次问太多
   - **所有回复必须是 JSON 格式，不能是纯文本**

2. **菜单信息**：
{menu_list}

3. **配置选项**：
   - 杯型：{', '.join(SIZE_OPTIONS)}
   - 甜度：{', '.join(SUGAR_OPTIONS)}
   - 冰块：{', '.join(ICE_OPTIONS)}
   - 加料：{', '.join(TOPPING_OPTIONS)}

4. **工具使用**（重要）：
   当顾客询问订单进度或排队情况时，你**必须**调用工具获取实时数据，**不要**编造或猜测进度信息：
   - 询问具体订单进度时（例如"订单 #5 做好了吗"、"查一下我的订单"），调用 get_order_status(order_id)
   - 询问全局排队情况时（例如"现在队伍排到哪了"），调用 get_all_orders_queue()
   - 调用工具后，根据返回的数据用自然语言回答顾客
   - **重要**：工具会返回订单的详细信息（饮品名、规格、加料等），当顾客询问"这个订单是啥"、"订单内容"时，你必须从工具返回的数据中提取并告诉顾客订单的具体内容
   - 如果顾客说"我的订单"但没有提供订单号，且当前 order_state.is_complete=false（正在点单），说明是在询问刚下的订单，礼貌询问订单号

5. **收集信息**（点单时）：
   当顾客要点单时，收集以下订单信息：
   - drink_name: 饮品名称（必须）
   - size: 杯型（必须）
   - sugar: 甜度（必须）
   - ice: 冰块（必须）
   - toppings: 加料列表（可选，默认为空）
   - notes: 备注（可选）

6. **对话规则**：
   - 如果顾客询问进度，优先调用工具，不要编造数据
   - 如果顾客要点单，按照收集信息流程进行
   - 如果顾客说的饮品不在菜单上，礼貌地提示并推荐菜单上的饮品
   - 如果信息不完整，继续询问缺失的字段
   - 如果有歧义，复述确认
   - 当所有必填信息收集齐全时，向顾客总结订单并询问是否确认
   - 顾客确认后，明确表示订单已完成

7. **输出格式**（非常重要！）：

   无论什么情况，你的回复**必须是有效的 JSON 对象**，包含以下三个字段：
   {{
       "assistant_reply": "给顾客的回复文本",
       "order_state": {{...订单状态对象...}},
       "action": "动作类型"
   }}

   **点单模式**（顾客正在点单时）：
   - assistant_reply: 给顾客的回复（中文字符串）
   - order_state: 当前订单状态（JSON 对象）
   - action: 下一步动作（字符串）

   action 的可能值：
   - "ask_more": 信息未收集齐全，继续询问
   - "confirm": 信息已齐全，复述订单等待顾客确认
   - "save_order": 顾客已确认，可以保存订单

   **查询模式**（顾客询问进度时）：
   - 使用工具调用（get_order_status 或 get_all_orders_queue）获取数据
   - 工具调用会自动处理，你只需要按照工具指示操作
   - 不要直接返回 JSON，而是调用工具

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

⚠️ **再次提醒：你的回复必须是完整的、有效的 JSON 对象。不要返回纯文本，不要在 JSON 外添加任何解释。**

如果顾客询问进度，使用工具调用而不是直接回复。"""

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

        # 调用 LLM（支持 Function Calling）
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=config.OPENAI_TEMPERATURE,
                tools=self.tools,
                tool_choice="auto"
                # 注意：不能同时使用 response_format + tools，某些 provider 不支持
            )

            message = response.choices[0].message

            # 处理 Tool Calls
            if message.tool_calls:
                return await self._handle_tool_calls(
                    messages=messages,
                    tool_calls=message.tool_calls,
                    current_order_state=current_order_state
                )

            # 无工具调用，解析正常回复（JSON 格式）
            if not message.content:
                raise ValueError("LLM 返回空内容")

            # 尝试解析 JSON（可能包裹在 ```json 或其他文本中）
            content = message.content.strip()

            # 提取 JSON 部分
            json_str = content
            if "```json" in content:
                # 提取 ```json ... ``` 之间的内容
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end > start:
                    json_str = content[start:end].strip()
            elif "```" in content:
                # 提取 ``` ... ``` 之间的内容
                start = content.find("```") + 3
                end = content.find("```", start)
                if end > start:
                    json_str = content[start:end].strip()
            elif content.startswith("{") and content.endswith("}"):
                # 看起来像纯 JSON
                json_str = content
            else:
                # 尝试找到 { ... } 结构
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx+1]

            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON 解析失败。原始内容: {content[:500]}")
                logger.error(f"提取的 JSON: {json_str[:500]}")
                raise ValueError(f"JSON 解析失败: {json_err}")

            # 验证必需字段
            if "assistant_reply" not in result or "order_state" not in result or "action" not in result:
                logger.error(f"JSON 缺少必需字段。解析结果: {result}")
                raise ValueError("JSON 缺少必需字段（assistant_reply, order_state, action）")

            # 构建 AgentResponse
            agent_response = AgentResponse(
                assistant_reply=result["assistant_reply"],
                order_state=OrderState(**result["order_state"]),
                action=AgentAction(result["action"]),
                mode="online"
            )

            return agent_response

        except Exception as e:
            logger.error(f"LLM 调用异常: {type(e).__name__}: {e}", exc_info=True)
            logger.warning("LLM 调用失败，切换离线模式：%s", e)
            return self._offline_response(
                user_text=user_text,
                current_order_state=current_order_state,
                reason=f"LLM 调用失败：{str(e)}"
            )

    async def _handle_tool_calls(
        self,
        messages: List[Dict[str, Any]],
        tool_calls: Any,
        current_order_state: OrderState
    ) -> AgentResponse:
        """执行工具调用并获取最终回复"""
        # 添加 assistant 的工具调用消息
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }
                for tool_call in tool_calls
            ]
        })

        # 执行每个工具调用
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            logger.info(f"调用工具: {function_name}，参数: {function_args}")

            # 执行工具
            result = await self._execute_tool(function_name, function_args)

            # 添加工具结果到消息历史
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": json.dumps(result, ensure_ascii=False)
            })

        # 让 LLM 根据工具结果生成最终回复（用自然语言包装工具返回的数据）
        # 添加明确的指示，要求返回标准 JSON 格式
        messages.append({
            "role": "system",
            "content": """基于工具返回的数据，用自然语言回复顾客。

工具返回的数据包含：
- 订单进度信息（current_stage_label, eta_seconds等）
- 订单详细内容（drink_name, size, sugar, ice, toppings）

当顾客询问"这个订单是啥"、"订单内容"等问题时，你必须从工具返回的数据中提取并告诉顾客订单的具体内容（饮品名、规格、加料）。

必须返回 JSON 格式：
{
    "assistant_reply": "用自然语言描述工具返回的信息，包括订单进度和订单详细内容（如果顾客询问的话）",
    "order_state": 当前订单状态（如果顾客正在点单则更新，否则保持原状态）,
    "action": "ask_more"（查询进度时默认使用 ask_more）
}"""
        })

        final_response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=config.OPENAI_TEMPERATURE,
            response_format={"type": "json_object"}
        )

        final_content = final_response.choices[0].message.content
        if not final_content:
            raise ValueError("工具调用后 LLM 返回空内容")

        # 使用增强的 JSON 提取逻辑
        content = final_content.strip()
        json_str = content
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                json_str = content[start:end].strip()
        elif content.startswith("{") and content.endswith("}"):
            json_str = content
        else:
            start_idx = content.find("{")
            end_idx = content.rfind("}")
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx+1]

        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"工具调用后 JSON 解析失败。原始内容: {final_content[:500]}")
            raise ValueError(f"工具调用后 JSON 解析失败: {e}")

        return AgentResponse(
            assistant_reply=result["assistant_reply"],
            order_state=OrderState(**result.get("order_state", current_order_state.model_dump())),
            action=AgentAction(result.get("action", "ask_more")),
            mode="online"
        )

    async def _execute_tool(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行具体工具"""
        from fastapi.encoders import jsonable_encoder

        if function_name == "get_order_status":
            order_id = arguments["order_id"]
            order = db.get_order(order_id)
            if not order:
                return {"error": f"订单 #{order_id} 不存在"}
            progress = build_order_progress(order)
            return jsonable_encoder(progress)

        elif function_name == "get_all_orders_queue":
            orders = db.get_recent_orders(50)
            snapshot = build_queue_snapshot(orders)
            return jsonable_encoder(snapshot)

        else:
            return {"error": f"未知工具: {function_name}"}

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
