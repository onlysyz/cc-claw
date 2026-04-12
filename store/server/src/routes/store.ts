/**
 * CC-Claw Agent Store API Routes
 * /api/store/*
 */

import { Router, Request, Response } from 'express';
import { body, query, validationResult } from 'express-validator';
import { PrismaClient } from '@prisma/client';

const router = Router();
const prisma = new PrismaClient();

// =====================================================
// MIDDLEWARE
// =====================================================

// All routes require authentication
const requireAuth = async (req: Request, res: Response, next: Function) => {
  // TODO: Implement actual auth check
  // For now, we'll use a placeholder
  if (!req.headers.authorization) {
    return res.status(401).json({ success: false, error: 'Unauthorized' });
  }
  next();
};

// =====================================================
// TEMPLATES - LIST & SEARCH
// =====================================================

/**
 * GET /api/store/templates
 * List templates with filtering, sorting, pagination
 */
router.get('/templates',
  query('category').optional().isString(),
  query('tags').optional().isArray(),
  query('price_min').optional().isInt({ min: 0 }),
  query('price_max').optional().isInt({ min: 0 }),
  query('sort').optional().isIn(['downloads', 'rating', 'newest', 'price_asc', 'price_desc']),
  query('page').optional().isInt({ min: 1 }),
  query('limit').optional().isInt({ min: 1, max: 50 }),
  query('q').optional().isString(),
  async (req: Request, res: Response) => {
    try {
      const {
        category,
        tags,
        price_min,
        price_max,
        sort = 'downloads',
        page = '1',
        limit = '20',
        q
      } = req.query;

      const pageNum = parseInt(page as string);
      const limitNum = parseInt(limit as string);
      const skip = (pageNum - 1) * limitNum;

      // Build where clause
      const where: any = { status: 'published' };

      if (category) {
        where.category = category;
      }

      if (tags && Array.isArray(tags)) {
        where.tags = { hasSome: tags };
      }

      if (price_min !== undefined || price_max !== undefined) {
        where.price = {};
        if (price_min !== undefined) {
          where.price.gte = parseInt(price_min as string);
        }
        if (price_max !== undefined) {
          where.price.lte = parseInt(price_max as string);
        }
      }

      if (q) {
        where.OR = [
          { name: { contains: q as string, mode: 'insensitive' } },
          { tagline: { contains: q as string, mode: 'insensitive' } },
          { description: { contains: q as string, mode: 'insensitive' } },
        ];
      }

      // Build orderBy
      let orderBy: any = { downloads: 'desc' };
      switch (sort) {
        case 'rating':
          orderBy = { rating: 'desc' };
          break;
        case 'newest':
          orderBy = { publishedAt: 'desc' };
          break;
        case 'price_asc':
          orderBy = { price: 'asc' };
          break;
        case 'price_desc':
          orderBy = { price: 'desc' };
          break;
      }

      // Query templates
      const [templates, total] = await Promise.all([
        prisma.templates.findMany({
          where,
          orderBy,
          skip,
          take: limitNum,
          select: {
            id: true,
            slug: true,
            name: true,
            tagline: true,
            category: true,
            tags: true,
            icon: true,
            price: true,
            currency: true,
            downloads: true,
            rating: true,
            ratingCount: true,
            author: {
              select: {
                id: true,
                username: true,
                name: true,
                avatarUrl: true,
              }
            },
            createdAt: true,
            publishedAt: true,
          }
        }),
        prisma.templates.count({ where }),
      ]);

      // Get category counts
      const categoryCounts = await prisma.templates.groupBy({
        by: ['category'],
        where: { status: 'published' },
        _count: { id: true },
      });

      const categories = categoryCounts.map(cc => ({
        value: cc.category,
        count: cc._count.id,
      }));

      res.json({
        success: true,
        data: {
          templates,
          pagination: {
            page: pageNum,
            limit: limitNum,
            total,
            pages: Math.ceil(total / limitNum),
          },
          filters: {
            categories,
          },
        },
      });
    } catch (error) {
      console.error('Error listing templates:', error);
      res.status(500).json({ success: false, error: 'Internal server error' });
    }
  }
);

// =====================================================
// TEMPLATES - SINGLE
// =====================================================

/**
 * GET /api/store/templates/:slug
 * Get template by slug
 */
