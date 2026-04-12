/**
 * CC-Claw Tier-Based Access Control Middleware
 */

import { Request, Response, NextFunction } from 'express';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

// =====================================================
// TIER CONSTANTS
// =====================================================

const FEATURES = {
  FREE: {
    rateLimit: 60,
    activeGoals: 1,
    historyDays: 7,
    tools: ['file', 'scraper', 'api', 'process', 'git'],
    apiAccess: false,
    webhookAccess: false,
    prioritySupport: false,
    customBranding: false,
    onPremise: false,
  },
  PRO: {
    rateLimit: 300,
    activeGoals: 5,
    historyDays: 30,
    tools: ['file', 'scraper', 'api', 'process', 'git', 'system', 'docker', 'agentsolvehub'],
    apiAccess: true,
    webhookAccess: true,
    prioritySupport: true,
    customBranding: false,
    onPremise: false,
  },
  ENTERPRISE: {
    rateLimit: Infinity,
    activeGoals: Infinity,
    historyDays: 365,
    tools: ['file', 'scraper', 'api', 'process', 'git', 'system', 'docker', 'agentsolvehub', 'custom'],
    apiAccess: true,
    webhookAccess: true,
    prioritySupport: true,
    customBranding: true,
    onPremise: true,
  },
};

type Tier = keyof typeof FEATURES;
type Feature = keyof typeof FEATURES.PRO;

// =====================================================
// HELPERS
// =====================================================

export const getUserTier = async (userId: string): Promise<Tier> => {
  const subscription = await prisma.subscriptions.findFirst({
    where: { userId, status: 'active' },
    orderBy: { createdAt: 'desc' },
  });

  if (!subscription) return 'FREE';

  // Check if subscription is still valid
  if (subscription.currentPeriodEnd && subscription.currentPeriodEnd < new Date()) {
    return 'FREE';
  }

  return (subscription.tier as Tier) || 'FREE';
};

export const hasFeature = async (userId: string, feature: Feature): Promise<boolean> => {
  const tier = await getUserTier(userId);
  return FEATURES[tier][feature] === true;
};

export const getRateLimit = async (userId: string): Promise<number> => {
  const tier = await getUserTier(userId);
  return FEATURES[tier].rateLimit;
};

// =====================================================
// MIDDLEWARE FACTORIES
// =====================================================

/**
 * Require a minimum tier to access the route
 * Usage: requireTier('PRO')(req, res, next)
 */
export const requireTier = (minTier: Tier) => {
  return async (req: Request, res: Response, next: NextFunction) => {
    const userId = req.headers.authorization?.replace('Bearer ', '');

    if (!userId) {
      return res.status(401).json({
        success: false,
        error: 'Authentication required',
      });
    }

    const userTier = await getUserTier(userId);
    const tierOrder: Tier[] = ['FREE', 'PRO', 'ENTERPRISE'];

    const userTierIndex = tierOrder.indexOf(userTier);
    const minTierIndex = tierOrder.indexOf(minTier);

    if (userTierIndex < minTierIndex) {
      return res.status(403).json({
        success: false,
        error: `${minTier} tier required`,
        currentTier: userTier,
        upgradeUrl: '/billing?upgrade=' + minTier.toLowerCase(),
      });
    }

    // Attach tier info to request for downstream use
    (req as any).userTier = userTier;
    (req as any).tierFeatures = FEATURES[userTier];

    next();
  };
};

/**
 * Require a specific tool to be enabled
 * Usage: requireTool('docker')(req, res, next)
 */
export const requireTool = (toolName: string) => {
  return async (req: Request, res: Response, next: NextFunction) => {
    const userId = req.headers.authorization?.replace('Bearer ', '');

    if (!userId) {
      return res.status(401).json({
        success: false,
        error: 'Authentication required',
      });
    }

    const tier = await getUserTier(userId);
    const tools = FEATURES[tier].tools;

    if (!tools.includes(toolName) && !tools.includes('custom')) {
      return res.status(403).json({
        success: false,
        error: `${toolName} tool requires PRO tier`,
        upgradeUrl: '/billing?upgrade=pro',
      });
    }

    next();
  };
};

/**
 * Check rate limit for user
 * Usage: checkRateLimit()(req, res, next)
 */
