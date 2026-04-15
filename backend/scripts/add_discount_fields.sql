-- Adiciona campos de desconto para reservas e receitas
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS discount FLOAT DEFAULT 0.0;
ALTER TABLE revenues ADD COLUMN IF NOT EXISTS discount FLOAT DEFAULT 0.0;