router.get('/templates/:slug', async (req: Request, res: Response) => {
  try {
    const { slug } = req.params;
    const userId = req.headers.authorization?.replace('Bearer ', '');

    const template = await prisma.templates.findUnique({
      where: { slug },
      include: {
        author: {
          select: {
            id: true,
            username: true,
            name: true,
            avatarUrl: true,
            _count: {
              select: {
                templates: { where: { status: 'published' } },
              }
            }
          }
        },
      },
    });

    if (!template || template.status !== 'published') {
      return res.status(404).json({ success: false, error: 'Template not found' });
    }

    // Check if user has purchased
    let isPurchased = false;
    let isFavorited = false;

    if (userId) {
      const purchase = await prisma.purchases.findUnique({
        where: {
          templateId_userId: {
            templateId: template.id,
            userId,
          }
        }
      });
      isPurchased = !!purchase;

      const favorite = await prisma.favorites.findUnique({
        where: {
          userId_templateId: {
            userId,
            templateId: template.id,
          }
        }
      });
      isFavorited = !!favorite;
    }

    // Don't show full config if not purchased and not free
    const config = (isPurchased || template.price === 0)
      ? template.config
      : { preview: true, config: null };

    res.json({
      success: true,
      data: {
        ...template,
        config,
        isPurchased,
        isFavorited,
        author: {
          ...template.author,
          templateCount: template.author._count.templates,
        },
      },
    });
  } catch (error) {
    console.error('Error getting template:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

// =====================================================
// TEMPLATES - CREATE / UPDATE / DELETE
// =====================================================

/**
 * POST /api/store/templates
 * Create a new template
 */
router.post('/templates',
  requireAuth,
  body('name').isString().trim().notEmpty(),
  body('tagline').isString().trim(),
  body('category').isString(),
  body('config').isObject(),
  async (req: Request, res: Response) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ success: false, errors: errors.array() });
      }

      const userId = req.headers.authorization?.replace('Bearer ', '');
      const { name, tagline, description, category, tags, icon, config, price, license } = req.body;

      // Generate slug
      const baseSlug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
      const slug = `${baseSlug}-${Date.now().toString(36)}`;

      const template = await prisma.templates.create({
        data: {
          slug,
          name,
          tagline,
          description: description || '',
          category,
          tags: tags || [],
          icon: icon || '🤖',
          config,
          price: price || 0,
          currency: 'USD',
          license: license || 'MIT',
          sourceIncluded: true,
          authorId: userId,
          status: 'draft',
        }
      });

      res.status(201).json({ success: true, data: template });
    } catch (error) {
      console.error('Error creating template:', error);
      res.status(500).json({ success: false, error: 'Internal server error' });
    }
  }
);

/**
 * PUT /api/store/templates/:id
 * Update template
 */
