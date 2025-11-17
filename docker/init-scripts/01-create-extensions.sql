-- Create PostgreSQL extensions for vector similarity search
-- Note: pgvector extension may not be available in standard postgres image
-- For production, use ankane/pgvector Docker image

-- Create extensions if available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Placeholder for pgvector (requires ankane/pgvector image)
-- CREATE EXTENSION IF NOT EXISTS vector;
