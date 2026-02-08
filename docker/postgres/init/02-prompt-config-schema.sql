-- Schema for prompt_config database (Clerk + UUID, no migrations).
-- Run this script when connected to database "prompt_config".

-- placeholders
CREATE TABLE IF NOT EXISTS placeholders (
    id UUID NOT NULL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_placeholders_name ON placeholders (name);

-- placeholder_values
CREATE TABLE IF NOT EXISTS placeholder_values (
    id UUID NOT NULL PRIMARY KEY,
    placeholder_id UUID NOT NULL REFERENCES placeholders (id),
    name VARCHAR(100) NOT NULL,
    value TEXT NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_placeholder_values_name ON placeholder_values (name);

-- profiles
CREATE TABLE IF NOT EXISTS profiles (
    id UUID NOT NULL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_profiles_name ON profiles (name);
CREATE INDEX IF NOT EXISTS ix_profiles_category ON profiles (category);

-- profile_placeholder_settings
CREATE TABLE IF NOT EXISTS profile_placeholder_settings (
    profile_id UUID NOT NULL REFERENCES profiles (id),
    placeholder_id UUID NOT NULL REFERENCES placeholders (id),
    placeholder_value_id UUID NOT NULL REFERENCES placeholder_values (id),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    PRIMARY KEY (profile_id, placeholder_id)
);

-- user_profiles (Clerk + optional wallet)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID NOT NULL PRIMARY KEY,
    clerk_user_id VARCHAR(255) UNIQUE,
    wallet_address VARCHAR(42) UNIQUE,
    username VARCHAR(100),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    last_login TIMESTAMP WITHOUT TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_user_profiles_clerk ON user_profiles (clerk_user_id);
CREATE INDEX IF NOT EXISTS ix_user_profiles_wallet ON user_profiles (wallet_address);

-- user_placeholder_settings
CREATE TABLE IF NOT EXISTS user_placeholder_settings (
    user_id UUID NOT NULL REFERENCES user_profiles (id) ON DELETE CASCADE,
    placeholder_id UUID NOT NULL REFERENCES placeholders (id) ON DELETE CASCADE,
    placeholder_value_id UUID NOT NULL REFERENCES placeholder_values (id) ON DELETE RESTRICT,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, placeholder_id)
);
