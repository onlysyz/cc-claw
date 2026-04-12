# CC-Claw Agent Store — Design Document

## Overview

The Agent Store is a marketplace where users can share, discover, and purchase preset agent configurations (templates) for CC-Claw.

**Core Concept:**
> "Agents as first-class products" — Each template is a pre-configured agent with goals, tools, prompts, and settings optimized for specific use cases.

---

## Marketplace Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                        │
│  /store — Marketplace browse                                    │
│  /store/[id] — Template detail                                 │
│  /store/create — Submit template                               │
│  /store/manage — My templates                                  │
│  /store/purchases — Purchased templates                       │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API Gateway                             │
│  Authentication, Rate Limiting, Caching                        │
└─────────────────────────────┬───────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Templates    │   │   Payments    │   │    Users      │
│  Service      │   │   Service     │   │   Service     │
└───────────────┘   └───────────────┘   └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  PostgreSQL   │   │   Stripe      │   │  PostgreSQL   │
│  (templates)  │   │   (billing)   │   │  (users)      │
└───────────────┘   └───────────────┘   └───────────────┘
```

---

## Template Schema

### Template Types

| Type | Description | Price Range |
|------|-------------|-------------|
| **Goal Template** | Pre-configured goal + task decomposition | Free - $5 |
| **Tool Set** | Bundled tool configurations | $2 - $10 |
| **Workflow** | Multi-step autonomous workflows | $5 - $20 |
| **Full Agent** | Complete agent with personality + tools | $10 - $50 |

### Template Structure

```typescript
interface AgentTemplate {
  id: string;
  slug: string;

  // Basic Info
  name: string;                    // "Bug Fixer Pro"
  tagline: string;                  // "Automatically find and fix bugs"
  description: string;              // Full markdown description
  category: TemplateCategory;
  tags: string[];                   // ["bug-fixing", "python", "fast"]

  // Media
  icon: string;                    // Emoji or icon name
  coverImage?: string;              // URL to cover image
  screenshots?: string[];           // Array of screenshot URLs

  // Content
  config: TemplateConfig;

  // Pricing
  price: number;                   // In cents (0 = free)
  currency: "USD" | "CNY";

  // Licensing
  license: "MIT" | "CC-BY" | "CC-BY-NC" | "Proprietary";
  sourceIncluded: boolean;          // Can users see the full config?

  // Stats
  downloads: number;
  rating: number;                  // 1-5 stars
  ratingCount: number;

  // Author
  authorId: string;
  author: UserSummary;

  // Timestamps
  createdAt: Date;
  updatedAt: Date;
  publishedAt?: Date;

  // Status
  status: "draft" | "pending" | "published" | "rejected";
}

interface TemplateConfig {
  // Goal settings
  defaultGoal: string;
  goalPrompt?: string;             // Custom prompt for goal decomposition

  // Tools enabled
  tools: ToolConfig[];

  // Claude settings
  claudeSettings: {
    model?: "opus" | "sonnet" | "haiku";
    temperature?: number;
    maxTokens?: number;
  };

  // Custom instructions
  systemPrompt?: string;           // Override system prompt
  userPromptTemplate?: string;     // Template for user input

  // Files included (for full agents)
  files?: TemplateFile[];

  // Dependencies (npm packages, etc.)
  dependencies?: string[];
}

interface ToolConfig {
  name: string;
  enabled: boolean;
  settings: Record<string, any>;   // Tool-specific settings
}

interface TemplateFile {
  path: string;
  content: string;                  // Base64 encoded for binary files
  description?: string;
}
```

### Categories

```typescript
enum TemplateCategory {
  // Development
  BUG_FIXING = "bug-fixing",
  FEATURE_DEV = "feature-development",
  REFACTORING = "refactoring",
  CODE_REVIEW = "code-review",
  TESTING = "testing",
  DOCUMENTATION = "documentation",

  // DevOps
  DEVOPS = "devops",
  CI_CD = "ci-cd",
  DOCKER = "docker",
  KUBERNETES = "kubernetes",
  INFRASTRUCTURE = "infrastructure",

  // Data
  DATA_ANALYSIS = "data-analysis",
  MACHINE_LEARNING = "machine-learning",
  DATA_PIPELINE = "data-pipeline",

  // General
  RESEARCH = "research",
  CONTENT_WRITING = "content-writing",
  LEARNING = "learning",
}
```

---

## Database Schema

```sql
-- Users (extend existing User model)
ALTER TABLE users ADD COLUMN is_seller BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN stripe_account_id VARCHAR(255);
ALTER TABLE users ADD COLUMN payout_email VARCHAR(255);

