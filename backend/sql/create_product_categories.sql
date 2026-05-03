-- Criação da tabela de categorias de produtos se não existir
CREATE TABLE IF NOT EXISTS product_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index para performance
CREATE INDEX IF NOT EXISTS ix_product_categories_id ON product_categories (id);
CREATE INDEX IF NOT EXISTS ix_product_categories_name ON product_categories (name);
CREATE INDEX IF NOT EXISTS ix_product_categories_tenant_id ON product_categories (tenant_id);
