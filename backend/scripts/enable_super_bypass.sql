-- SCRIPT DE ATUALIZAÇÃO DE RLS PARA BYPASS DO SUPERADMIN
-- Permite que sessões com app.current_tenant = '-1' vejam todos os registros.

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
        -- Remove política antiga
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_policy ON %I', t);
        
        -- Cria a nova política com suporte ao bypass (-1)
        EXECUTE format('
            CREATE POLICY tenant_isolation_policy ON %I 
            USING (
                tenant_id = current_setting(''app.current_tenant'')::integer 
                OR current_setting(''app.current_tenant'') = ''-1''
            )
            WITH CHECK (
                tenant_id = current_setting(''app.current_tenant'')::integer 
                OR current_setting(''app.current_tenant'') = ''-1''
            )
        ', t);
    END LOOP;
END $$;
