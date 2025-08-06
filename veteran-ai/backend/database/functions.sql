-- Vector search function for pgvector
CREATE OR REPLACE FUNCTION vector_search(
    query_embedding vector(1536),
    similarity_threshold float DEFAULT 0.5,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id uuid,
    title text,
    content text,
    document_type varchar(20),
    platform varchar(20),
    metadata jsonb,
    created_at timestamp with time zone,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id,
        d.title,
        d.content,
        d.document_type,
        d.platform,
        d.metadata,
        d.created_at,
        1 - (d.embedding <=> query_embedding) as similarity
    FROM documents d
    WHERE d.embedding IS NOT NULL
    AND 1 - (d.embedding <=> query_embedding) > similarity_threshold
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Find similar documents function
CREATE OR REPLACE FUNCTION find_similar_documents(
    target_embedding vector(1536),
    exclude_id uuid DEFAULT NULL,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id uuid,
    title text,
    content text,
    document_type varchar(20),
    platform varchar(20),
    metadata jsonb,
    created_at timestamp with time zone,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id,
        d.title,
        d.content,
        d.document_type,
        d.platform,
        d.metadata,
        d.created_at,
        1 - (d.embedding <=> target_embedding) as similarity
    FROM documents d
    WHERE d.embedding IS NOT NULL
    AND (exclude_id IS NULL OR d.id != exclude_id)
    ORDER BY d.embedding <=> target_embedding
    LIMIT match_count;
END;
$$;

-- Hybrid search function (combining full-text and vector search)
CREATE OR REPLACE FUNCTION hybrid_search(
    query_text text,
    query_embedding vector(1536),
    similarity_threshold float DEFAULT 0.5,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id uuid,
    title text,
    content text,
    document_type varchar(20),
    platform varchar(20),
    metadata jsonb,
    created_at timestamp with time zone,
    similarity float,
    text_rank float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH vector_search AS (
        SELECT 
            d.id,
            d.title,
            d.content,
            d.document_type,
            d.platform,
            d.metadata,
            d.created_at,
            1 - (d.embedding <=> query_embedding) as similarity
        FROM documents d
        WHERE d.embedding IS NOT NULL
        AND 1 - (d.embedding <=> query_embedding) > similarity_threshold
        ORDER BY d.embedding <=> query_embedding
        LIMIT match_count * 2
    ),
    text_search AS (
        SELECT 
            d.id,
            ts_rank(to_tsvector('english', d.title || ' ' || d.content), plainto_tsquery('english', query_text)) as rank
        FROM documents d
        WHERE to_tsvector('english', d.title || ' ' || d.content) @@ plainto_tsquery('english', query_text)
    )
    SELECT 
        vs.id,
        vs.title,
        vs.content,
        vs.document_type,
        vs.platform,
        vs.metadata,
        vs.created_at,
        vs.similarity,
        COALESCE(ts.rank, 0) as text_rank
    FROM vector_search vs
    LEFT JOIN text_search ts ON vs.id = ts.id
    ORDER BY (vs.similarity * 0.7 + COALESCE(ts.rank, 0) * 0.3) DESC
    LIMIT match_count;
END;
$$;

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Function to enable pgvector (callable from application)
CREATE OR REPLACE FUNCTION enable_pgvector()
RETURNS text
LANGUAGE plpgsql
AS $$
BEGIN
    -- Check if extension exists
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        CREATE EXTENSION vector;
        RETURN 'pgvector extension enabled';
    ELSE
        RETURN 'pgvector extension already enabled';
    END IF;
END;
$$;