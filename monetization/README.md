# CC-Claw Monetization System

## Overview

Three-tier monetization model:
1. **FREE** — Base usage with rate limits
2. **PRO** — Enhanced features + higher limits ($9/month)
3. **ENTERPRISE** — Unlimited + custom services ($49/month or custom)

---

## Tier Comparison

| Feature | FREE | PRO | ENTERPRISE |
|---------|------|-----|------------|
| **Rate Limit** | 60 req/min | 300 req/min | Unlimited |
| **Active Goals** | 1 | 5 | Unlimited |
| **Tools** | Basic (5) | All (8) + Custom | All + Private |
| **History** | 7 days | 30 days | Unlimited |
| **API Access** | ❌ | ✅ | ✅ |
| **Priority Support** | ❌ | ✅ | ✅ |
| **Custom Bot** | ❌ | ❌ | ✅ |
| **On-premise Deploy** | ❌ | ❌ | ✅ |
| **SLA** | ❌ | ❌ | 99.9% |

---

## Pro Features

### Feature List

```typescript
const PRO_FEATURES = {
  // Execution
  rateLimit: 300,                    // requests per minute
  activeGoals: 5,                    // concurrent goals
  goalHistory: 30 * 24 * 60 * 60,   // 30 days in seconds

  // Tools
  tools: {
    basic: true,                     // FileProcessor, DataScraper, ApiClient, ProcessManager, GitHelper
    advanced: true,                  // SystemInfo, DockerHelper + AgentSolveHub
    custom: false,                   // Custom tool support
    privateTools: false,             // Private tool registry
  },

  // API
  api: {
    enabled: true,                   // REST API access
    endpoints: ['all'],              // All endpoints
    webhooks: true,                  // Webhook support
    customIntegration: false,        // Custom integrations
  },

  // Support
  support: {
    priority: true,                  // Priority queue
    email: true,                     // Email support
    discord: true,                   // Discord PRO channel
    sla: false,                      // SLA guarantee
  },

  // Branding
  branding: {
    removeWatermark: true,           // Remove "Powered by CC-Claw"
    customLogo: false,               // Custom logo in bot
  },
};
```

### Pro Badge & UI

- PRO badge next to username in bot
- PRO-only features shown with lock icon
- Upgrade prompt when FREE user hits limits

---

## API Billing System

### Usage Tracking

```typescript
interface UsageRecord {
  id: string;
  userId: string;
  tier: 'FREE' | 'PRO' | 'ENTERPRISE';
  metric: 'requests' | 'tokens' | 'goals' | 'storage';
  count: number;
  period: 'minute' | 'hour' | 'day' | 'month';
  timestamp: Date;
  cost: number;           // In cents
}
```

### Billing Cycle

- **Monthly subscription**: Billed on 1st of each month
- **Usage-based**: API calls beyond tier limit (PRO only, $0.001/call)
- **Overage protection**: Max $5/month overage cap

### API Keys

```typescript
interface ApiKey {
  id: string;
  userId: string;
  key: string;             // sk_live_xxxx
  name: string;           // "Production", "Development"
  tier: 'PRO' | 'ENTERPRISE';
  permissions: string[];  // ['read', 'write', 'admin']
  rateLimit: number;
  lastUsed: Date;
  createdAt: Date;

  // Usage
  requestsToday: number;
  requestsThisMonth: number;
}
```

---

## Enterprise Tier

### Enterprise Features

```typescript
const ENTERPRISE_FEATURES = {
  // Everything in PRO, plus:
  execution: {
    unlimitedRequests: true,
    unlimitedGoals: true,
    customModels: true,              // Fine-tuned models
    on-premiseDeploy: true,         // Self-hosted option
    airGapped: true,               // No cloud connection required
  },

  tools: {
    custom: true,                   // Build custom tools
    privateTools: true,            // Private tool registry
    toolWhitelist: true,           // Restrict available tools
  },

  api: {
    customIntegration: true,        // Custom API integrations
    webhookFiltering: true,        // Advanced webhook config
    auditLog: true,                // Full audit trail
    samlSso: true,                 // SSO integration
  },

  support: {
    sla: '99.9%',                  // SLA guarantee
    dedicatedManager: true,        // Dedicated account manager
    customTraining: true,          // Team training
    priorityBugs: true,           // P0 bugs in 4 hours
  },

  branding: {
    customLogo: true,              // Branded bot
    whiteLabel: true,             // Fully white-labeled
  },
};
```

### Enterprise Pricing

| Plan | Monthly | Annual | Includes |
|------|---------|--------|----------|
| **Startup** | $49/user | $39/user | Everything in ENTERPRISE |
| **Business** | $99/user | $79/user | + Dedicated infra |
| **Enterprise** | Custom | Custom | + On-premise + SLA |

**Minimum:** 5 users for Business tier

---

## Implementation Files

```
/monetization/
├── server/
│   ├── src/
│   │   ├── routes/
│   │   │   ├── billing.ts      # Billing API routes
│   │   │   └── subscriptions.ts # Subscription management
│   │   ├── services/
│   │   │   ├── stripe.ts       # Stripe integration
│   │   │   ├── billing.ts      # Billing logic
│   │   │   └── usage.ts        # Usage tracking
│   │   └── middleware/
│   │       └── tierCheck.ts    # Tier-based access control
│   └── shared/
│       └── types.ts            # Shared types
└── README.md
```

---

## Stripe Integration

### Products & Prices

```
Stripe Products:
├── CC-Claw PRO
│   ├── Price: $9/month
│   └── Interval: month
├── CC-Claw PRO Annual
│   ├── Price: $90/year ($7.50/month)
│   └── Interval: year
└── CC-Claw Enterprise
    ├── Custom pricing
    └── Contact sales
```

### Webhook Events

```typescript
// Handled events
const WEBHOOK_EVENTS = [
  'checkout.session.completed',    // New subscription
  'customer.subscription.updated', // Tier change
  'customer.subscription.deleted', // Cancellation
  'invoice.payment_succeeded',     // Payment successful
  'invoice.payment_failed',         // Payment failed
  'usage_record.created',           // API usage overage
];
```

---

## Database Schema Additions

```sql
-- Subscriptions
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    stripe_subscription_id VARCHAR(255),
    stripe_customer_id VARCHAR(255),
    tier VARCHAR(20) DEFAULT 'FREE',
    status VARCHAR(20) DEFAULT 'active',
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Usage records
CREATE TABLE usage_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    metric VARCHAR(50) NOT NULL,
    count INTEGER NOT NULL,
    period VARCHAR(20) NOT NULL,
    cost INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- API keys
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    key VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(100),
    tier VARCHAR(20) DEFAULT 'PRO',
    permissions JSONB DEFAULT '["read"]',
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX subscriptions_user_idx ON subscriptions(user_id);
CREATE INDEX usage_records_user_idx ON usage_records(user_id);
CREATE INDEX usage_records_period_idx ON usage_records(period, created_at);
CREATE INDEX api_keys_key_idx ON api_keys(key);
```
