"""数据模型定义"""
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class OrderStatus(str, Enum):
    """订单状态枚举"""
    COLLECTING = "collecting"  # 正在收集信息
    CONFIRMING = "confirming"  # 等待用户确认
    SAVED = "saved"  # 已保存到数据库


class AgentAction(str, Enum):
    """Agent 动作枚举"""
    NONE = "none"
    ASK_MORE = "ask_more"  # 继续询问
    CONFIRM = "confirm"  # 复述订单等待确认
    SAVE_ORDER = "save_order"  # 保存订单


class OrderState(BaseModel):
    """订单状态（草稿）"""
    drink_name: Optional[str] = None
    size: Optional[str] = None  # small, medium, large
    sugar: Optional[str] = None  # 0%, 30%, 50%, 70%, 100%
    ice: Optional[str] = None  # no_ice, less, normal, extra
    toppings: List[str] = []  # 加料列表: boba, pudding, grass_jelly 等
    notes: Optional[str] = None  # 备注
    is_complete: bool = False  # 是否信息完整


class SessionState(BaseModel):
    """会话状态"""
    session_id: str
    history: List[dict] = []  # 对话历史 [{"role": "user/assistant", "content": "..."}]
    order_state: OrderState = OrderState()
    status: OrderStatus = OrderStatus.COLLECTING


class TalkRequest(BaseModel):
    """语音对话请求"""
    session_id: str


class TalkResponse(BaseModel):
    """语音对话响应"""
    assistant_reply: str
    order_state: OrderState
    order_status: OrderStatus
    order_id: Optional[int] = None  # 订单保存后返回 ID


class AgentResponse(BaseModel):
    """Agent 响应"""
    assistant_reply: str
    order_state: OrderState
    action: AgentAction


class Menu(BaseModel):
    """菜单项"""
    name: str
    category: str
    description: Optional[str] = None
    base_price: float


# 奶茶菜单数据
TEA_MENU = [
    Menu(name="乌龙奶茶", category="奶茶", description="经典乌龙茶配奶", base_price=15.0),
    Menu(name="茉莉奶绿", category="奶茶", description="清新茉莉绿茶", base_price=15.0),
    Menu(name="红茶拿铁", category="奶茶", description="浓郁红茶奶", base_price=16.0),
    Menu(name="抹茶拿铁", category="抹茶", description="日式抹茶", base_price=18.0),
    Menu(name="黑糖珍珠奶茶", category="奶茶", description="黑糖风味珍珠", base_price=18.0),
    Menu(name="芝士奶盖", category="奶盖", description="浓香芝士", base_price=20.0),
]

# 配置选项
SIZE_OPTIONS = ["小杯", "中杯", "大杯"]
SUGAR_OPTIONS = ["无糖", "三分糖", "五分糖", "七分糖", "全糖"]
ICE_OPTIONS = ["去冰", "少冰", "正常冰", "多冰"]
TOPPING_OPTIONS = ["珍珠", "布丁", "仙草", "椰果", "芋圆"]
