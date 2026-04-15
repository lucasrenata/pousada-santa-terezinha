-- SCRIPT DE MIGRAÇÃO E ATIVAÇÃO DE RLS
-- Adiciona a coluna tenant_id e ativa as políticas de isolamento

SET app.current_tenant = '-1';

-- 1. Garante que existe pelo menos um Tenant padrão
INSERT INTO tenants (name, is_active, created_at) 
SELECT 'Pousada Principal', true, now()
WHERE NOT EXISTS (SELECT 1 FROM tenants WHERE id = 1);

-- 2. Adiciona tenant_id em todas as tabelas e atribui ao Tenant 1
DO $$
DECLARE
    t TEXT;
    tables TEXT[] := ARRAY[
        'users', 'rooms', 'guests', 'products', 'bookings', 
        'companions', 'consumptions', 'revenues', 'business_rules', 
        'chat_messages', 'stock_entries', 'stock_entry_items', 
        'settings', 'events', 'expenses', 'product_categories'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        -- Adiciona a coluna se ela não existir
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = t AND column_name = 'tenant_id') THEN
            EXECUTE format('ALTER TABLE %I ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)', t);
            -- Atribui dados existentes ao Tenant 1
            EXECUTE format('UPDATE %I SET tenant_id = 1 WHERE tenant_id IS NULL', t);
        END IF;

        -- Habilita RLS e força a política mesmo para o proprietário da tabela
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);

        -- Recria a política de isolamento
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_policy ON %I', t);
        EXECUTE format('
            CREATE POLICY tenant_isolation_policy ON %I 
            USING (
                tenant_id = NULLIF(current_setting(''app.current_tenant'', true), '''') ::integer 
                OR 
                current_setting(''app.current_tenant'', true) = ''-1''
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting(''app.current_tenant'', true), '''') ::integer 
                OR 
                current_setting(''app.current_tenant'', true) = ''-1''
            )
        ', t);
    END LOOP;
END $$;
