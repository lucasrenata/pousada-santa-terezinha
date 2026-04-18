-- SCRIPT DE PROVISIONAMENTO DO USUÁRIO DA APLICAÇÃO (POUSADA_APP)
-- Este script deve ser executado pelo usuário 'admin' (superuser)

-- 1. Criar o usuário 'pousada_app' se ele não existir
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'pousada_app') THEN
        CREATE ROLE pousada_app WITH LOGIN PASSWORD 'ParcerIA19141919@';
    ELSE
        ALTER ROLE pousada_app WITH PASSWORD 'ParcerIA19141919@';
    END IF;
END $$;

-- 2. Garantir permissões básicas de conexão e esquema
GRANT CONNECT ON DATABASE pousada_db TO pousada_app;
GRANT USAGE ON SCHEMA public TO pousada_app;

-- 3. Dar permissões em todas as tabelas atuais
-- Nota: Isso é necessário para que o pousada_app possa ler/escrever dados
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pousada_app;

-- 4. Dar permissões em todas as sequências (necessário para IDs auto-incremento)
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO pousada_app;

-- 5. Configurar privilégios padrão para o futuro
-- Garante que tabelas criadas no futuro pelo 'admin' (via Alembic) 
-- sejam automaticamente acessíveis pelo 'pousada_app'
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public 
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pousada_app;

ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public 
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO pousada_app;

-- 6. Garantir que o usuário pousada_app NÃO tenha bypass de RLS
-- (Opcional, pois por padrão ele não tem, mas garante a segurança máxima)
ALTER ROLE pousada_app NOBYPASSRLS;

-- 7. Ativar RLS nas tabelas (caso ainda não estejam)
-- Este passo reforça o que o script init_rls.sql faz
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE guests ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_state ENABLE ROW LEVEL SECURITY;

-- Mensagem de Confirmação
SELECT 'Provisionamento de pousada_app concluído com sucesso!' as status;
