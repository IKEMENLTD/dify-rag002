-- 管理者アカウント作成SQL
-- Email: ooxmichaelxoo@gmail.com
-- Password: akutu4256

-- Generate UUID
DO $$
DECLARE
    user_id UUID := gen_random_uuid();
    password_hash TEXT;
    salt TEXT;
BEGIN
    -- Generate salt
    salt := encode(gen_random_bytes(32), 'hex');
    
    -- For production, you should properly hash the password
    -- This is a placeholder - actual password hashing should be done in application
    password_hash := encode(digest('akutu4256' || salt, 'sha256'), 'hex');
    
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
        -- Insert new admin user
        INSERT INTO users (
            id,
            email,
            username,
            password_hash,
            salt,
            role,
            permissions,
            is_active,
            created_at,
            updated_at
        ) VALUES (
            user_id,
            'ooxmichaelxoo@gmail.com',
            'ooxmichaelxoo',
            password_hash,
            salt,
            'admin',
            ARRAY['read', 'write', 'delete', 'admin'],
            true,
            NOW(),
            NOW()
        );
        
        RAISE NOTICE 'Created new admin user';
    END IF;
    
    -- Create API key for admin user
    INSERT INTO api_keys (
        user_id,
        key,
        name,
        permissions,
        is_active,
        created_at
    ) VALUES (
        user_id,
        'sk-admin-' || encode(gen_random_bytes(32), 'base64'),
        'Admin API Key',
        ARRAY['read', 'write', 'delete', 'admin'],
        true,
        NOW()
    );
    
    RAISE NOTICE 'Admin account created/updated successfully';
    RAISE NOTICE 'Email: ooxmichaelxoo@gmail.com';
    RAISE NOTICE 'Role: admin';
    RAISE NOTICE 'Permissions: read, write, delete, admin';
END $$;