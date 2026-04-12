-- CC-Claw Agent Store Database Schema
-- Migration: 001_add_store_schema.sql

-- =====================================================
-- EXTENSIONS
-- =====================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy search

-- =====================================================
-- TEMPLATES TABLE
-- =====================================================

CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    tagline VARCHAR(500),
    description TEXT,
    category VARCHAR(100) NOT NULL,
    tags JSONB DEFAULT '[]',
    icon VARCHAR(50) DEFAULT '🤖',
    cover_image VARCHAR(500),
    screenshots JSONB DEFAULT '[]',

    -- Configuration
    config JSONB NOT NULL,

    -- Pricing
    price INTEGER DEFAULT 0,           -- In cents (0 = free)
    currency VARCHAR(3) DEFAULT 'USD',
    license VARCHAR(50) DEFAULT 'MIT',
    source_included BOOLEAN DEFAULT FALSE,

    -- Stats
    downloads INTEGER DEFAULT 0,
    rating DECIMAL(3,2) DEFAULT 0,
    rating_count INTEGER DEFAULT 0,

    -- Author
    author_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    published_at TIMESTAMP WITH TIME ZONE,

    -- Status
    status VARCHAR(20) DEFAULT 'draft',

    -- Full-text search
    search_vector TSVECTOR
);

-- Indexes
CREATE INDEX templates_slug_idx ON templates(slug);
CREATE INDEX templates_category_idx ON templates(category);
CREATE INDEX templates_author_idx ON templates(author_id);
CREATE INDEX templates_status_idx ON templates(status);
CREATE INDEX templates_price_idx ON templates(price);
CREATE INDEX templates_rating_idx ON templates(rating DESC);
CREATE INDEX templates_downloads_idx ON templates(downloads DESC);
CREATE INDEX templates_created_at_idx ON templates(created_at DESC);
CREATE INDEX templates_search_idx ON templates USING GIN(search_vector);
CREATE INDEX templates_tags_idx ON templates USING GIN(tags);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER templates_updated_at
    BEFORE UPDATE ON templates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Trigger to update search_vector
CREATE OR REPLACE FUNCTION templates_search_trigger()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector = to_tsvector('english',
        COALESCE(NEW.name, '') || ' ' ||
        COALESCE(NEW.tagline, '') || ' ' ||
        COALESCE(NEW.description, '') || ' ' ||
        COALESCE(NEW.tags::TEXT, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER templates_search_update
    BEFORE INSERT OR UPDATE ON templates
    FOR EACH ROW
    EXECUTE FUNCTION templates_search_trigger();

-- =====================================================
-- TEMPLATE REVIEWS
-- =====================================================

CREATE TABLE template_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(255),
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(template_id, user_id)
);

CREATE INDEX template_reviews_template_idx ON template_reviews(template_id);
CREATE INDEX template_reviews_user_idx ON template_reviews(user_id);
CREATE INDEX template_reviews_rating_idx ON template_reviews(rating DESC);

-- Trigger to update template rating on review change
CREATE OR REPLACE FUNCTION update_template_rating()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE templates
    SET rating = (
        SELECT COALESCE(AVG(rating), 0)
        FROM template_reviews
        WHERE template_id = COALESCE(NEW.template_id, OLD.template_id)
    ),
    rating_count = (
        SELECT COUNT(*)
        FROM template_reviews
        WHERE template_id = COALESCE(NEW.template_id, OLD.template_id)
    )
    WHERE id = COALESCE(NEW.template_id, OLD.template_id);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER template_reviews_rating_update
    AFTER INSERT OR UPDATE OR DELETE ON template_reviews
    FOR EACH ROW
    EXECUTE FUNCTION update_template_rating();

-- =====================================================
-- PURCHASES TABLE
-- =====================================================

CREATE TABLE purchases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    price_paid INTEGER NOT NULL,                    -- In cents
    currency VARCHAR(3) DEFAULT 'USD',
    stripe_payment_id VARCHAR(255),
    stripe_session_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'completed',        -- pending, completed, refunded
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(template_id, user_id)
);

CREATE INDEX purchases_template_idx ON purchases(template_id);
CREATE INDEX purchases_user_idx ON purchases(user_id);
CREATE INDEX purchases_stripe_idx ON purchases(stripe_payment_id);
CREATE INDEX purchases_created_at_idx ON purchases(created_at DESC);

-- =====================================================
-- DOWNLOADS TABLE (for free templates)
-- =====================================================

CREATE TABLE template_downloads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,  -- Null for anonymous
    downloaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX template_downloads_template_idx ON template_downloads(template_id);
CREATE INDEX template_downloads_user_idx ON template_downloads(user_id);

-- Trigger to update template download count
CREATE OR REPLACE FUNCTION update_template_downloads()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE templates
    SET downloads = (
        SELECT COUNT(*)
        FROM purchases
        WHERE template_id = NEW.template_id AND status = 'completed'
    ) + (
        SELECT COUNT(*)
        FROM template_downloads
        WHERE template_id = NEW.template_id
    )
    WHERE id = NEW.template_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER template_downloads_count_update
    AFTER INSERT ON purchases
    FOR EACH ROW
    WHEN (NEW.status = 'completed')
    EXECUTE FUNCTION update_template_downloads();

CREATE TRIGGER template_downloads_free_count_update
    AFTER INSERT ON template_downloads
    FOR EACH ROW
    EXECUTE FUNCTION update_template_downloads();

-- =====================================================
-- FAVORITES / WISHLIST
-- =====================================================

CREATE TABLE favorites (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    PRIMARY KEY (user_id, template_id)
);

