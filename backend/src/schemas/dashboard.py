from typing import Optional
from pydantic import BaseModel, ConfigDict


class PeriodData(BaseModel):
    model_config = ConfigDict(extra='ignore')
    from_date: str
    to_date: str


class CallsData(BaseModel):
    model_config = ConfigDict(extra='ignore')
    total: int
    booked: int
    cancelled: int
    transferred: int
    faq_answered: int
    no_action: int
    vs_yesterday_pct: float
    inbound_handled: Optional[int] = 0
    inbound_total: Optional[int] = 0
    outbound_total: Optional[int] = 0
    outbound_confirmed: Optional[int] = 0


class AppointmentsData(BaseModel):
    model_config = ConfigDict(extra='ignore')
    total_today: int
    scheduled: int
    confirmed: int
    completed: int
    cancelled: int
    ai_booked_today: Optional[int] = 0
    staff_booked_today: Optional[int] = 0


class PriorAuthData(BaseModel):
    model_config = ConfigDict(extra='ignore')
    approved: int = 0
    pending: int = 0
    total: int = 0


class RevenueData(BaseModel):
    model_config = ConfigDict(extra='ignore')
    amount_cents: int
    currency: str
    appointment_count: int
    avg_value_cents: int


class StatsData(BaseModel):
    model_config = ConfigDict(extra='ignore')
    period: PeriodData
    calls: CallsData
    appointments: AppointmentsData
    revenue_recovered: RevenueData
    prior_auths: Optional[PriorAuthData] = None
    estimated_hours_saved: Optional[float] = 0.0
    ai_performance_rate: float
    no_show_rate_month: float


class StatsResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')
    success: bool
    data: StatsData
