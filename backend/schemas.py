from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
import models

# --- AUTH ---
class UserCreate(BaseModel):
    username: str
    full_name: str
    email: str
    password: str
    role: str = "recepcionista"
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    tenant_id: Optional[int] = None
    class Config: from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    tenant_id: Optional[int] = None

# --- TENANTS & SIGNUP ---
class TenantBase(BaseModel):
    name: str
    subdomain: Optional[str] = None
    cnpj: Optional[str] = None
    address: Optional[str] = None

class TenantCreate(TenantBase):
    pass

class TenantResponse(TenantBase):
    id: int
    is_active: bool
    created_at: datetime
    class Config: from_attributes = True

class TenantPublicResponse(BaseModel):
    name: str
    cnpj: Optional[str] = None
    address: Optional[str] = None
    class Config: from_attributes = True

class SignupRequest(BaseModel):
    pousada_name: str
    admin_username: str
    admin_full_name: str
    admin_email: str
    admin_password: str

class SignupResponse(BaseModel):
    user: UserResponse
    payment_url: Optional[str] = None
    tenant_id: int

class FieldValidationRequest(BaseModel):
    field: str # 'username' or 'email'
    value: str

class FieldValidationResponse(BaseModel):
    available: bool
    message: Optional[str] = None

# --- ROOMS ---
class RoomBase(BaseModel):
    id: str # O ID agora é o número do quarto (ex: "101")
    type: str
    price_per_night: float
    floor: Optional[int] = 1
    max_capacity: int = 2 # <--- NOVO
    description: Optional[str] = None


class RoomCreate(RoomBase): pass

class RoomUpdate(BaseModel):
    id: Optional[str] = None
    type: Optional[str] = None
    price_per_night: Optional[float] = None
    floor: Optional[int] = None
    max_capacity: Optional[int] = None
    description: Optional[str] = None


class RoomResponse(RoomBase):
    status: models.RoomStatus
    maintenance_note: str | None = None
    class Config: from_attributes = True