-- Templates table
CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    tagline VARCHAR(500),
    description TEXT,
    category VARCHAR(100) NOT NULL,
    tags JSONB DEFAULT '[]',
    icon VARCHAR(50) DEFAULT '🤖',

    -- Content
    config JSONB NOT NULL,
    cover_image VARCHAR(500),
    screenshots JSONB DEFAULT '[]',

    -- Pricing
    price INTEGER DEFAULT 0,           -- In cents
    currency VARCHAR(3) DEFAULT 'USD',
    license VARCHAR(50) DEFAULT 'MIT',
    source_included BOOLEAN DEFAULT FALSE,

    -- Stats
    downloads INTEGER DEFAULT 0,
    rating DECIMAL(3,2) DEFAULT 0,
    rating_count INTEGER DEFAULT 0,

    -- Author
    author_id UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    published_at TIMESTAMP,

    -- Status
    status VARCHAR(20) DEFAULT 'draft',

    -- Search vector
    search_vector TSVECTOR
);

-- Create index for search
CREATE INDEX templates_search_idx ON templates USING GIN(search_vector);
CREATE INDEX templates_category_idx ON templates(category);
CREATE INDEX templates_author_idx ON templates(author_id);
CREATE INDEX templates_status_idx ON templates(status);

-- Reviews
CREATE TABLE template_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES templates(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(255),
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(template_id, user_id)
);

-- Purchases
CREATE TABLE purchases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES templates(id),
    user_id UUID REFERENCES users(id),
    price_paid INTEGER NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    stripe_payment_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(template_id, user_id)
);

-- Downloads (for free templates)
CREATE TABLE template_downloads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES templates(id),
    user_id UUID REFERENCES users(id),
    downloaded_at TIMESTAMP DEFAULT NOW()
);

-- Favorites/Wishlist
CREATE TABLE favorites (
    user_id UUID REFERENCES users(id),
    template_id UUID REFERENCES templates(id),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, template_id)
);
```

---

## API Endpoints

### Templates

```
GET    /api/store/templates              — List templates (paginated, filterable)
GET    /api/store/templates/:slug        — Get template by slug
POST   /api/store/templates              — Create template (authenticated)
PUT    /api/store/templates/:id          — Update template
DELETE /api/store/templates/:id          — Delete template
POST   /api/store/templates/:id/publish — Publish template
POST   /api/store/templates/:id/unpublish — Unpublish template

GET    /api/store/templates/:id/download — Download template (if purchased/free)
GET    /api/store/templates/:id/preview — Preview template config (no spoiler)
```

### Reviews

```
GET    /api/store/templates/:id/reviews  — List reviews for template
POST   /api/store/templates/:id/reviews  — Add review (purchased only)
PUT    /api/store/reviews/:id            — Update own review
DELETE /api/store/reviews/:id            — Delete own review
```

### Purchases

```
POST   /api/store/templates/:id/purchase  — Purchase template (Stripe)
GET    /api/store/purchases              — List user's purchases
GET    /api/store/purchases/:id          — Get purchase details
```

### Seller

```
GET    /api/store/seller/templates        — List seller's templates
GET    /api/store/seller/earnings        — Get earnings summary
GET    /api/store/seller/payouts         — List payouts
POST   /api/store/seller/apply           — Apply to become seller
```

### Search & Discovery

```
GET    /api/store/categories              — List categories
GET    /api/store/featured               — Featured templates
GET    /api/store/trending               — Trending templates
GET    /api/store/new                    — Newest templates
GET    /api/store/free                   — Free templates
```

### Query Parameters

```
GET /api/store/templates?
  category=bug-fixing
  &tags=["python","javascript"]
  &price_min=0
  &price_max=1000
  &sort=downloads|rating|newest|price
  &page=1
  &limit=20
  &q=search+query
