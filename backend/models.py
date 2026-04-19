from sqlalchemy import Column, Integer, String, Float, Boolean, Enum, ForeignKey, DateTime, Text, Date, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime
from sqlalchemy.orm import declared_attr

class TenantMixin:
    """Mixin para adicionar tenant_id em todas as tabelas de negócio"""
    @declared_attr
    def tenant_id(cls):
        return Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

# --- ENUMS ---
class RoomStatus(str, enum.Enum):
    DISPONIVEL = "disponivel"
    OCUPADO = "ocupado"
    LIMPEZA = "limpeza"
    MANUTENCAO = "manutencao"

class BookingStatus(str, enum.Enum):
    PENDENTE = "pendente"    
    CONFIRMADO = "confirmado" 
    ATIVO = "ativo"          
    CONCLUIDO = "concluido"  
    CANCELADO = "cancelado"

class BookingMode(str, enum.Enum):
    NORMAL = "normal"      
    CARAVANA = "caravana"  

class PaymentMethod(str, enum.Enum):
    PIX = "pix"
    CREDITO = "credito"
    DEBITO = "debito"
    DINHEIRO = "dinheiro"

class PaymentStatus(str, enum.Enum):
    PENDENTE = "pending"
    PARCIAL = "partial"
    PAGO = "paid"
    CANCELADO = "cancelled"

class RevenueCategory(str, enum.Enum):
    HOSPEDAGEM = "hospedagem"
    CONSUMO = "consumo"
    OUTROS = "outros"

class ExpenseCategory(str, enum.Enum):
    AGUA = "agua"
    ENERGIA = "energia"
    INTERNET = "internet"
    MANUTENCAO = "manutencao"
    FORNECEDOR = "fornecedor"
    SALARIOS = "salarios"
    LIMPEZA = "limpeza"
    ALIMENTACAO = "alimentacao"
    MARKETING = "marketing"
    IMPOSTOS = "impostos"
    ALUGUEL = "aluguel"
    OUTROS = "outros"

class ComandaStatus(str, enum.Enum):
    ABERTA = "aberta"
    PAGA = "paga"
    CANCELADA = "cancelada"
    LANCADA_NO_QUARTO = "lancada_no_quarto"

class CaixaStatus(str, enum.Enum):
    ABERTO = "aberto"
    FECHADO = "fechado"

class CaixaMovementType(str, enum.Enum):
    SUPRIMENTO = "suprimento"
    SANGRIA = "sangria"
    VENDA = "venda"
    RETIRADA = "retirada"

class ComandaItemType(str, enum.Enum):
    PRODUTO = "produto"
    PESO = "peso"
    MARMITEX = "marmitex"

# --- TABELAS ---

class Tenant(Base):
    """Gerenciamento de Organizações (Clientes)"""
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    subdomain = Column(String, unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

    users = relationship("User", back_populates="tenant")
    configs = relationship("TenantConfig", back_populates="tenant")

class TenantConfig(Base):
    """Configurações Sensíveis por Tenant (ex: Mercado Pago)"""
    __tablename__ = "tenant_configs"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True)
    
    # Mercado Pago - Tokens Criptografados
    mp_access_token = Column(String, nullable=True) # Valor Criptografado
    mp_public_key = Column(String, nullable=True)
    
    # Chave PIX Manual para Fallback e Agent Chat
    manual_pix_key = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    tenant = relationship("Tenant", back_populates="configs")

