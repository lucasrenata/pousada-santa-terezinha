from sqlalchemy import Column, Integer, String, Float, Boolean, Enum, ForeignKey, DateTime, Text, Date, JSON
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
    deposit_amount = Column(Float, default=0.0)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDENTE)
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDENTE)
    room = relationship("Room", back_populates="bookings")
    guest = relationship("Guest", back_populates="bookings")
    consumptions = relationship("Consumption", back_populates="booking")
    companions = relationship("Companion", back_populates="booking")
    # Relacionamento com Revenue (opcional, se quiser linkar pagamentos)
    revenues = relationship("Revenue", back_populates="booking")

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
    created_at = Column(DateTime, default=datetime.now)
    booking = relationship("Booking", back_populates="consumptions")
    product = relationship("Product")

class Revenue(Base, TenantMixin):
    """Tabela Financeira - O Livro Caixa"""
    __tablename__ = "revenues"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)
    amount = Column(Float)
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
    created_at = Column(DateTime, default=datetime.now)
    
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

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)   # A chave única da config
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
