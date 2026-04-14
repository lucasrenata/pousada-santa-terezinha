-- SCRIPT DE INICIALIZAÇÃO DO ROW LEVEL SECURITY (RLS)
-- Este script ativa o isolamento de dados no nível do banco de dados.

-- 1. Habilitar RLS em todas as tabelas de negócio
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE guests ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE companions ENABLE ROW LEVEL SECURITY;
ALTER TABLE consumptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE revenues ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_entry_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

-- 2. Criar Políticas de Isolamento (Isolation Policies)
-- Nota: 'app.current_tenant' é a variável de sessão definida pelo backend.

DO $$
DECLARE
    t TEXT;
    tables TEXT[] := ARRAY[
        'users', 'rooms', 'guests', 'products', 'bookings', 
        'companions', 'consumptions', 'revenues', 'business_rules', 
        'chat_messages', 'stock_entries', 'stock_entry_items', 
        'settings', 'events'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        -- Remove política se já existir para evitar erro em re-execução
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_policy ON %I', t);
        
        -- Cria a política: só permite acesso se o tenant_id da linha for igual ao da sessão
        -- Ou se o tenant_id for nulo (para dados globais ou migração, se necessário - use com cautela)
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

-- 3. Bypasses e Exceções (Opcional)
-- Caso queira que o usuário 'admin' do postgres veja tudo (já é padrão),
-- mas se quiser criar um role 'superadmin' que ignore RLS:
-- ALTER ROLE superadmin BYPASSRLS;