class User(Base):
    """Usuários do Sistema (Login)"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True) # Utilizado para o Login
    full_name = Column(String, nullable=True) # Nome completo do funcionário
    email = Column(String, unique=True, index=True, nullable=True) # E-mail corporativo válido
    password_hash = Column(String)
    role = Column(String, default="recepcionista")
    
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    tenant = relationship("Tenant", back_populates="users")

class Room(Base, TenantMixin):
    __tablename__ = "rooms"
    id = Column(String, primary_key=True, index=True) # Agora o ID É o número do quarto (ex: "101")
    type = Column(String) 
    price_per_night = Column(Float)
    status = Column(Enum(RoomStatus), default=RoomStatus.DISPONIVEL)
    floor = Column(Integer, default=1)
    description = Column(Text, nullable=True) # Características do quarto para o Agente
    
    # --- NOVO CAMPO ---
    max_capacity = Column(Integer, default=2) # Ex: 2 pessoas
    maintenance_note = Column(Text, nullable=True)
    
    bookings = relationship("Booking", back_populates="room")
    booking_associations = relationship("BookingRoom", back_populates="room")


class Guest(Base, TenantMixin):
    """Cadastro Completo do Hóspede Principal"""
    __tablename__ = "guests"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True) 
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, nullable=True) 
    document = Column(String, unique=True, index=True, nullable=True) 
    birth_date = Column(Date, nullable=True) 
    profession = Column(String, nullable=True)
    address_zip = Column(String, nullable=True) 
    address_street = Column(String, nullable=True) 
    address_number = Column(String, nullable=True)
    address_neighborhood = Column(String, nullable=True) 
    address_city = Column(String, nullable=True)
    address_state = Column(String, nullable=True) 
    notes = Column(Text, nullable=True)
    bookings = relationship("Booking", back_populates="guest")

    @property
    def age(self):
        if not self.birth_date:
            return None
        from datetime import date
        today = date.today()
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))

class Product(Base, TenantMixin):
    """Cadastro de Produtos Rico"""
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Float)
    category = Column(String) 
    barcode = Column(String, unique=True, index=True, nullable=True)
    unit_measure = Column(String, default="UN") 
    stock_quantity = Column(Integer, default=0)
    min_stock = Column(Integer, default=5) 
    max_stock = Column(Integer, nullable=True)
    cost_price = Column(Float, default=0.0)
    markup_percent = Column(Float, default=0.0)
    supplier = Column(String, nullable=True) 
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    is_quick_access = Column(Boolean, default=False)

class ProductCategory(Base, TenantMixin):
    """Categorias Customizadas de Produtos"""
    __tablename__ = "product_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    # tenant_id vem do TenantMixin

class Booking(Base, TenantMixin):
    """Reserva Detalhada"""
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=True) 
    guest_id = Column(Integer, ForeignKey("guests.id"))
    check_in_date = Column(DateTime) 
    check_out_date = Column(DateTime) 
    real_check_in = Column(DateTime, nullable=True) 
    real_check_out = Column(DateTime, nullable=True) 
    check_in_time = Column(String, default="14:00") 
    check_out_time = Column(String, default="14:00") 
    mode = Column(Enum(BookingMode), default=BookingMode.NORMAL)
    total_guests = Column(Integer, default=1) 
    notes = Column(Text, nullable=True) 
    daily_rate = Column(Float) 
    total_amount = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    deposit_amount = Column(Float, default=0.0)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDENTE)
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDENTE)
    payment_receipt_url = Column(String, nullable=True) # Novo: URL para o arquivo do comprovante
    room = relationship("Room", back_populates="bookings")
    guest = relationship("Guest", back_populates="bookings")
    consumptions = relationship("Consumption", back_populates="booking")
    companions = relationship("Companion", back_populates="booking")
    # Relacionamento com Revenue (opcional, se quiser linkar pagamentos)
    revenues = relationship("Revenue", back_populates="booking")
    
    # NOVAS ASSOCIAÇÕES (Suporte a Multi-Quartos)
    room_associations = relationship("BookingRoom", back_populates="booking", cascade="all, delete-orphan")

class BookingRoom(Base, TenantMixin):
    """Associação de Quartos a uma Reserva (Múltiplos Quartos por Reserva)"""
    __tablename__ = "booking_rooms"
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    
    booking = relationship("Booking", back_populates="room_associations")
    room = relationship("Room", back_populates="booking_associations")

class Companion(Base, TenantMixin):
    """Acompanhantes"""
    __tablename__ = "companions"
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    name = Column(String)
    age = Column(Integer)
    booking = relationship("Booking", back_populates="companions")

class Consumption(Base, TenantMixin):
    __tablename__ = "consumptions"
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    unit_price = Column(Float)
    description = Column(String, nullable=True) # Nome amigável para itens manuais
    created_at = Column(DateTime, default=datetime.now)
    booking = relationship("Booking", back_populates="consumptions")
    product = relationship("Product")

class Revenue(Base, TenantMixin):
    """Tabela Financeira - O Livro Caixa"""
    __tablename__ = "revenues"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)
    amount = Column(Float)
    discount = Column(Float, default=0.0)
    category = Column(Enum(RevenueCategory))
    payment_method = Column(Enum(PaymentMethod))
    created_at = Column(DateTime, default=datetime.now)
    
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    booking = relationship("Booking", back_populates="revenues")
    created_by_user = Column(String, nullable=True) 
# ... (Mantenha todo o resto igual) ...

class BusinessRule(Base, TenantMixin):
    """Regras de Negócio Dinâmicas (Preços diferenciados, Restrições, etc.)"""
    __tablename__ = "business_rules"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    rule_type = Column(String) # 'price_modifier', 'booking_restriction', etc.
    config = Column(JSON) # Parametros da regra
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

class ChatMessage(Base, TenantMixin):
    """Persistência de mensagens do Chat IA"""
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True) # ID da sessão (UUID) vindo do Front
    role = Column(String)                   # 'user' ou 'assistant'
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    
class StockEntry(Base, TenantMixin):
    """Entrada de Estoque (Nota Fiscal)"""
    __tablename__ = "stock_entries"
    id = Column(Integer, primary_key=True, index=True)
    supplier = Column(String, nullable=True)
    invoice_number = Column(String, nullable=True, index=True)
    invoice_date = Column(Date, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    items = relationship("StockEntryItem", back_populates="entry", cascade="all, delete-orphan")

class StockEntryItem(Base, TenantMixin):
    __tablename__ = "stock_entry_items"
    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, ForeignKey("stock_entries.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=0)
    unit_price = Column(Float, nullable=True)
    entry = relationship("StockEntry", back_populates="items")
    product = relationship("Product")

class SystemSetting(Base, TenantMixin):
    """
    Configurações Globais do Sistema
    Ex: {"key": "checkout_time", "value": "12:00"}
    Ex: {"key": "child_price_percentage", "value": "0.5"}
    """
    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint('key', 'tenant_id', name='uq_settings_key_tenant'),
    )

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, index=True)   # A chave única da config POR TENANT
    value = Column(String)                          # O valor (sempre string, converte no uso)
    description = Column(String, nullable=True)     # Para o Admin saber o que é


class Event(Base, TenantMixin):
    """Calendário de Eventos da Região (Canção Nova, etc.)"""
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    start_date = Column(Date)
    end_date = Column(Date)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    daily_rate = Column(Float, default=0.0) # Fallback/Geral
    daily_rate_single = Column(Float, default=0.0)
    daily_rate_couple = Column(Float, default=0.0)
    daily_rate_extra = Column(Float, default=0.0)
    daily_rate_child = Column(Float, default=0.0)
    color = Column(String, default="#6366f1")  # Cor do card no calendário
    created_at = Column(DateTime, default=datetime.now)

class TenantMemory(Base):
    __tablename__ = "tenant_memories"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True)
    guest_id = Column(Integer, ForeignKey("guests.id"), nullable=True)
    
    category = Column(String, default="geral") # 'preferencia', 'regra_negocio', 'logistica'
    content = Column(String, nullable=False)
    importance = Column(Integer, default=1) # 1 a 5
    
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    guest = relationship("Guest")

class Expense(Base, TenantMixin):
    """Contas a Pagar / Despesas Operacionais"""
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    # Usamos values_callable para garantir que o SQLAlchemy envie o valor do enum (minúsculo) e não o nome do membro (MAIÚSCULO)
    category = Column(Enum(ExpenseCategory, values_callable=lambda x: [e.value for e in x]), nullable=False, default=ExpenseCategory.OUTROS)
    due_date = Column(Date, nullable=True)          # Data de vencimento
    paid_date = Column(Date, nullable=True)          # Data efetiva de pagamento
    is_paid = Column(Boolean, default=False)
    payment_method = Column(Enum(PaymentMethod), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(String, nullable=True)       # username do funcionário

class SessionState(Base, TenantMixin):
    """Estado persistente das sessões dos agentes de IA (LangGraph State)"""
    __tablename__ = 'session_state'
    
    session_id = Column(String(255), primary_key=True)
    current_state = Column(String(50), default='DISCOVERY')
    context_json = Column(Text, default='{}') # Armazena o Pydantic model serializado
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# --- NOVAS TABELAS PDV ---

class CaixaSession(Base, TenantMixin):
    """Sessão de Caixa (Turno) por Usuário"""
    __tablename__ = "caixa_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    opening_balance = Column(Float, default=0.0)
    closing_balance = Column(Float, nullable=True)
    status = Column(Enum(CaixaStatus), default=CaixaStatus.ABERTO)
    opened_at = Column(DateTime, default=datetime.now)
    closed_at = Column(DateTime, nullable=True)
    summary_json = Column(JSON, nullable=True)
    
    user = relationship("User")
    movements = relationship("CaixaMovement", back_populates="session")
    comandas = relationship("Comanda", back_populates="session")

class CaixaMovement(Base, TenantMixin):
    """Movimentações de Dinheiro no Caixa (Suprimento, Sangria, etc.)"""
    __tablename__ = "caixa_movements"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("caixa_sessions.id"))
    type = Column(Enum(CaixaMovementType))
    amount = Column(Float)
    description = Column(String, nullable=True)
    payment_method = Column(Enum(PaymentMethod), nullable=True) # Pix, Dinheiro, etc.
    created_at = Column(DateTime, default=datetime.now)
    
    session = relationship("CaixaSession", back_populates="movements")

class Comanda(Base, TenantMixin):
    """Comanda de Pedidos (PDV)"""
    __tablename__ = "comandas"
    id = Column(Integer, primary_key=True, index=True)
    identificador = Column(String, index=True) # Ex: "Mesa 10", "Balcão", etc.
    status = Column(Enum(ComandaStatus), default=ComandaStatus.ABERTA)
    total = Column(Float, default=0.0)
    
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    session_id = Column(Integer, ForeignKey("caixa_sessions.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    booking = relationship("Booking")
    session = relationship("CaixaSession", back_populates="comandas")
    items = relationship("ComandaItem", back_populates="comanda", cascade="all, delete-orphan")

class ComandaItem(Base, TenantMixin):
    """Itens da Comanda"""
    __tablename__ = "comanda_items"
    id = Column(Integer, primary_key=True, index=True)
    comanda_id = Column(Integer, ForeignKey("comandas.id"))
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    
    quantity = Column(Float, default=1.0)
    unit_price = Column(Float)
    description = Column(String, nullable=True) # Usado para itens manuais (Peso/Marmitex)
    type = Column(Enum(ComandaItemType), default=ComandaItemType.PRODUTO)
    
    created_at = Column(DateTime, default=datetime.now)
    
    comanda = relationship("Comanda", back_populates="items")
    product = relationship("Product")

class PDVSale(Base, TenantMixin):
    """Registro Histórico de Venda (Imutável)"""
    __tablename__ = "pdv_sales"
    id = Column(Integer, primary_key=True, index=True)
    comanda_identificador = Column(String, index=True) # Nome da comanda no fechamento
    total_amount = Column(Float)
    discount = Column(Float, default=0.0)
    payment_method = Column(Enum(PaymentMethod))
    
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(Integer, ForeignKey("caixa_sessions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User")
    items = relationship("PDVSaleItem", back_populates="sale", cascade="all, delete-orphan")

class PDVSaleItem(Base, TenantMixin):
    """Itens do Registro de Venda (Snapshot)"""
    __tablename__ = "pdv_sale_items"
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("pdv_sales.id"))
    
    product_name = Column(String) # Nome do produto no momento da venda
    quantity = Column(Float)
    unit_price = Column(Float)
    total_item = Column(Float)
    
    sale = relationship("PDVSale", back_populates="items")

class RefreshToken(Base):
    """Tokens de Atualização para Sessões Longas"""
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")
