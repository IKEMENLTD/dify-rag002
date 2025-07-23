-- 管理者アカウント作成 (Supabase用)
-- Email: ooxmichaelxoo@gmail.com
-- Username: ooxmichaelxoo

-- 方法1: usersテーブルに直接追加（auth_user_idがNULLの場合）
DO $$
DECLARE
    user_id UUID := gen_random_uuid();
BEGIN
    -- Check if user exists
    IF EXISTS (SELECT 1 FROM users WHERE email = 'ooxmichaelxoo@gmail.com') THEN
        -- Update existing user to admin
        UPDATE users
        SET 
            role = 'admin',
            permissions = ARRAY['read', 'write', 'delete', 'admin'],
            is_active = true,
            updated_at = NOW()
        WHERE email = 'ooxmichaelxoo@gmail.com';
        
        -- Get the user_id
        SELECT id INTO user_id FROM users WHERE email = 'ooxmichaelxoo@gmail.com';
        
        RAISE NOTICE 'Updated existing user to admin';
    ELSE
        -- Insert new admin user (without auth integration)
        INSERT INTO users (
            id,
            email,
            display_name,
            role,
            permissions,
            auth_provider,
            is_active,
            created_at,
            updated_at
        ) VALUES (
            user_id,
            'ooxmichaelxoo@gmail.com',
            'Michael Admin',
            'admin',
            ARRAY['read', 'write', 'delete', 'admin'],
            'email',
            true,
            NOW(),
            NOW()
        );
        
        RAISE NOTICE 'Created new admin user';
    END IF;
    
    -- Create API key for admin user
    INSERT INTO api_keys (
        user_id,
        api_key_hash,
        name,
        permissions,
        is_active,
        created_at,
        expires_at
    ) VALUES (
        user_id,
        -- Note: This is a placeholder hash. In production, use proper hashing
        encode(digest('sk-admin-' || gen_random_uuid()::text, 'sha256'), 'hex'),
        'Admin API Key',
        ARRAY['read', 'write', 'delete', 'admin'],
        true,
        NOW(),
        NOW() + INTERVAL '1 year'
    );
    
    RAISE NOTICE 'Admin account created/updated successfully';
    RAISE NOTICE 'Email: ooxmichaelxoo@gmail.com';
    RAISE NOTICE 'Role: admin';
    RAISE NOTICE 'Permissions: read, write, delete, admin';
    RAISE NOTICE '';
    RAISE NOTICE 'IMPORTANT: To set the password, you need to:';
    RAISE NOTICE '1. Create an auth.users entry through Supabase Dashboard';
    RAISE NOTICE '2. Or use Supabase Auth API to create the user with password';
END $$;

-- 表示作成されたユーザー情報
SELECT 
    id,
    email,
    display_name,
    role,
    permissions,
    is_active,
    created_at
FROM users 
WHERE email = 'ooxmichaelxoo@gmail.com';

-- 表示作成されたAPIキー情報
SELECT 
    ak.id,
    ak.name,
    ak.permissions,
    ak.is_active,
    ak.expires_at
FROM api_keys ak
JOIN users u ON ak.user_id = u.id
WHERE u.email = 'ooxmichaelxoo@gmail.com';