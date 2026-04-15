CREATE OR REPLACE FUNCTION clean_old_chat_messages() 
RETURNS trigger AS $$
BEGIN
    DELETE FROM chat_messages 
    WHERE created_at < (NOW() - INTERVAL '2 days');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger disparada após cada inserção na tabela chat_messages
-- Nota: O PostgreSQL não permite triggers AFTER INSERT que deletem da mesma tabela se não for FOR EACH STATEMENT ou similar.
-- Usaremos AFTER INSERT FOR EACH STATEMENT para garantir eficiência.
DROP TRIGGER IF EXISTS trigger_clean_chat_history ON chat_messages;
CREATE TRIGGER trigger_clean_chat_history
AFTER INSERT ON chat_messages
FOR EACH STATEMENT
EXECUTE FUNCTION clean_old_chat_messages();
