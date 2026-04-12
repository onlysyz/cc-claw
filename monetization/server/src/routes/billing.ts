/**
 * CC-Claw Billing Routes
 * /api/billing/*
 */

import { Router, Request, Response } from 'express';
import { body, query, validationResult } from 'express-validator';
import Stripe from 'stripe';
import { PrismaClient } from '@prisma/client';

const router = Router();
const prisma = new PrismaClient();

// Initialize Stripe (use env variable in production)
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || 'sk_test_placeholder', {
  apiVersion: '2023-10-16',
});

// =====================================================
// CONSTANTS
// =====================================================

const TIERS = {
  FREE: {
    name: 'Free',
    price: 0,
    rateLimit: 60,
    activeGoals: 1,
    historyDays: 7,
    tools: ['file', 'scraper', 'api', 'process', 'git'],
    apiEnabled: false,
    prioritySupport: false,
  },
  PRO: {
    name: 'Pro',
    price: 900, // $9 in cents
    priceAnnual: 9000, // $90 in cents
    rateLimit: 300,
    activeGoals: 5,
    historyDays: 30,
    tools: ['file', 'scraper', 'api', 'process', 'git', 'system', 'docker', 'agentsolvehub'],
    apiEnabled: true,
    prioritySupport: true,
  },
  ENTERPRISE: {
    name: 'Enterprise',
    price: 4900, // $49 in cents
    rateLimit: Infinity,
    activeGoals: Infinity,
    historyDays: 365,
    tools: ['all'],
    apiEnabled: true,
    prioritySupport: true,
    dedicatedSupport: true,
    customBranding: true,
    onPremise: true,
  },
};

const TIER_ORDER = ['FREE', 'PRO', 'ENTERPRISE'];

// =====================================================
// HELPERS
// =====================================================

const getTierFromSubscription = async (userId: string): Promise<keyof typeof TIERS> => {
  const subscription = await prisma.subscriptions.findFirst({
    where: { userId, status: 'active' },
    orderBy: { createdAt: 'desc' },
  });

  if (!subscription) return 'FREE';

  const tierIndex = TIER_ORDER.indexOf(subscription.tier as keyof typeof TIERS);
  if (tierIndex === -1) return 'FREE';

  // Check if subscription is still valid
  if (subscription.currentPeriodEnd && subscription.currentPeriodEnd < new Date()) {
    return 'FREE';
  }

  return subscription.tier as keyof typeof TIERS;
};

const formatCurrency = (cents: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(cents / 100);
};

// =====================================================
// TIER INFO
// =====================================================

/**
 * GET /api/billing/tiers
 * Get all available tiers
 */