export const checkRateLimit = () => {
  return async (req: Request, res: Response, next: NextFunction) => {
    const userId = req.headers.authorization?.replace('Bearer ', '');
    const apiKey = req.headers['x-api-key'] as string;

    // Use API key user or header user
    let effectiveUserId = userId;

    if (apiKey && !userId) {
      const keyRecord = await prisma.apiKeys.findUnique({
        where: { key: apiKey },
      });
      effectiveUserId = keyRecord?.userId;
    }

    if (!effectiveUserId) {
      return res.status(401).json({
        success: false,
        error: 'Authentication required',
      });
    }

    const rateLimit = await getRateLimit(effectiveUserId);

    // Get current usage for this minute
    const minuteAgo = new Date(Date.now() - 60000);

    const usage = await prisma.usageRecords.aggregate({
      where: {
        userId: effectiveUserId,
        period: 'minute',
        createdAt: { gte: minuteAgo },
      },
      _sum: { count: true },
    });

    const currentCount = usage._sum.count || 0;

    // Add rate limit headers
    res.setHeader('X-RateLimit-Limit', rateLimit);
    res.setHeader('X-RateLimit-Remaining', Math.max(0, rateLimit - currentCount));
    res.setHeader('X-RateLimit-Reset', Math.ceil(Date.now() / 60000) * 60);

    if (currentCount >= rateLimit) {
      return res.status(429).json({
        success: false,
        error: 'Rate limit exceeded',
        currentTier: await getUserTier(effectiveUserId),
        upgradeUrl: '/billing?upgrade=pro',
        retryAfter: 60, // seconds
      });
    }

    // Record usage
    await prisma.usageRecords.create({
      data: {
        userId: effectiveUserId,
        metric: 'requests',
        count: 1,
        period: 'minute',
      },
    });

    next();
  };
};

/**
 * Require API key for access
 * Usage: requireApiKey()(req, res, next)
 */
export const requireApiKey = () => {
  return async (req: Request, res: Response, next: NextFunction) => {
    const apiKey = req.headers['x-api-key'] as string;

    if (!apiKey) {
      return res.status(401).json({
        success: false,
        error: 'API key required. Include X-API-Key header.',
      });
    }

    const keyRecord = await prisma.apiKeys.findUnique({
      where: { key: apiKey },
    });

    if (!keyRecord) {
      return res.status(401).json({
        success: false,
        error: 'Invalid API key',
      });
    }

    // Update last used
    await prisma.apiKeys.update({
      where: { id: keyRecord.id },
      data: { lastUsedAt: new Date() },
    });

    // Attach API key info to request
    (req as any).apiKey = keyRecord;
    (req as any).userTier = keyRecord.tier;
    (req as any).tierFeatures = FEATURES[keyRecord.tier as Tier];

    next();
  };
};

// =====================================================
// TIER INFO MIDDLEWARE
// =====================================================

/**
 * Attach tier info to all requests (for UI display)
 * Usage: attachTierInfo()(req, res, next)
 */
export const attachTierInfo = () => {
  return async (req: Request, res: Response, next: NextFunction) => {
    const userId = req.headers.authorization?.replace('Bearer ', '');

    if (!userId) {
      (req as any).tierInfo = {
        tier: 'FREE',
        ...FEATURES.FREE,
      };
      return next();
    }

    const tier = await getUserTier(userId);

    (req as any).tierInfo = {
      tier,
      ...FEATURES[tier],
    };

    next();
  };
};

// =====================================================
// UPGRADE PROMPTS
// =====================================================

export const getUpgradePrompt = (tier: Tier, feature: string) => {
  const prompts: Record<string, string> = {
    tool: `${feature} requires PRO tier. Upgrade to unlock all tools.`,
    rateLimit: 'Rate limit reached. Upgrade to PRO for 5x more requests.',
    api: 'API access requires PRO tier. Upgrade to get your API key.',
    goals: 'Maximum goals reached. Upgrade to PRO for 5 concurrent goals.',
  };

  return prompts[feature] || 'Upgrade to PRO for more features.';
};

// =====================================================
// FEATURE FLAGS (for gradual rollouts)
// =====================================================

export const isFeatureEnabled = async (
  userId: string,
  feature: string,
  percentage: number = 100
): Promise<boolean> => {
  // For gradual rollouts, check user ID hash
  const hash = userId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return (hash % 100) < percentage;
};
