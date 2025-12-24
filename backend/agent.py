"""LLM Agent ordering logic"""
import json
import logging
from typing import List, Dict, Optional, Any
from .config import config
from .llm import LLMBackend, LLMBackendRouter
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
    """Tea ordering agent (supports Function Calling)"""

    def __init__(self):
        """Initialize agent"""
        self.llm_router = LLMBackendRouter(config)
        if not self.llm_router.backends:
            logger.warning("No online LLM providers available, will use offline rule engine.")
        self.tools = self._build_tools()

    def _build_tools(self) -> List[Dict[str, Any]]:
        """Build Function Calling tool definitions"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_order_status",
                    "description": "Query the production progress, estimated completion time (ETA), and order details (drink name, specs, etc.) for a specific order",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "integer",
                                "description": "Order number, e.g., 5 means order #5"
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
                    "description": "View the queue and production status of all current orders. When users ask 'what orders are there', 'how many orders', 'order list', 'all orders', etc., must call this tool to get real data. Returns information about active orders and recently completed orders (number, stage, estimated completion time, order content).",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]

    def _build_system_prompt(self) -> str:
        """Build system prompt"""
        menu_list = "\n".join([f"- {item.name} ({item.category}): {item.description}, ${item.base_price}" for item in TEA_MENU])

        return f"""You are a professional tea shop attendant, responsible for helping customers place orders and check order progress.

⚠️ **IMPORTANT: You MUST respond strictly in JSON format. All responses MUST be valid JSON objects!**

Your tasks:

1. **Role**:
   - Communicate with customers in friendly, warm English
   - Be professional and help customers make choices
   - Ask only 1-2 key questions at a time, don't ask too many at once
   - **All responses MUST be in JSON format, NOT plain text**

2. **Menu Information**:
{menu_list}

3. **Configuration Options**:
   - Size: {', '.join(SIZE_OPTIONS)}
   - Sweetness: {', '.join(SUGAR_OPTIONS)}
   - Ice: {', '.join(ICE_OPTIONS)}
   - Add-ons: {', '.join(TOPPING_OPTIONS)}