```

---

## API Response Formats

### List Templates Response

```json
{
  "success": true,
  "data": {
    "templates": [
      {
        "id": "uuid",
        "slug": "bug-fixer-pro",
        "name": "Bug Fixer Pro",
        "tagline": "Automatically find and fix bugs",
        "icon": "🐛",
        "category": "bug-fixing",
        "price": 500,
        "rating": 4.8,
        "ratingCount": 124,
        "downloads": 3420,
        "author": {
          "id": "uuid",
          "username": "dev123",
          "avatarUrl": "..."
        }
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 150,
      "pages": 8
    },
    "filters": {
      "categories": [
        {"value": "bug-fixing", "count": 45},
        {"value": "feature-dev", "count": 32}
      ],
      "priceRange": {
        "min": 0,
        "max": 5000
      }
    }
  }
}
```

### Template Detail Response

```json
{
  "success": true,
  "data": {
    "template": {
      "id": "uuid",
      "slug": "bug-fixer-pro",
      "name": "Bug Fixer Pro",
      "tagline": "Automatically find and fix bugs",
      "description": "# Bug Fixer Pro\n\nThis template...",
      "category": "bug-fixing",
      "tags": ["bug-fixing", "python", "debugging"],
      "icon": "🐛",
      "coverImage": "https://...",
      "screenshots": ["https://...", "https://..."],
      "price": 500,
      "currency": "USD",
      "license": "MIT",
      "sourceIncluded": true,
      "downloads": 3420,
      "rating": 4.8,
      "ratingCount": 124,
      "author": {
        "id": "uuid",
        "username": "dev123",
        "name": "Developer Name",
        "avatarUrl": "...",
        "templateCount": 12,
        "totalDownloads": 15000
      },
      "config": {
        "defaultGoal": "Fix all bugs in the repository",
        "tools": [...],
        "claudeSettings": {...}
      },
      "createdAt": "2024-01-15T00:00:00Z",
      "updatedAt": "2024-01-20T00:00:00Z",
      "publishedAt": "2024-01-16T00:00:00Z"
    },
    "isPurchased": false,
    "isFavorited": false
  }
}
```

---

## Frontend Pages

### /store — Marketplace Browse

```
┌─────────────────────────────────────────────────────────────────┐
│  🔍 Search...                    [Category ▼] [Sort ▼] [Filter]│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Categories:                                                    │
│  [🐛 Bug Fixing] [⚡ Feature Dev] [🧪 Testing] [📚 Docs]       │
│  [🚀 DevOps] [🐳 Docker] [📊 Data] [🔬 ML]                     │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ 🐛 Bug      │  │ ⚡ Feature  │  │ 🔧 Code    │            │
│  │ Fixer Pro  │  │ Dev Kit     │  │ Review AI  │            │
│  │ ★★★★☆ 124  │  │ ★★★★★ 89    │  │ ★★★★☆ 56   │            │
│  │ $4.99      │  │ Free        │  │ $9.99      │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ 🐳 Docker  │  │ 📊 Data    │  │ 🚀 CI/CD   │            │
│  │ Helper     │  │ Analysis    │  │ Pipeline   │            │
│  │ ★★★★☆ 78   │  │ ★★★★☆ 45   │  │ ★★★★★ 112  │            │
│  │ Free       │  │ $14.99     │  │ $19.99     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Showing 1-20 of 150 templates    [< Prev] [1] [2] [3] [Next] │
└─────────────────────────────────────────────────────────────────┘
```

### /store/[slug] — Template Detail

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to Store                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🐛 Bug Fixer Pro                           by @dev123        │
│  ★★★★☆ 4.8 (124 reviews)              3,420 downloads        │
│                                                                 │
│  $4.99                                         [Buy Now]       │
│                                              [★ Favorite]      │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  [Cover Image]                                                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ [Screenshot 1] [Screenshot 2] [Screenshot 3]          │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Description                                                    │
│  ─────────────                                                  │
│  This template is designed to automatically find and fix bugs  │
│  in your codebase. It uses a systematic approach to identify    │
│  common bug patterns and fix them.                              │
│                                                                 │
│  Features:                                                      │
│  • Automatic bug detection                                      │
│  • Safe refactoring                                            │
│  • Test verification                                           │
│  • Detailed reports                                            │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  What's Included                                                │
│  ─────────────                                                  │
│  ✓ Pre-configured goal: "Fix all bugs in the repository"       │
│  ✓ Custom tool set for bug detection                           │
│  ✓ Claude Opus for detailed analysis                           │
│  ✓ Full source code included                                   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Reviews (124)                                                  │
│  ─────────────                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ★★★★★ "Exactly what I needed!" — @user1, 2 days ago   │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ★★★★☆ "Great template, saved me hours" — @user2        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  More by @dev123                                               │
│  ─────────────                                                  │
│  [🐛 Bug Fixer Pro] [⚡ Feature Kit] [📝 Docs Helper]          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### /store/create — Submit Template

```
┌─────────────────────────────────────────────────────────────────┐
│  Submit Your Template                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Basic Info                                                    │
│  ───────────                                                    │
│  Name: [Bug Fixer Pro________________]                         │
│  Tagline: [Automatically find and fix bugs________]            │
│  Category: [Bug Fixing ▼]                                      │
│  Tags: [bug-fixing] [python] [debugging] [+Add]              │
│                                                                 │
│  Description (Markdown supported)                               │
│  ─────────────────────────────────────────                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ This template is designed to...                        │   │
│  │                                                         │   │
│  │ # Features                                              │   │
│  │ - Feature 1                                            │   │
│  │ - Feature 2                                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Icon: [🤖 ▼]  Cover Image: [Upload]                           │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Configuration                                                  │
│  ─────────────                                                  │
│  Default Goal: [Fix all bugs in the repository__________]     │
│                                                                 │
│  Tools:                                                         │
│  [✓] FileProcessor    [✓] DataScraper    [ ] ProcessManager   │
│  [✓] GitHelper        [✓] DockerHelper   [ ] ApiClient        │
│                                                                 │
│  Claude Model: [Opus ▼]                                        │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Pricing                                                        │
│  ──────                                                        │
│  Price: [$0.00 ▼] (0 = free)                                  │
│  License: [MIT ▼]                                              │
│  [✓] Include full source code                                  │
│                                                                 │
│                                          [Save Draft] [Publish] │
└─────────────────────────────────────────────────────────────────┘
```

---

## Seller Dashboard

### /store/manage — My Templates

```
┌─────────────────────────────────────────────────────────────────┐
│  Seller Dashboard                           [Become a Seller]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Earnings Summary                                               │
│  ───────────────                                                │
│  Total Earnings: $1,234.56          Pending: $89.99            │
│  This Month: $234.56              Templates Sold: 456          │
│                                                                 │
│  [+ New Template]                                                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  My Templates                                                   │
│  ─────────────                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 🐛 Bug Fixer Pro    [Published]  $4.99   124 sales     │   │
│  │                    [Edit] [Stats] [Unpublish]           │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ⚡ Feature Kit       [Draft]     Free    —              │   │
│  │                    [Edit] [Publish] [Delete]           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Recent Sales                                                   │
│  ─────────────                                                  │
│  🐛 Bug Fixer Pro → @buyer123 — $4.99 — 2 hours ago          │
│  🐛 Bug Fixer Pro → @buyer456 — $4.99 — 5 hours ago          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Payment Flow

### Purchase Flow (Stripe)

```
1. User clicks "Buy Now"
   ↓
2. Create Stripe Checkout Session
   POST /api/store/templates/:id/purchase
   → { sessionId, checkoutUrl }
   ↓
3. Redirect to Stripe Checkout
   ↓
4. User completes payment
   ↓
5. Stripe webhook: payment_intent.succeeded
   → Create Purchase record
   → Unlock template for user
   → Credit seller (minus platform fee)
   ↓
6. Redirect to /store/purchases/:id
   → Show "Download" button + config
```

### Platform Fees

| Seller Tier | Platform Fee | Payout |
|-------------|--------------|--------|
| Default | 15% | Weekly (min $10) |
| Pro Seller (100+ sales) | 10% | Weekly (min $10) |
| Partner (500+ sales) | 5% | Daily |

---

## Rating & Review System

```typescript
// Only allow reviews after purchase
// One review per user per template
// Reviews are permanent (can edit, not delete after 30 days)
// Rating affects template visibility

interface Review {
  id: string;
  templateId: string;
  userId: string;
  rating: 1 | 2 | 3 | 4 | 5;
  title?: string;
  content?: string;
  createdAt: Date;
  updatedAt: Date;
}
```

---

## Discovery & Search

### Search

```sql
-- Full-text search
SELECT * FROM templates
WHERE status = 'published'
  AND (
    name ILIKE '%query%' OR
    tagline ILIKE '%query%' OR
    description ILIKE '%query%' OR
    tags @> '["query"]'
  )
ORDER BY downloads DESC;
```

### Trending Algorithm

```typescript
// Popularity score based on:
// - Downloads (30%)
// - Recent purchases (40%)
// - Rating (20%)
// - Review count (10%)

function trendingScore(template: Template): number {
  const dlScore = Math.log1p(template.downloads) / 10;
  const purchaseScore = Math.log1p(template.recentPurchases) / 5;
  const ratingScore = template.rating / 5;
  const reviewScore = Math.log1p(template.ratingCount) / 3;

  return (purchaseScore * 0.4) + (dlScore * 0.3) +
         (ratingScore * 0.2) + (reviewScore * 0.1);
}
```

---

## Implementation Priority

| Phase | Features | Effort |
|-------|----------|--------|
| **Phase 1** | Templates CRUD, listing, search, categories | 1 week |
| **Phase 2** | Purchases, Stripe integration, seller dashboard | 1 week |
| **Phase 3** | Reviews, ratings, favorites, wishlist | 3 days |
| **Phase 4** | Advanced search, recommendations, analytics | 1 week |
| **Phase 5** | Seller tiers, promotions, featured listings | 1 week |

---

## Tech Stack

- **Frontend:** React + TailwindCSS + React Query
- **Backend:** Node.js + Express (or add to existing server)
- **Database:** PostgreSQL (extend existing)
- **Payments:** Stripe Connect (for marketplace)
- **Storage:** S3 or existing storage for images
- **Search:** PostgreSQL full-text search (or Meilisearch later)