CREATE INDEX favorites_user_idx ON favorites(user_id);
CREATE INDEX favorites_template_idx ON favorites(template_id);

-- =====================================================
-- SELLER ACCOUNTS
-- =====================================================

CREATE TABLE seller_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending',      -- pending, approved, rejected
    paypal_email VARCHAR(255),
    stripe_account_id VARCHAR(255),
    stripe_onboarding_complete BOOLEAN DEFAULT FALSE,
    rejection_reason TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,

    UNIQUE(user_id)
);

CREATE INDEX seller_applications_user_idx ON seller_applications(user_id);
CREATE INDEX seller_applications_status_idx ON seller_applications(status);

-- =====================================================
-- EARNINGS & PAYOUTS
-- =====================================================

CREATE TABLE earnings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    seller_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    template_id UUID REFERENCES templates(id) ON DELETE SET NULL,
    purchase_id UUID REFERENCES purchases(id) ON DELETE SET NULL,
    amount INTEGER NOT NULL,                   -- In cents (after platform fee)
    platform_fee INTEGER NOT NULL,             -- Platform fee amount
    gross_amount INTEGER NOT NULL,             -- Original price
    status VARCHAR(20) DEFAULT 'pending',      -- pending, available, paid
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CHECK (amount >= 0),
    CHECK (platform_fee >= 0),
    CHECK (gross_amount >= 0)
);

CREATE INDEX earnings_seller_idx ON earnings(seller_id);
CREATE INDEX earnings_status_idx ON earnings(status);
CREATE INDEX earnings_created_at_idx ON earnings(created_at DESC);

-- =====================================================
-- PLATFORM SETTINGS
-- =====================================================

CREATE TABLE platform_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Default settings
INSERT INTO platform_settings (key, value) VALUES
('platform_fees', '{"default": 0.15, "pro": 0.10, "partner": 0.05}'),
('payout_settings', '{"min_payout": 1000, "payout_schedule": "weekly"}');  -- min in cents ($10)

-- =====================================================
-- CATEGORIES (Seed Data)
-- =====================================================

CREATE TABLE template_categories (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    sort_order INTEGER DEFAULT 0,
    template_count INTEGER DEFAULT 0
);

INSERT INTO template_categories (id, name, description, icon, sort_order) VALUES
('bug-fixing', 'Bug Fixing', 'Automatically find and fix bugs', '🐛', 1),
('feature-development', 'Feature Development', 'Build new features efficiently', '⚡', 2),
('refactoring', 'Refactoring', 'Improve code quality and structure', '🔧', 3),
('code-review', 'Code Review', 'Review and analyze code', '👀', 4),
('testing', 'Testing', 'Write and manage tests', '🧪', 5),
('documentation', 'Documentation', 'Generate and maintain docs', '📚', 6),
('devops', 'DevOps', 'CI/CD and deployment automation', '🚀', 7),
('ci-cd', 'CI/CD', 'Pipeline setup and management', '🔄', 8),
('docker', 'Docker', 'Container management', '🐳', 9),
('kubernetes', 'Kubernetes', 'K8s deployment and management', '☸️', 10),
('infrastructure', 'Infrastructure', 'Infrastructure as code', '🏗️', 11),
('data-analysis', 'Data Analysis', 'Analyze and visualize data', '📊', 12),
('machine-learning', 'Machine Learning', 'ML model development', '🤖', 13),
('data-pipeline', 'Data Pipeline', 'ETL and data processing', '🔗', 14),
('research', 'Research', 'Web research and analysis', '🔍', 15),
('content-writing', 'Content Writing', 'Generate written content', '✍️', 16),
('learning', 'Learning', 'Study and learning assistance', '📖', 17);

-- =====================================================
-- FUNCTION: Update category counts
-- =====================================================

CREATE OR REPLACE FUNCTION update_category_counts()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE template_categories
    SET template_count = (
        SELECT COUNT(*)
        FROM templates
        WHERE category = template_categories.id
        AND status = 'published'
    )
    WHERE id IN (SELECT DISTINCT category FROM templates);

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_category_counts_trigger
    AFTER INSERT OR UPDATE OR DELETE ON templates
    FOR EACH ROW
    EXECUTE FUNCTION update_category_counts();

-- =====================================================
-- VIEWS
-- =====================================================

-- View for template list with author info
CREATE VIEW template_list_view AS
SELECT
    t.id,
    t.slug,
    t.name,
    t.tagline,
    t.category,
    t.icon,
    t.price,
    t.currency,
    t.downloads,
    t.rating,
    t.rating_count,
    t.status,
    t.published_at,
    t.created_at,
    u.id as author_id,
    u.username as author_username,
    u.name as author_name,
    u.avatar_url as author_avatar
FROM templates t
LEFT JOIN users u ON t.author_id = u.id
WHERE t.status = 'published';

-- View for seller earnings summary
CREATE VIEW seller_earnings_summary AS
SELECT
    e.seller_id,
    u.username,
    SUM(CASE WHEN e.status = 'pending' THEN e.amount ELSE 0 END) as pending_amount,
    SUM(CASE WHEN e.status = 'available' THEN e.amount ELSE 0 END) as available_amount,
    SUM(CASE WHEN e.status = 'paid' THEN e.amount ELSE 0 END) as paid_amount,
    COUNT(*) as total_transactions
FROM earnings e
JOIN users u ON e.seller_id = u.id
GROUP BY e.seller_id, u.username;

-- =====================================================
-- PERMISSIONS (assuming auth system exists)
-- =====================================================

-- Users can read published templates
-- Only authors can update their own templates
-- Only purchasers can review templates they bought
-- Sellers can see their own earnings