4. **Tool Usage** (Important):
   When customers inquire about order progress or queue status, you **MUST** call tools to get real-time data. **DO NOT** fabricate or guess progress information:

   **When to call get_all_orders_queue()**:
   - When customers ask about all orders, order list, queue status, **MUST** call this tool
   - Example triggers: "what orders are there", "how many orders", "where's the queue at", "order list", "all orders", "how many orders now"
   - **Key**: Don't guess or say "no orders", MUST call tool to query real data first

   **When to call get_order_status(order_id)**:
   - When asking about specific order progress (e.g., "is order #5 ready", "check my order", "52?", "#52"), **MUST** call this tool first
   - **Key**: Even if the order number wasn't created in current session, call tool first, don't directly say "doesn't exist"
   - Only if tool call fails (order truly doesn't exist), then tell customer "order doesn't exist"

   **After Tool Calls**:
   - After calling tool, answer customer in natural language based on returned data
   - **Important**: Tool returns detailed order information (drink name, specs, add-ons, etc.). When customers ask "what is this order", "order content", "what is it", you MUST extract from tool data and tell customer the specific order content
   - If customer says "my order" without providing order number, and current order_state.is_complete=false (ordering in progress), they're asking about just-placed order, politely ask for order number

5. **Collect Information** (When Ordering):
   When customers want to order, collect the following information:
   - drink_name: Drink name (required)
   - size: Size (required)
   - sugar: Sweetness (required)
   - ice: Ice level (required)
   - toppings: Add-ons list (optional, default empty)
   - notes: Notes (optional)

6. **Conversation Rules**:
   - If customer asks about progress, prioritize calling tools, don't fabricate data
   - If customer wants to order, follow information collection process
   - If drink isn't on menu, politely inform and recommend menu items
   - If information incomplete, continue asking for missing fields
   - If ambiguous, repeat back for confirmation
   - When all required info is collected, summarize order and ask customer to confirm
   - After customer confirms, clearly indicate order is complete

7. **Output Format** (Very Important!):

   In all cases, your response **MUST be a valid JSON object** containing these three fields:
   {{
       "assistant_reply": "reply text to customer",
       "order_state": {{...order state object...}},
       "action": "action type"
   }}

   **Ordering Mode** (customer is placing order):
   - assistant_reply: Reply to customer (English string)
   - order_state: Current order state (JSON object)
   - action: Next action (string)

   Possible action values:
   - "ask_more": Information incomplete, continue asking
   - "confirm": Information complete, repeat order and wait for customer confirmation
   - "save_order": Customer confirmed, can save order

   **Query Mode** (customer asking about progress):
   - Use tool calls (get_order_status or get_all_orders_queue) to get data
   - Tool calls handled automatically, you just follow tool instructions
   - Don't return JSON directly, call tool instead

   order_state format:
   {{
       "drink_name": "drink name or null",
       "size": "size or null",
       "sugar": "sweetness or null",
       "ice": "ice level or null",
       "toppings": ["topping1", "topping2"],
       "notes": "notes or null",
       "is_complete": true/false
   }}

7. **Example Conversation**:

   Customer: "I'd like a milk tea"
   Response:
   {{
       "assistant_reply": "Great! Which one would you like? We have Oolong Milk Tea, Jasmine Green Tea, Black Tea Latte, etc.",
       "order_state": {{"drink_name": null, "size": null, "sugar": null, "ice": null, "toppings": [], "notes": null, "is_complete": false}},
       "action": "ask_more"
   }}

   Customer: "Oolong Milk Tea"
   Response:
   {{
       "assistant_reply": "Sounds good, Oolong Milk Tea! What size would you like? We have Small, Medium, Large. And how about sweetness and ice?",
       "order_state": {{"drink_name": "Oolong Milk Tea", "size": null, "sugar": null, "ice": null, "toppings": [], "notes": null, "is_complete": false}},
       "action": "ask_more"
   }}

   Customer: "Large, 30% sweet, no ice"
   Response:
   {{
       "assistant_reply": "Perfect! Let me confirm: Large Oolong Milk Tea, 30% sweet, no ice. Would you like any add-ons? Like pearls, pudding, grass jelly, etc.",
       "order_state": {{"drink_name": "Oolong Milk Tea", "size": "Large", "sugar": "30% Sweet", "ice": "No Ice", "toppings": [], "notes": null, "is_complete": false}},
       "action": "ask_more"
   }}

   Customer: "Add pearls"
   Response:
   {{
       "assistant_reply": "Great! Your order: Large Oolong Milk Tea, 30% sweet, no ice, with pearls. Ready to confirm?",
       "order_state": {{"drink_name": "Oolong Milk Tea", "size": "Large", "sugar": "30% Sweet", "ice": "No Ice", "toppings": ["Pearls"], "notes": null, "is_complete": true}},
       "action": "confirm"
   }}

   Customer: "Yes, confirm"
   Response:
   {{
       "assistant_reply": "Perfect, order confirmed! Your order: Large Oolong Milk Tea, 30% sweet, no ice, with pearls. Please wait a moment, we'll prepare it right away!",
       "order_state": {{"drink_name": "Oolong Milk Tea", "size": "Large", "sugar": "30% Sweet", "ice": "No Ice", "toppings": ["Pearls"], "notes": null, "is_complete": true}},
       "action": "save_order"
   }}

⚠️ **Reminder: Your response MUST be a complete, valid JSON object. Don't return plain text, don't add any explanations outside JSON.**

If customer asks about progress, use tool calls instead of direct response."""

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

        if not self.llm_router.backends:
            return self._offline_response(
                user_text=user_text,
                current_order_state=current_order_state,
                reason="OpenRouter/VLLM not configured, temporarily using rule engine for ordering"
            )

        # Call LLM (supports Function Calling)
        try:
            logger.info(f"Preparing to call LLM, message count: {len(messages)}")

            response, provider = await self.llm_router.call_with_fallback(
                messages=messages,
                temperature=config.OPENAI_TEMPERATURE,
                tools=self.tools,
                tool_choice="auto"
            )

            logger.info(f"✅ LLM call successful, using backend: {provider.name}")
            message = response.choices[0].message

            # 处理 Tool Calls
            if message.tool_calls:
                return await self._handle_tool_calls(
                    messages=messages,
                    tool_calls=message.tool_calls,
                    current_order_state=current_order_state,
                    primary_backend=provider
                )

            # No tool calls, parse normal response (JSON format)
            if not message.content:
                raise ValueError("LLM returned empty content")

            # Try to parse JSON (may be wrapped in ```json or other text)
            content = message.content.strip()

            # Extract JSON part
            json_str = content
            if "```json" in content:
                # Extract content between ```json ... ```
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end > start:
                    json_str = content[start:end].strip()
            elif "```" in content:
                # Extract content between ``` ... ```
                start = content.find("```") + 3
                end = content.find("```", start)
                if end > start:
                    json_str = content[start:end].strip()
            elif content.startswith("{") and content.endswith("}"):
                # Looks like pure JSON
                json_str = content
            else:
                # Try to find { ... } structure
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx+1]

            try:
                result = json.loads(json_str)
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON parsing failed. Original content: {content[:500]}")
                logger.error(f"Extracted JSON: {json_str[:500]}")
                raise ValueError(f"JSON parsing failed: {json_err}")

            # Validate required fields
            if "assistant_reply" not in result or "order_state" not in result or "action" not in result:
                logger.error(f"JSON missing required fields. Parse result: {result}")
                raise ValueError("JSON missing required fields (assistant_reply, order_state, action)")

            # Build AgentResponse
            agent_response = AgentResponse(
                assistant_reply=result["assistant_reply"],
                order_state=OrderState(**result["order_state"]),
                action=AgentAction(result["action"]),
                mode="online"
            )

            return agent_response

        except Exception as e:
            logger.error(f"❌ All LLM backend calls failed: {type(e).__name__}: {e}", exc_info=True)
            logger.warning("LLM call failed, switching to offline mode: %s", e)
            return self._offline_response(
                user_text=user_text,
                current_order_state=current_order_state,
                reason=f"LLM call failed: {str(e)}"
            )

    async def _handle_tool_calls(
        self,
        messages: List[Dict[str, Any]],
        tool_calls: Any,
        current_order_state: OrderState,
        primary_backend: Optional[LLMBackend] = None
    ) -> AgentResponse:
        """Execute tool calls and get final response"""
        # Add assistant's tool call message
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

        # Execute each tool call
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            logger.info(f"Calling tool: {function_name}, arguments: {function_args}")

            # Execute tool
            result = await self._execute_tool(function_name, function_args)

            # Add tool result to message history
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": json.dumps(result, ensure_ascii=False)
            })

        # Let LLM generate final response based on tool results (wrap tool data in natural language)
        # Add explicit instructions to require standard JSON format
        messages.append({
            "role": "system",
            "content": """Based on the data returned by the tool, respond to the customer in natural language.

Tool returned data may contain:
- **Success case**: Order progress information (current_stage_label, eta_seconds, etc.) and order details (drink_name, size, sugar, ice, toppings)
- **Failure case**: Error message (error field), e.g., {"error": "Order #52 does not exist"}

**Important handling rules**:
1. If tool return contains "error" field, order doesn't exist, politely tell customer the order doesn't exist
2. If tool return succeeds, when customer asks "what is this order", "order content", "what is it", you must extract from tool data and tell customer the specific order content (drink name, specs, add-ons)
3. If customer just asks about progress, concisely answer progress and estimated completion time

Must return JSON format:
{
    "assistant_reply": "Describe tool returned information in natural language (if error, tell customer order doesn't exist; if success, include order progress and order details)",
    "order_state": Current order state (update if customer is ordering, otherwise keep original state),
    "action": "ask_more" (default use ask_more when querying progress)
}"""
        })

        logger.info(f"Calling LLM to generate final response after tool call, message count: {len(messages)}")

        final_response, provider = await self.llm_router.call_with_fallback(
            messages=messages,
            temperature=config.OPENAI_TEMPERATURE,
            response_format={"type": "json_object"},
            primary=primary_backend
        )

        logger.info(f"✅ LLM response after tool call successful, using backend: {provider.name}")
        final_content = final_response.choices[0].message.content
        if not final_content:
            raise ValueError("LLM returned empty content after tool call")

        # Use enhanced JSON extraction logic
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
            logger.error(f"JSON parsing failed after tool call. Original content: {final_content[:500]}")
            raise ValueError(f"JSON parsing failed after tool call: {e}")

        return AgentResponse(
            assistant_reply=result["assistant_reply"],
            order_state=OrderState(**result.get("order_state", current_order_state.model_dump())),
            action=AgentAction(result.get("action", "ask_more")),
            mode="online"
        )

    async def _execute_tool(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute specific tool"""
        from fastapi.encoders import jsonable_encoder

        if function_name == "get_order_status":
            order_id = arguments["order_id"]
            order = db.get_order(order_id)
            if not order:
                return {"error": f"Order #{order_id} does not exist"}
            progress = build_order_progress(order)
            return jsonable_encoder(progress)

        elif function_name == "get_all_orders_queue":
            orders = db.get_recent_orders(50)
            snapshot = build_queue_snapshot(orders)
            return jsonable_encoder(snapshot)

        else:
            return {"error": f"Unknown tool: {function_name}"}

    def _offline_response(
        self,
        user_text: str,
        current_order_state: OrderState,
        reason: Optional[str] = None
    ) -> AgentResponse:
        """
        Fallback strategy when LLM is unavailable
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

        # Update completion status
        required_fields = ["drink_name", "size", "sugar", "ice"]
        state.is_complete = all(getattr(state, field) for field in required_fields)

        confirm_keywords = ["confirm", "yes", "okay", "sure", "order", "that's it", "good", "done"]
        action = AgentAction.ASK_MORE
        reply_body: str

        missing_field = next((field for field in required_fields if not getattr(state, field)), None)

        if missing_field:
            reply_body = self._build_missing_field_prompt(missing_field, state)
        elif state.is_complete and any(keyword in normalized_text for keyword in confirm_keywords):
            action = AgentAction.SAVE_ORDER
            reply_body = f"Confirmed: {self._build_order_summary(state)}. Please wait a moment, we'll prepare it right away."
        elif state.is_complete:
            action = AgentAction.CONFIRM
            reply_body = f"{self._build_order_summary(state)}. Please confirm or let me know if you need any adjustments."
        else:
            reply_body = "I need more information. Please tell me the drink, size, sweetness, and ice level you'd like."

        notice = "[Offline Mode] "
        if reason:
            notice += f"{reason}. "
            logger.warning("Offline mode triggered, reason: %s", reason)

        return AgentResponse(
            assistant_reply=f"{notice}{reply_body}",
            order_state=state,
            action=action,
            mode="offline"
        )

    def _match_option(self, text: str, options: List[str]) -> Optional[str]:
        """Match predefined options based on text"""
        for option in options:
            if option in text:
                return option
        return None

    def _build_missing_field_prompt(self, field: str, state: OrderState) -> str:
        """Build prompt based on missing field"""
        menu_names = ", ".join(item.name for item in TEA_MENU)
        if field == "drink_name":
            return f"Please tell me which drink you'd like. You can choose from: {menu_names}."
        if field == "size":
            drink = state.drink_name or "this drink"
            return f"Got it, {drink}. Please tell me the size ({', '.join(SIZE_OPTIONS)})."
        if field == "sugar":
            return f"Size noted. Please choose sweetness level ({', '.join(SUGAR_OPTIONS)})."
        if field == "ice":
            return f"Great! Now tell me your ice preference ({', '.join(ICE_OPTIONS)})."
        return "Please continue to complete the order information."

    def _build_order_summary(self, state: OrderState) -> str:
        """Build order summary"""
        parts = []
        if state.size and state.drink_name:
            parts.append(f"{state.size} {state.drink_name}")
        elif state.drink_name:
            parts.append(state.drink_name)
        if state.sugar:
            parts.append(state.sugar)
        if state.ice:
            parts.append(state.ice)
        if state.toppings:
            parts.append(f"add-ons: {', '.join(state.toppings)}")
        return ", ".join(parts)


# Global Agent instance
tea_agent = TeaOrderAgent()
