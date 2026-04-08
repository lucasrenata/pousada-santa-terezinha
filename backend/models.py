from sqlalchemy import Column, Integer, String, Float, Boolean, Enum, ForeignKey, DateTime, Text, Date
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime

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

class User(Base):
    """Usuários do Sistema (Login)"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="recepcionista")

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, unique=True, index=True)
    type = Column(String) 
    price_per_night = Column(Float)
    status = Column(Enum(RoomStatus), default=RoomStatus.DISPONIVEL)
    floor = Column(Integer, default=1)
    
    # --- NOVO CAMPO ---
    max_capacity = Column(Integer, default=2) # Ex: 2 pessoas
    maintenance_note = Column(Text, nullable=True)
    
    bookings = relationship("Booking", back_populates="room")


class Guest(Base):
    """Cadastro Completo do Hóspede Principal"""
    __tablename__ = "guests"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True) 
    email = Column(String, unique=True, index=True)
    phone = Column(String) 
    document = Column(String, unique=True, index=True) 
    birth_date = Column(Date, nullable=True) 
    profession = Column(String, nullable=True)
    address_zip = Column(String, nullable=True) 
    address_street = Column(String, nullable=True) 
    address_number = Column(String, nullable=True)
    address_neighborhood = Column(String, nullable=True) 
    address_city = Column(String, nullable=True)
    address_state = Column(String, nullable=True) 
    bookings = relationship("Booking", back_populates="guest")

class Product(Base):
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
    supplier = Column(String, nullable=True) 
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    is_quick_access = Column(Boolean, default=False)

class Booking(Base):
    """Reserva Detalhada"""
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True) 
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

class Companion(Base):
    """Acompanhantes"""
    __tablename__ = "companions"
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    name = Column(String)
    age = Column(Integer)
    booking = relationship("Booking", back_populates="companions")

class Consumption(Base):
    __tablename__ = "consumptions"
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    unit_price = Column(Float)
    created_at = Column(DateTime, default=datetime.now)
    booking = relationship("Booking", back_populates="consumptions")
    product = relationship("Product")

class Revenue(Base):
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

class StockEntry(Base):
    """Entrada de Estoque (Nota Fiscal)"""
    __tablename__ = "stock_entries"
    id = Column(Integer, primary_key=True, index=True)
    supplier = Column(String, nullable=True)
    invoice_number = Column(String, nullable=True, index=True)
    invoice_date = Column(Date, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    items = relationship("StockEntryItem", back_populates="entry", cascade="all, delete-orphan")

class StockEntryItem(Base):
    __tablename__ = "stock_entry_items"
    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, ForeignKey("stock_entries.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=0)
    unit_price = Column(Float, nullable=True)
    entry = relationship("StockEntry", back_populates="items")
    product = relationship("Product")

class SystemSetting(Base):
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


