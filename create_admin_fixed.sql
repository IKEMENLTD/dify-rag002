-- 管理者アカウント作成 (修正版)
-- Email: ooxmichaelxoo@gmail.com

DO $$
DECLARE
    user_id UUID := gen_random_uuid();
BEGIN
    -- Check if user exists
    IF EXISTS (SELECT 1 FROM users WHERE email = 'ooxmichaelxoo@gmail.com') THEN
        -- Update existing user to admin
        UPDATE users
        SET 
            is_active = true,
            updated_at = NOW()
        WHERE email = 'ooxmichaelxoo@gmail.com';
        
        -- Get the user_id
        SELECT id INTO user_id FROM users WHERE email = 'ooxmichaelxoo@gmail.com';
        
        RAISE NOTICE 'Updated existing user to admin';
    ELSE
        -- Insert new admin user (with available columns only)
        INSERT INTO users (
            id,
            email,
            username,
            is_active,
            created_at,
            updated_at
        ) VALUES (
            user_id,
            'ooxmichaelxoo@gmail.com',
            'ooxmichaelxoo',
            true,
            NOW(),
            NOW()
        );
        
        RAISE NOTICE 'Created new admin user';
    END IF;
    
    RAISE NOTICE 'Admin account created/updated successfully';
    RAISE NOTICE 'Email: ooxmichaelxoo@gmail.com';
    RAISE NOTICE '';
    RAISE NOTICE 'IMPORTANT: This user needs to be linked with Supabase Auth';
    RAISE NOTICE 'Please create auth user in Supabase Dashboard with password: akutu4256';
END $$;

-- 表示作成されたユーザー情報
SELECT * FROM users WHERE email = 'ooxmichaelxoo@gmail.com';