router.put('/templates/:id', requireAuth, async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const userId = req.headers.authorization?.replace('Bearer ', '');

    // Check ownership
    const existing = await prisma.templates.findUnique({ where: { id } });
    if (!existing) {
      return res.status(404).json({ success: false, error: 'Template not found' });
    }
    if (existing.authorId !== userId) {
      return res.status(403).json({ success: false, error: 'Forbidden' });
    }

    const { name, tagline, description, category, tags, icon, config, price, license, status } = req.body;

    const template = await prisma.templates.update({
      where: { id },
      data: {
        ...(name && { name }),
        ...(tagline !== undefined && { tagline }),
        ...(description !== undefined && { description }),
        ...(category && { category }),
        ...(tags && { tags }),
        ...(icon && { icon }),
        ...(config && { config }),
        ...(price !== undefined && { price }),
        ...(license && { license }),
        ...(status === 'published' && { publishedAt: new Date() }),
      },
    });

    res.json({ success: true, data: template });
  } catch (error) {
    console.error('Error updating template:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

/**
 * DELETE /api/store/templates/:id
 * Delete template
 */
router.delete('/templates/:id', requireAuth, async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const userId = req.headers.authorization?.replace('Bearer ', '');

    const existing = await prisma.templates.findUnique({ where: { id } });
    if (!existing) {
      return res.status(404).json({ success: false, error: 'Template not found' });
    }
    if (existing.authorId !== userId) {
      return res.status(403).json({ success: false, error: 'Forbidden' });
    }

    await prisma.templates.delete({ where: { id } });

    res.json({ success: true });
  } catch (error) {
    console.error('Error deleting template:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

/**
 * POST /api/store/templates/:id/publish
 * Publish template
 */
router.post('/templates/:id/publish', requireAuth, async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const userId = req.headers.authorization?.replace('Bearer ', '');

    const existing = await prisma.templates.findUnique({ where: { id } });
    if (!existing) {
      return res.status(404).json({ success: false, error: 'Template not found' });
    }
    if (existing.authorId !== userId) {
      return res.status(403).json({ success: false, error: 'Forbidden' });
    }

    const template = await prisma.templates.update({
      where: { id },
      data: {
        status: 'published',
        publishedAt: new Date(),
      },
    });

    res.json({ success: true, data: template });
  } catch (error) {
    console.error('Error publishing template:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

// =====================================================
// TEMPLATES - DOWNLOAD / PURCHASE
// =====================================================

/**
 * GET /api/store/templates/:id/download
 * Download template (if purchased or free)
 */
router.get('/templates/:id/download', requireAuth, async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const userId = req.headers.authorization?.replace('Bearer ', '');

    const template = await prisma.templates.findUnique({ where: { id } });
    if (!template || template.status !== 'published') {
      return res.status(404).json({ success: false, error: 'Template not found' });
    }

    // Check if free or purchased
    if (template.price > 0) {
      const purchase = await prisma.purchases.findUnique({
        where: {
          templateId_userId: { templateId: id, userId },
        }
      });
      if (!purchase) {
        return res.status(403).json({ success: false, error: 'Purchase required' });
      }
    }

    // Record download for free templates
    if (template.price === 0) {
      await prisma.templateDownloads.create({
        data: {
          templateId: id,
          userId,
        }
      });
    }

    res.json({
      success: true,
      data: {
        id: template.id,
        slug: template.slug,
        name: template.name,
        config: template.config,
        files: template.sourceIncluded ? template.config.files : undefined,
      },
    });
  } catch (error) {
    console.error('Error downloading template:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

/**
 * POST /api/store/templates/:id/purchase
 * Initiate purchase (creates Stripe checkout)
 */
router.post('/templates/:id/purchase', requireAuth, async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const userId = req.headers.authorization?.replace('Bearer ', '');

    const template = await prisma.templates.findUnique({ where: { id } });
    if (!template || template.status !== 'published') {
      return res.status(404).json({ success: false, error: 'Template not found' });
    }

    if (template.price === 0) {
      return res.status(400).json({ success: false, error: 'Template is free' });
    }

    // Check if already purchased
    const existing = await prisma.purchases.findUnique({
      where: {
        templateId_userId: { templateId: id, userId },
      }
    });
    if (existing) {
      return res.status(400).json({ success: false, error: 'Already purchased' });
    }

    // TODO: Create Stripe Checkout Session
    // const session = await stripe.checkout.sessions.create({
    //   payment_method_types: ['card'],
    //   line_items: [{
    //     price_data: {
    //       currency: 'usd',
    //       product_data: {
    //         name: template.name,
    //         description: template.tagline,
    //       },
    //       unit_amount: template.price,
    //     },
    //     quantity: 1,
    //   }],
    //   mode: 'payment',
    //   success_url: `${BASE_URL}/store/purchases/${template.id}?success=true`,
    //   cancel_url: `${BASE_URL}/store/${template.slug}?canceled=true`,
    //   metadata: {
    //     templateId: template.id,
    //     userId,
    //   },
    // });

    // Placeholder response until Stripe is integrated
    res.json({
      success: true,
      data: {
        checkoutUrl: `/store/templates/${id}/checkout?mock=true`,
        sessionId: `mock_session_${Date.now()}`,
      },
    });
  } catch (error) {
    console.error('Error initiating purchase:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

// =====================================================
// REVIEWS
// =====================================================

/**
 * GET /api/store/templates/:id/reviews
 * List reviews for template
 */
router.get('/templates/:id/reviews', async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const { page = '1', limit = '20' } = req.query;

    const reviews = await prisma.templateReviews.findMany({
      where: { templateId: id },
      orderBy: { createdAt: 'desc' },
      skip: (parseInt(page as string) - 1) * parseInt(limit as string),
      take: parseInt(limit as string),
      include: {
        user: {
          select: {
            id: true,
            username: true,
            name: true,
            avatarUrl: true,
          }
        }
      }
    });

    res.json({ success: true, data: reviews });
  } catch (error) {
    console.error('Error listing reviews:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

/**
 * POST /api/store/templates/:id/reviews
 * Add review (requires purchase)
 */
router.post('/templates/:id/reviews',
  requireAuth,
  body('rating').isInt({ min: 1, max: 5 }),
  async (req: Request, res: Response) => {
    try {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ success: false, errors: errors.array() });
      }

      const { id } = req.params;
      const userId = req.headers.authorization?.replace('Bearer ', '');
      const { rating, title, content } = req.body;

      // Check if purchased
      const purchase = await prisma.purchases.findUnique({
        where: {
          templateId_userId: { templateId: id, userId },
        }
      });

      if (!purchase) {
        return res.status(403).json({ success: false, error: 'Must purchase before reviewing' });
      }

      const review = await prisma.templateReviews.create({
        data: {
          templateId: id,
          userId,
          rating,
          title,
          content,
        },
        include: {
          user: {
            select: {
              id: true,
              username: true,
              name: true,
              avatarUrl: true,
            }
          }
        }
      });

      res.status(201).json({ success: true, data: review });
    } catch (error) {
      console.error('Error creating review:', error);
      res.status(500).json({ success: false, error: 'Internal server error' });
    }
  }
);

// =====================================================
// FAVORITES
// =====================================================

/**
 * POST /api/store/templates/:id/favorite
 * Toggle favorite
 */
router.post('/templates/:id/favorite', requireAuth, async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const userId = req.headers.authorization?.replace('Bearer ', '');

    const existing = await prisma.favorites.findUnique({
      where: {
        userId_templateId: { userId, templateId: id },
      }
    });

    if (existing) {
      await prisma.favorites.delete({
        where: {
          userId_templateId: { userId, templateId: id },
        }
      });
      res.json({ success: true, data: { favorited: false } });
    } else {
      await prisma.favorites.create({
        data: { userId, templateId: id },
      });
      res.json({ success: true, data: { favorited: true } });
    }
  } catch (error) {
    console.error('Error toggling favorite:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

// =====================================================
// CATEGORIES & FEATURED
// =====================================================

/**
 * GET /api/store/categories
 * List all categories
 */
router.get('/categories', async (req: Request, res: Response) => {
  try {
    const categories = await prisma.templateCategories.findMany({
      orderBy: { sortOrder: 'asc' },
    });

    res.json({ success: true, data: categories });
  } catch (error) {
    console.error('Error listing categories:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

/**
 * GET /api/store/featured
 * Get featured templates
 */
router.get('/featured', async (req: Request, res: Response) => {
  try {
    const templates = await prisma.templates.findMany({
      where: {
        status: 'published',
        rating: { gte: 4.5 },
        ratingCount: { gte: 10 },
      },
      orderBy: { rating: 'desc' },
      take: 6,
      select: {
        id: true,
        slug: true,
        name: true,
        tagline: true,
        category: true,
        icon: true,
        price: true,
        rating: true,
        ratingCount: true,
        author: {
          select: {
            id: true,
            username: true,
          }
        },
      },
    });

    res.json({ success: true, data: templates });
  } catch (error) {
    console.error('Error listing featured:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

/**
 * GET /api/store/trending
 * Get trending templates
 */
router.get('/trending', async (req: Request, res: Response) => {
  try {
    // Simple trending: most downloads in last 7 days
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

    const templates = await prisma.templates.findMany({
      where: {
        status: 'published',
        publishedAt: { gte: sevenDaysAgo },
      },
      orderBy: { downloads: 'desc' },
      take: 10,
      select: {
        id: true,
        slug: true,
        name: true,
        tagline: true,
        category: true,
        icon: true,
        price: true,
        downloads: true,
        author: {
          select: {
            id: true,
            username: true,
          }
        },
      },
    });

    res.json({ success: true, data: templates });
  } catch (error) {
    console.error('Error listing trending:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

// =====================================================
// PURCHASES
// =====================================================

/**
 * GET /api/store/purchases
 * List user's purchases
 */
router.get('/purchases', requireAuth, async (req: Request, res: Response) => {
  try {
    const userId = req.headers.authorization?.replace('Bearer ', '');

    const purchases = await prisma.purchases.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      include: {
        template: {
          select: {
            id: true,
            slug: true,
            name: true,
            tagline: true,
            icon: true,
            category: true,
          }
        }
      },
    });

    res.json({ success: true, data: purchases });
  } catch (error) {
    console.error('Error listing purchases:', error);
    res.status(500).json({ success: false, error: 'Internal server error' });
  }
});

export default router;