router.get('/tiers', async (req: Request, res: Response) => {
  try {
    const tiers = Object.entries(TIERS).map(([key, tier]) => ({
      id: key,
      name: tier.name,
      price: tier.price,
      priceFormatted: formatCurrency(tier.price),
      priceAnnual: tier.priceAnnual,
      priceAnnualFormatted: tier.priceAnnual ? formatCurrency(tier.priceAnnual) : null,
      features: {
        rateLimit: tier.rateLimit === Infinity ? 'Unlimited' : `${tier.rateLimit} req/min`,
        activeGoals: tier.activeGoals === Infinity ? 'Unlimited' : tier.activeGoals,
        historyDays: tier.historyDays,
        tools: tier.tools,
        apiEnabled: tier.apiEnabled,
        prioritySupport: tier.prioritySupport,
        dedicatedSupport: tier.dedicatedSupport || false,
        customBranding: tier.customBranding || false,
        onPremise: tier.onPremise || false,
      },
    }));

    res.json({ success: true, data: tiers });
  } catch (error) {
    console.error('Error getting tiers:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

// =====================================================
// SUBSCRIPTIONS
// =====================================================

/**
 * GET /api/billing/subscription
 * Get current user's subscription
 */
router.get('/subscription', async (req: Request, res: Response) => {
  try {
    const userId = req.headers.authorization?.replace('Bearer ', '');
    if (!userId) {
      return res.status(401).json({ success: false, error: 'Unauthorized' });
    }

    const subscription = await prisma.subscriptions.findFirst({
      where: { userId },
      orderBy: { createdAt: 'desc' },
    });

    if (!subscription) {
      return res.json({
        success: true,
        data: {
          tier: 'FREE',
          subscription: null,
        },
      });
    }

    const tier = TIERS[subscription.tier as keyof typeof TIERS];

    res.json({
      success: true,
      data: {
        tier: subscription.tier,
        status: subscription.status,
        currentPeriodStart: subscription.currentPeriodStart,
        currentPeriodEnd: subscription.currentPeriodEnd,
        cancelAtPeriodEnd: subscription.cancelAtPeriodEnd,
        price: tier.price,
        priceFormatted: formatCurrency(tier.price),
      },
    });
  } catch (error) {
    console.error('Error getting subscription:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

/**
 * POST /api/billing/subscription/checkout
 * Create Stripe checkout session for PRO
 */
router.post('/subscription/checkout',
  body('tier').isIn(['PRO', 'ENTERPRISE']),
  body('interval').isIn(['month', 'year']),
  async (req: Request, res: Response) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ success: false, errors: errors.array() });
      }

      const userId = req.headers.authorization?.replace('Bearer ', '');
      if (!userId) {
        return res.status(401).json({ success: false, error: 'Unauthorized' });
      }

      const { tier, interval } = req.body;
      const tierInfo = TIERS[tier as keyof typeof TIERS];

      // Get or create Stripe customer
      const user = await prisma.users.findUnique({ where: { id: userId } });
      if (!user) {
        return res.status(404).json({ success: false, error: 'User not found' });
      }

      let customerId = user.stripeCustomerId;

      if (!customerId) {
        const customer = await stripe.customers.create({
          email: user.email,
          metadata: { userId: user.id },
        });
        customerId = customer.id;

        await prisma.users.update({
          where: { id: userId },
          data: { stripeCustomerId: customerId },
        });
      }

      // Create checkout session
      const session = await stripe.checkout.sessions.create({
        customer: customerId,
        payment_method_types: ['card'],
        line_items: [
          {
            price_data: {
              currency: 'usd',
              product_data: {
                name: `CC-Claw ${tier}`,
                description: `CC-Claw ${tier} subscription - ${interval === 'year' ? 'annual' : 'monthly'}`,
                images: ['https://cc-claw.dev/logo.png'],
              },
              unit_amount: interval === 'year' ? tierInfo.priceAnnual : tierInfo.price,
            },
            quantity: 1,
          },
        ],
        mode: 'subscription',
        subscription_data: {
          metadata: {
            userId,
            tier,
          },
        },
        success_url: `${process.env.APP_URL}/billing?success=true&session_id={CHECKOUT_SESSION_ID}`,
        cancel_url: `${process.env.APP_URL}/billing?canceled=true`,
        metadata: {
          userId,
          tier,
        },
      });

      res.json({ success: true, data: { checkoutUrl: session.url, sessionId: session.id } });
    } catch (error) {
      console.error('Error creating checkout session:', error);
      res.status(500).json({ success: false, error: 'Failed to create checkout session' });
    }
  }
);

/**
 * POST /api/billing/subscription/cancel
 * Cancel subscription
 */
router.post('/subscription/cancel', async (req: Request, res: Response) => {
  try {
    const userId = req.headers.authorization?.replace('Bearer ', '');
    if (!userId) {
      return res.status(401).json({ success: false, error: 'Unauthorized' });
    }

    const subscription = await prisma.subscriptions.findFirst({
      where: { userId, status: 'active' },
    });

    if (!subscription || !subscription.stripeSubscriptionId) {
      return res.status(404).json({ success: false, error: 'No active subscription' });
    }

    // Cancel at period end
    const updated = await stripe.subscriptions.update(
      subscription.stripeSubscriptionId,
      { cancel_at_period_end: true }
    );

    await prisma.subscriptions.update({
      where: { id: subscription.id },
      data: { cancelAtPeriodEnd: true },
    });

    res.json({
      success: true,
      data: {
        canceled: true,
        effectiveDate: new Date(updated.cancel_at).toISOString(),
      },
    });
  } catch (error) {
    console.error('Error canceling subscription:', error);
    res.status(500).json({ success: false, error: 'Failed to cancel subscription' });
  }
});

/**
 * POST /api/billing/subscription/reactivate
 * Reactivate a canceled subscription
 */
router.post('/subscription/reactivate', async (req: Request, res: Response) => {
  try {
    const userId = req.headers.authorization?.replace('Bearer ', '');
    if (!userId) {
      return res.status(401).json({ success: false, error: 'Unauthorized' });
    }

    const subscription = await prisma.subscriptions.findFirst({
      where: { userId, cancelAtPeriodEnd: true },
    });

    if (!subscription || !subscription.stripeSubscriptionId) {
      return res.status(404).json({ success: false, error: 'No canceled subscription' });
    }

    await stripe.subscriptions.update(subscription.stripeSubscriptionId, {
      cancel_at_period_end: false,
    });

    await prisma.subscriptions.update({
      where: { id: subscription.id },
      data: { cancelAtPeriodEnd: false },
    });

    res.json({ success: true, data: { reactivated: true } });
  } catch (error) {
    console.error('Error reactivating subscription:', error);
    res.status(500).json({ success: false, error: 'Failed to reactivate subscription' });
  }
});

// =====================================================
// USAGE
// =====================================================

/**
 * GET /api/billing/usage
 * Get current usage statistics
 */
router.get('/usage', async (req: Request, res: Response) => {
  try {
    const userId = req.headers.authorization?.replace('Bearer ', '');
    if (!userId) {
      return res.status(401).json({ success: false, error: 'Unauthorized' });
    }

    const tier = await getTierFromSubscription(userId);
    const tierInfo = TIERS[tier as keyof typeof TIERS];

    // Get today's usage
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const todayUsage = await prisma.usageRecords.aggregate({
      where: {
        userId,
        createdAt: { gte: today },
      },
      _sum: { count: true },
    });

    // Get this month's usage
    const monthStart = new Date();
    monthStart.setDate(1);
    monthStart.setHours(0, 0, 0, 0);

    const monthUsage = await prisma.usageRecords.aggregate({
      where: {
        userId,
        createdAt: { gte: monthStart },
        period: 'month',
      },
      _sum: { count: true },
    });

    res.json({
      success: true,
      data: {
        tier,
        rateLimit: tierInfo.rateLimit,
        requestsToday: todayUsage._sum.count || 0,
        requestsThisMonth: monthUsage._sum.count || 0,
        usagePercent: tierInfo.rateLimit === Infinity
          ? 0
          : ((todayUsage._sum.count || 0) / tierInfo.rateLimit) * 100,
      },
    });
  } catch (error) {
    console.error('Error getting usage:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

/**
 * GET /api/billing/history
 * Get billing history
 */
router.get('/history', async (req: Request, res: Response) => {
  try {
    const userId = req.headers.authorization?.replace('Bearer ', '');
    if (!userId) {
      return res.status(401).json({ success: false, error: 'Unauthorized' });
    }

    // Get invoices from Stripe
    const user = await prisma.users.findUnique({ where: { id: userId } });
    if (!user?.stripeCustomerId) {
      return res.json({ success: true, data: [] });
    }

    const invoices = await stripe.invoices.list({
      customer: user.stripeCustomerId,
      limit: 12,
    });

    const history = invoices.data.map((invoice) => ({
      id: invoice.id,
      amount: invoice.amount_paid,
      amountFormatted: formatCurrency(invoice.amount_paid),
      status: invoice.status,
      date: new Date(invoice.created * 1000).toISOString(),
      description: invoice.description || `CC-Claw ${invoice.lines.data[0]?.description || 'Subscription'}`,
      receiptUrl: invoice.invoice_pdf,
    }));

    res.json({ success: true, data: history });
  } catch (error) {
    console.error('Error getting billing history:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

// =====================================================
// API KEYS (PRO+)
// =====================================================

/**
 * GET /api/billing/api-keys
 * List user's API keys
 */
router.get('/api-keys', async (req: Request, res: Response) => {
  try {
    const userId = req.headers.authorization?.replace('Bearer ', '');
    if (!userId) {
      return res.status(401).json({ success: false, error: 'Unauthorized' });
    }

    const tier = await getTierFromSubscription(userId);
    if (tier === 'FREE') {
      return res.status(403).json({
        success: false,
        error: 'API access requires PRO or higher tier',
        upgradeUrl: '/billing?upgrade=pro',
      });
    }

    const keys = await prisma.apiKeys.findMany({
      where: { userId },
      select: {
        id: true,
        name: true,
        key: true,
        permissions: true,
        lastUsedAt: true,
        createdAt: true,
        requestsThisMonth: true,
      },
    });

    // Mask keys for display
    const maskedKeys = keys.map((k) => ({
      ...k,
      key: `sk_${k.key.slice(3, 8)}...${k.key.slice(-4)}`,
    }));

    res.json({ success: true, data: maskedKeys });
  } catch (error) {
    console.error('Error listing API keys:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

/**
 * POST /api/billing/api-keys
 * Create new API key
 */
router.post('/api-keys',
  body('name').isString().trim().notEmpty(),
  body('permissions').optional().isArray(),
  async (req: Request, res: Response) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ success: false, errors: errors.array() });
      }

      const userId = req.headers.authorization?.replace('Bearer ', '');
      if (!userId) {
        return res.status(401).json({ success: false, error: 'Unauthorized' });
      }

      const tier = await getTierFromSubscription(userId);
      if (tier === 'FREE') {
        return res.status(403).json({
          success: false,
          error: 'API access requires PRO or higher tier',
        });
      }

      const { name, permissions = ['read'] } = req.body;

      // Generate key
      const key = `sk_live_${Buffer.from(crypto.randomBytes(24)).toString('base64url')}`;

      const apiKey = await prisma.apiKeys.create({
        data: {
          userId,
          key,
          name,
          tier,
          permissions,
          rateLimit: tier === 'ENTERPRISE' ? Infinity : TIERS.PRO.rateLimit,
        },
      });

      res.status(201).json({
        success: true,
        data: {
          id: apiKey.id,
          name: apiKey.name,
          key: apiKey.key, // Return full key only on creation
          permissions: apiKey.permissions,
          tier: apiKey.tier,
        },
      });
    } catch (error) {
      console.error('Error creating API key:', error);
      res.status(500).json({ success: false, error: 'Internal server error' });
    }
  }
);

/**
 * DELETE /api/billing/api-keys/:id
 * Revoke API key
 */
router.delete('/api-keys/:id', async (req: Request, res: Response) => {
  try {
    const userId = req.headers.authorization?.replace('Bearer ', '');
    if (!userId) {
      return res.status(401).json({ success: false, error: 'Unauthorized' });
    }

    const { id } = req.params;

    await prisma.apiKeys.delete({
      where: { id, userId },
    });

    res.json({ success: true });
  } catch (error) {
    console.error('Error deleting API key:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

// =====================================================
// STRIPE WEBHOOKS
// =====================================================

/**
 * POST /api/billing/webhook
 * Handle Stripe webhooks
 */
router.post('/webhook',
  (req: Request, res: Response) => {
    const sig = req.headers['stripe-signature'] as string;

    let event: Stripe.Event;

    try {
      event = stripe.webhooks.constructEvent(
        req.body,
        sig,
        process.env.STRIPE_WEBHOOK_SECRET || ''
      );
    } catch (err: any) {
      console.error('Webhook signature verification failed:', err.message);
      return res.status(400).send(`Webhook Error: ${err.message}`);
    }

    // Handle the event
    switch (event.type) {
      case 'checkout.session.completed': {
        const session = event.data.object as Stripe.Checkout.Session;
        const userId = session.metadata?.userId;
        const tier = session.metadata?.tier as 'PRO' | 'ENTERPRISE';

        if (userId && tier) {
          // Create or update subscription
          prisma.subscriptions.upsert({
            where: { userId },
            create: {
              userId,
              stripeSubscriptionId: session.subscription as string,
              stripeCustomerId: session.customer as string,
              tier,
              status: 'active',
              currentPeriodStart: new Date(),
              currentPeriodEnd: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // Approximate
            },
            update: {
              stripeSubscriptionId: session.subscription as string,
              tier,
              status: 'active',
            },
          }).catch(console.error);
        }
        break;
      }

      case 'customer.subscription.updated': {
        const subscription = event.data.object as Stripe.Subscription;
        const userId = subscription.metadata?.userId;

        if (userId) {
          prisma.subscriptions.updateMany({
            where: { stripeSubscriptionId: subscription.id },
            data: {
              tier: (subscription.metadata?.tier || 'PRO') as string,
              status: subscription.status === 'active' ? 'active' : 'inactive',
              currentPeriodEnd: new Date(subscription.current_period_end * 1000),
              cancelAtPeriodEnd: subscription.cancel_at_period_end,
            },
          }).catch(console.error);
        }
        break;
      }

      case 'customer.subscription.deleted': {
        const subscription = event.data.object as Stripe.Subscription;

        prisma.subscriptions.updateMany({
          where: { stripeSubscriptionId: subscription.id },
          data: {
            status: 'canceled',
            cancelAtPeriodEnd: false,
          },
        }).catch(console.error);
        break;
      }

      case 'invoice.payment_failed': {
        const invoice = event.data.object as Stripe.Invoice;
        const customerId = invoice.customer as string;

        // Find user and mark subscription as past_due
        prisma.subscriptions.updateMany({
          where: { stripeCustomerId: customerId },
          data: { status: 'past_due' },
        }).catch(console.error);
        break;
      }

      default:
        console.log(`Unhandled event type: ${event.type}`);
    }

    res.json({ received: true });
  }
);

export default router;
