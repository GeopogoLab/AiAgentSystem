"""数据模型定义"""
from __future__ import annotations
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


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

class ProductionStage(str, Enum):
    """制作阶段"""
    QUEUED = "queued"
    BREWING = "brewing"
    SEALING = "sealing"
    READY = "ready"

class OrderState(BaseModel):
    """订单状态（草稿）"""
    drink_name: Optional[str] = None
    size: Optional[str] = None  # small, medium, large
    sugar: Optional[str] = None  # 0%, 30%, 50%, 70%, 100%
    ice: Optional[str] = None  # no_ice, less, normal, extra
    toppings: List[str] = Field(default_factory=list)  # 加料列表
    notes: Optional[str] = None  # 备注
    is_complete: bool = False  # 是否信息完整


class SessionState(BaseModel):
    """会话状态"""
    session_id: str
    history: List["ConversationMessage"] = Field(default_factory=list)
    order_state: OrderState = Field(default_factory=OrderState)
    status: OrderStatus = OrderStatus.COLLECTING
    last_order_id: Optional[int] = None
    last_order_total: Optional[float] = None
    order_history: List[int] = Field(default_factory=list)  # 订单ID历史列表


class TalkRequest(BaseModel):
    """语音对话请求"""
    session_id: str


class TalkResponse(BaseModel):
    """语音对话响应"""
    assistant_reply: str
    order_state: OrderState
    order_status: OrderStatus
    order_id: Optional[int] = None  # 订单保存后返回 ID
    reply_mode: str = "online"
    order_total: Optional[float] = None


class AgentResponse(BaseModel):
    """Agent 响应"""
    assistant_reply: str
    order_state: OrderState
    action: AgentAction
    mode: str = "online"


class ConversationMessage(BaseModel):
    """通用对话消息"""
    role: str
    content: str
    mode: str = "online"

class ProductionTimelineItem(BaseModel):
    """制作流程节点"""
    stage: ProductionStage
    label: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None

class OrderProgressResponse(BaseModel):
    """订单制作进度"""
    order_id: int
    current_stage: ProductionStage
    current_stage_label: str
    eta_seconds: Optional[int] = None
    total_duration_seconds: int
    is_completed: bool
    timeline: List[ProductionTimelineItem]
    queue_position: Optional[int] = None
    total_orders: Optional[int] = None
    # 订单详情
    drink_name: Optional[str] = None
    size: Optional[str] = None
    sugar: Optional[str] = None
    ice: Optional[str] = None
    toppings: List[str] = Field(default_factory=list)


class ProductionQueueSnapshot(BaseModel):
    """制作排队快照"""
    generated_at: datetime
    active_orders: List[OrderProgressResponse]
    completed_orders: List[OrderProgressResponse]

class TTSRequest(BaseModel):
    """文本转语音请求"""
    text: str
    voice: Optional[str] = None


class TTSResponse(BaseModel):
    """文本转语音响应"""
    audio_url: Optional[str] = None
    audio_base64: Optional[str] = None
    voice: str
    format: str = "mp3"

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