# --- GUESTS (COMPLETO DA DOC) ---
class GuestBase(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    document: str
    birth_date: Optional[date] = None
    profession: Optional[str] = None
    address_zip: Optional[str] = None
    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_neighborhood: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None

class GuestCreate(GuestBase): pass

class GuestPublicCreate(GuestBase):
    tenant_id: int # Recebido via URL pública
    session_id: Optional[str] = None # ID da sessão de chat para o webhook de reconhecimento

class GuestUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    document: Optional[str] = None
    birth_date: Optional[date] = None
    profession: Optional[str] = None
    address_zip: Optional[str] = None
    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_neighborhood: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None

class GuestResponse(GuestBase):
    id: int
    age: Optional[int] = None
    class Config: from_attributes = True

# --- PRODUCTS ---
class ProductBase(BaseModel):
    name: str
    price: float
    category: str
    barcode: Optional[str] = None
    unit_measure: str = "UN"
    stock_quantity: int
    min_stock: int = 5
    max_stock: Optional[int] = None
    cost_price: float = 0.0
    markup_percent: float = 0.0
    supplier: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    is_quick_access: bool = False

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int
    class Config: from_attributes = True

class ProductCategoryCreate(BaseModel):
    name: str

class ProductCategoryResponse(BaseModel):
    id: int
    name: str
    class Config: from_attributes = True
 
class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    barcode: Optional[str] = None
    unit_measure: Optional[str] = None
    stock_quantity: Optional[int] = None
    min_stock: Optional[int] = None
    max_stock: Optional[int] = None
    supplier: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_quick_access: Optional[bool] = None
    cost_price: Optional[float] = None
    markup_percent: Optional[float] = None

class StockDashboard(BaseModel):
    total_products: int
    total_value: float # Preço de Venda
    total_cost_value: float # Preço de Custo
    potential_profit: float # Lucro Potencial
    low_stock_count: int
    low_stock_items: List[ProductResponse]

class QuickAccessUpdateRequest(BaseModel):
    product_ids: List[int]
 
class StockEntryItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: float | None = None
    class Config: from_attributes = True
 
class StockEntryResponse(BaseModel):
    id: int
    supplier: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    note: str | None = None
    created_at: datetime
    items: List[StockEntryItemResponse]
    class Config: from_attributes = True

# --- BOOKINGS & CONSUMPTION ---
class CompanionCreate(BaseModel):
    name: str
    age: int

class CompanionResponse(BaseModel):
    id: int
    name: str
    age: int
    class Config: from_attributes = True

class BookingCreate(BaseModel):
    guest_id: int
    room_id: Optional[str] = None # Pode virar null se for reserva online sem quarto definido
    check_in_date: datetime
    check_out_date: datetime
    check_in_time: Optional[str] = "14:00"
    check_out_time: Optional[str] = "14:00"
    mode: models.BookingMode
    total_guests: int
    daily_rate: float
    notes: Optional[str] = None
    companions: List[CompanionCreate] = []

class BookingUpdate(BaseModel):
    room_id: Optional[str] = None
    guest_id: Optional[int] = None
    check_in_date: Optional[datetime] = None
    check_out_date: Optional[datetime] = None
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    mode: Optional[models.BookingMode] = None
    total_guests: Optional[int] = None
    daily_rate: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[models.BookingStatus] = None
    payment_status: Optional[models.PaymentStatus] = None
    deposit_amount: Optional[float] = None
    total_amount: Optional[float] = None
    companions: Optional[List[CompanionCreate]] = None


class CheckInRequest(BaseModel):
    booking_id: int # Agora fazemos check-in de uma RESERVA existente
    room_id: str    # Confirmamos qual quarto vai usar

class CheckoutPaymentRequest(BaseModel):
    payment_method: models.PaymentMethod
    discount: float = 0.0

class ConsumptionRequest(BaseModel):
    room_id: str
    product_id: int
    quantity: int

class ConsumptionResponse(BaseModel):
    product_name: str
    quantity: int
    unit_price: float
    total: float

class BookingResponse(BaseModel):
    id: int
    room_id: Optional[str] = None
    room_number: Optional[str] = None
    guest_id: int
    guest_name: str
    guest_age: Optional[int] = None
    mode: models.BookingMode
    daily_rate: Optional[float] = None
    status: models.BookingStatus
    total_guests: int
    total_amount: Optional[float] = None
    deposit_amount: Optional[float] = None
    payment_status: models.PaymentStatus
    check_in_date: datetime
    check_out_date: datetime
    check_in_time: Optional[str] = "14:00"
    check_out_time: Optional[str] = "14:00"
    notes: Optional[str] = None
    payment_receipt_url: Optional[str] = None
    companions: List[CompanionResponse] = []
    
    class Config: from_attributes = True
 
class BookingPublicCreate(BaseModel):
    tenant_id: int
    guest: GuestCreate
    room_id: Optional[str] = None
    check_in_date: datetime
    check_out_date: datetime
    check_in_time: Optional[str] = "14:00"
    check_out_time: Optional[str] = "14:00"
    mode: models.BookingMode
    total_guests: int
    daily_rate: float
    notes: Optional[str] = None
    companions: List[CompanionCreate] = []
 
class RescheduleRequest(BaseModel):
    booking_id: int
    room_id: Optional[str] = None
    check_in_date: datetime
    check_out_date: datetime
# --- FINANCEIRO ---
class RevenueCreate(BaseModel):
    description: str
    amount: float
    category: models.RevenueCategory
    payment_method: models.PaymentMethod
    booking_id: Optional[int] = None

class RevenueResponse(RevenueCreate):
    id: int
    created_at: datetime
    class Config: from_attributes = True
 
class RevenueUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[models.RevenueCategory] = None
    payment_method: Optional[models.PaymentMethod] = None
    booking_id: Optional[int] = None

# --- BUSINESS RULES ---
class BusinessRuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    rule_type: str
    config: dict
    is_active: bool = True

class BusinessRuleCreate(BusinessRuleBase):
    pass

class BusinessRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[str] = None
    config: Optional[dict] = None
    is_active: Optional[bool] = None

class BusinessRuleResponse(BusinessRuleBase):
    id: int
    created_at: datetime
    class Config: from_attributes = True

# --- DESPESAS (CONTAS A PAGAR) ---
class ExpenseCreate(BaseModel):
    description: str
    amount: float
    category: models.ExpenseCategory
    due_date: Optional[date] = None
    notes: Optional[str] = None

class ExpenseUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[models.ExpenseCategory] = None
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    is_paid: Optional[bool] = None
    payment_method: Optional[models.PaymentMethod] = None
    notes: Optional[str] = None

class ExpenseResponse(BaseModel):
    id: int
    description: str
    amount: float
    category: models.ExpenseCategory
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    is_paid: bool
    payment_method: Optional[models.PaymentMethod] = None
    notes: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None
    tenant_id: Optional[int] = None
    class Config: from_attributes = True

# --- PDV & COMANDAS ---
class CaixaSessionBase(BaseModel):
    opening_balance: float = 0.0

class CaixaSessionCreate(CaixaSessionBase):
    pass

class CaixaSessionResponse(CaixaSessionBase):
    id: int
    user_id: int
    status: models.CaixaStatus
    opened_at: datetime
    closed_at: Optional[datetime] = None
    closing_balance: Optional[float] = None
    summary_json: Optional[dict] = None
    user_full_name: Optional[str] = None
    class Config: from_attributes = True

class CaixaMovementCreate(BaseModel):
    type: models.CaixaMovementType
    amount: float
    description: Optional[str] = None

class CaixaMovementResponse(CaixaMovementCreate):
    id: int
    session_id: int
    created_at: datetime
    class Config: from_attributes = True

class ComandaItemBase(BaseModel):
    product_id: Optional[int] = None
    quantity: float = 1.0
    unit_price: float
    description: Optional[str] = None
    type: models.ComandaItemType = models.ComandaItemType.PRODUTO

class ComandaItemCreate(ComandaItemBase):
    pass

class ComandaItemUpdate(BaseModel):
    quantity: float

class ComandaItemResponse(ComandaItemBase):
    id: int
    comanda_id: int
    created_at: datetime
    class Config: from_attributes = True

class ComandaBase(BaseModel):
    identificador: str
    booking_id: Optional[int] = None

class ComandaCreate(ComandaBase):
    pass

class ComandaResponse(ComandaBase):
    id: int
    status: models.ComandaStatus
    total: float
    created_at: datetime
    updated_at: datetime
    items: List[ComandaItemResponse] = []
    class Config: from_attributes = True

class CloseComandaRequest(BaseModel):
    payment_method: Optional[models.PaymentMethod] = None
    lancada_no_quarto: bool = False # Se True, vincula ao booking_id da comanda
    booking_id: Optional[int] = None # Vínculo opcional no checkout
    discount: float = 0.0

class BatchCloseComandaRequest(BaseModel):
    comanda_ids: List[int]
    payment_method: Optional[models.PaymentMethod] = None
    lancada_no_quarto: bool = False
    booking_id: Optional[int] = None # Vínculo opcional no checkout
    discount: float = 0.0

class CaixaSummaryResponse(BaseModel):
    opening_balance: float
    vendas_dinheiro: float
    vendas_pix: float
    vendas_debito: float
    vendas_credito: float
    entradas_total: float
    retiradas_total: float
    saldo_dinheiro: float
    saldo_geral: float
    comandas_processadas: int
    movements: List[CaixaMovementResponse] = []
    class Config: from_attributes = True

# --- HISTÓRICO PDV ---
class PDVSaleItemResponse(BaseModel):
    id: int
    product_name: str
    quantity: float
    unit_price: float
    total_item: float
    class Config: from_attributes = True

class PDVSaleResponse(BaseModel):
    id: int
    comanda_identificador: str
    total_amount: float
    discount: float
    payment_method: Optional[models.PaymentMethod] = None
    user_id: int
    session_id: Optional[int] = None
    created_at: datetime
    items: List[PDVSaleItemResponse] = []
    class Config: from_attributes = True

