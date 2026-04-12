/**
 * CC-Claw Agent Store — Marketplace Page
 * /store
 */

import React, { useState, useEffect } from 'react';

// Types
interface Template {
  id: string;
  slug: string;
  name: string;
  tagline: string;
  category: string;
  tags: string[];
  icon: string;
  price: number;
  currency: string;
  downloads: number;
  rating: number;
  ratingCount: number;
  author: {
    id: string;
    username: string;
    avatarUrl?: string;
  };
}

interface Category {
  id: string;
  name: string;
  icon: string;
  templateCount: number;
}

interface Pagination {
  page: number;
  limit: number;
  total: number;
  pages: number;
}

// Mock data for demonstration
const MOCK_CATEGORIES: Category[] = [
  { id: 'bug-fixing', name: 'Bug Fixing', icon: '🐛', templateCount: 45 },
  { id: 'feature-development', name: 'Feature Development', icon: '⚡', templateCount: 32 },
  { id: 'testing', name: 'Testing', icon: '🧪', templateCount: 28 },
  { id: 'documentation', name: 'Documentation', icon: '📚', templateCount: 21 },
  { id: 'devops', name: 'DevOps', icon: '🚀', templateCount: 35 },
  { id: 'docker', name: 'Docker', icon: '🐳', templateCount: 18 },
  { id: 'data-analysis', name: 'Data Analysis', icon: '📊', templateCount: 24 },
  { id: 'refactoring', name: 'Refactoring', icon: '🔧', templateCount: 15 },
];

const MOCK_TEMPLATES: Template[] = [
  {
    id: '1',
    slug: 'bug-fixer-pro',
    name: 'Bug Fixer Pro',
    tagline: 'Automatically find and fix bugs in any codebase',
    category: 'bug-fixing',
    tags: ['bug-fixing', 'python', 'debugging'],
    icon: '🐛',
    price: 499,
    currency: 'USD',
    downloads: 3420,
    rating: 4.8,
    ratingCount: 124,
    author: { id: '1', username: 'dev123', avatarUrl: '' },
  },
  {
    id: '2',
    slug: 'feature-dev-kit',
    name: 'Feature Dev Kit',
    tagline: 'Build features faster with AI-powered scaffolding',
    category: 'feature-development',
    tags: ['scaffolding', 'templates', 'fastapi'],
    icon: '⚡',
    price: 0,
    currency: 'USD',
    downloads: 8920,
    rating: 4.9,
    ratingCount: 89,
    author: { id: '2', username: 'builder456', avatarUrl: '' },
  },
  {
    id: '3',
    slug: 'code-review-ai',
    name: 'Code Review AI',
    tagline: 'Comprehensive code review with best practices',
    category: 'code-review',
    tags: ['review', 'best-practices', 'security'],
    icon: '👀',
    price: 999,
    currency: 'USD',
    downloads: 1560,
    rating: 4.6,
    ratingCount: 56,
    author: { id: '3', username: 'senior_dev', avatarUrl: '' },
  },
  {
    id: '4',
    slug: 'docker-helper',
    name: 'Docker Helper',
    tagline: 'Container management and deployment automation',
    category: 'docker',
    tags: ['docker', 'containers', 'devops'],
    icon: '🐳',
    price: 0,
    currency: 'USD',
    downloads: 4200,
    rating: 4.7,
    ratingCount: 78,
    author: { id: '4', username: 'devops_pro', avatarUrl: '' },
  },
  {
    id: '5',
    slug: 'test-master',
    name: 'Test Master',
    tagline: 'Generate comprehensive test suites automatically',
    category: 'testing',
    tags: ['testing', 'jest', 'pytest'],
    icon: '🧪',
    price: 799,
    currency: 'USD',
    downloads: 2100,
    rating: 4.5,
    ratingCount: 92,
    author: { id: '5', username: 'qa_expert', avatarUrl: '' },
  },
  {
    id: '6',
    slug: 'ci-cd-pipeline',
    name: 'CI/CD Pipeline Builder',
    tagline: 'Set up complete CI/CD pipelines in minutes',
    category: 'ci-cd',
    tags: ['cicd', 'github-actions', 'gitlab'],
    icon: '🔄',
    price: 1499,
    currency: 'USD',
    downloads: 890,
    rating: 4.9,
    ratingCount: 112,
    author: { id: '6', username: 'cicd_guru', avatarUrl: '' },
  },
];

// Components
const CategoryCard: React.FC<{ category: Category; selected: boolean; onClick: () => void }> = ({
  category,
  selected,
  onClick,
}) => (
  <button
    onClick={onClick}
    className={`flex items-center gap-2 px-4 py-2 rounded-full border transition-all ${
      selected
        ? 'bg-gradient-to-r from-cyan-500 to-purple-500 text-white border-transparent'
        : 'bg-gray-800/50 border-gray-700 text-gray-300 hover:border-gray-600'
    }`}
  >
    <span>{category.icon}</span>
    <span className="font-medium">{category.name}</span>
    <span className={`text-xs ${selected ? 'text-white/70' : 'text-gray-500'}`}>
      {category.templateCount}
    </span>
  </button>
);

const TemplateCard: React.FC<{ template: Template }> = ({ template }) => (
  <div className="bg-gray-800/50 border border-gray-700 rounded-xl overflow-hidden hover:border-gray-600 transition-all hover:transform hover:-translate-y-1">
    {/* Cover */}
    <div className="h-32 bg-gradient-to-br from-gray-700 to-gray-800 flex items-center justify-center">
      <span className="text-5xl">{template.icon}</span>
    </div>

    {/* Content */}
    <div className="p-4">
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-white truncate">{template.name}</h3>
        <span className="text-lg font-bold text-cyan-400">
          {template.price === 0 ? 'Free' : `$${(template.price / 100).toFixed(2)}`}
        </span>
      </div>

      <p className="text-sm text-gray-400 mt-1 line-clamp-2">{template.tagline}</p>

      {/* Stats */}
      <div className="flex items-center gap-3 mt-3 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="text-yellow-400">★</span>
          {template.rating.toFixed(1)} ({template.ratingCount})
        </span>
        <span>{template.downloads.toLocaleString()} downloads</span>
      </div>

      {/* Author */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-700">
        <div className="w-6 h-6 rounded-full bg-gradient-to-br from-cyan-500 to-purple-500" />
        <span className="text-sm text-gray-400">@{template.author.username}</span>
      </div>
    </div>
  </div>
);

const SortSelect: React.FC<{ value: string; onChange: (value: string) => void }> = ({
  value,
  onChange,
}) => (
  <select
    value={value}
    onChange={(e) => onChange(e.target.value)}
    className="bg-gray-800 border border-gray-700 text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
  >
    <option value="downloads">Most Popular</option>
    <option value="rating">Highest Rated</option>
    <option value="newest">Newest</option>
    <option value="price_asc">Price: Low to High</option>
    <option value="price_desc">Price: High to Low</option>
  </select>
);

const PriceFilter: React.FC<{
  freeOnly: boolean;
  onChange: (freeOnly: boolean) => void;
}> = ({ freeOnly, onChange }) => (
  <label className="flex items-center gap-2 cursor-pointer">
    <input
      type="checkbox"
      checked={freeOnly}
      onChange={(e) => onChange(e.target.checked)}
      className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-cyan-500 focus:ring-cyan-500"
    />
    <span className="text-sm text-gray-300">Free only</span>
  </label>
);

// Main Page Component
const StorePage: React.FC = () => {
  const [templates, setTemplates] = useState<Template[]>(MOCK_TEMPLATES);
  const [categories] = useState<Category[]>(MOCK_CATEGORIES);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState('downloads');
  const [freeOnly, setFreeOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState<Pagination>({
    page: 1,
    limit: 12,
    total: 50,
    pages: 5,
  });

  // Filter templates
  const filteredTemplates = templates
    .filter((t) => !selectedCategory || t.category === selectedCategory)
    .filter((t) => !freeOnly || t.price === 0)
    .filter((t) => !searchQuery || t.name.toLowerCase().includes(searchQuery.toLowerCase()));

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-gray-900/80 backdrop-blur-xl border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between gap-4">
            {/* Logo */}
            <a href="/" className="flex items-center gap-2">
              <span className="text-2xl">🦞</span>
              <span className="font-bold text-xl">CC-Claw Store</span>
            </a>

            {/* Search */}
            <div className="flex-1 max-w-xl">
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search templates..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-cyan-500"
                />
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">
                  🔍
                </span>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              <a
                href="/store/manage"
                className="text-sm text-gray-400 hover:text-white transition-colors"
              >
                My Templates
              </a>
              <a
                href="/store/create"
                className="bg-gradient-to-r from-cyan-500 to-purple-500 text-white px-4 py-2 rounded-lg font-medium text-sm hover:opacity-90 transition-opacity"
              >
                + New Template
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Hero */}
        <section className="text-center py-12">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-cyan-400 to-purple-400 bg-clip-text text-transparent">
            Agent Templates Marketplace
          </h1>
          <p className="mt-3 text-gray-400 max-w-2xl mx-auto">
            Discover, share, and buy pre-configured agent templates for every use case.
            Save time with proven workflows.
          </p>

          {/* Stats */}
          <div className="flex justify-center gap-8 mt-8">
            <div className="text-center">
              <div className="text-2xl font-bold text-white">2,500+</div>
              <div className="text-sm text-gray-500">Templates</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-white">15,000+</div>
              <div className="text-sm text-gray-500">Downloads</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-white">500+</div>
              <div className="text-sm text-gray-500">Creators</div>
            </div>
          </div>
        </section>

        {/* Categories */}
        <section className="mb-8">
          <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide">
            <button
              onClick={() => setSelectedCategory(null)}
              className={`flex items-center gap-2 px-4 py-2 rounded-full border transition-all whitespace-nowrap ${
                !selectedCategory
                  ? 'bg-gradient-to-r from-cyan-500 to-purple-500 text-white border-transparent'
                  : 'bg-gray-800/50 border-gray-700 text-gray-300 hover:border-gray-600'
              }`}
            >
              All
            </button>
            {categories.map((cat) => (
              <CategoryCard
                key={cat.id}
                category={cat}
                selected={selectedCategory === cat.id}
                onClick={() => setSelectedCategory(cat.id)}
              />
            ))}
          </div>
        </section>

        {/* Filters & Results */}
        <section>
          {/* Filter Bar */}
          <div className="flex items-center justify-between gap-4 mb-6">
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-400">
                {filteredTemplates.length} templates
              </span>
              <PriceFilter freeOnly={freeOnly} onChange={setFreeOnly} />
            </div>
            <SortSelect value={sortBy} onChange={setSortBy} />
          </div>

          {/* Templates Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredTemplates.map((template) => (
              <a key={template.id} href={`/store/${template.slug}`}>
                <TemplateCard template={template} />
              </a>
            ))}
          </div>

          {/* Empty State */}
          {filteredTemplates.length === 0 && (
            <div className="text-center py-16">
              <div className="text-5xl mb-4">🔍</div>
              <h3 className="text-xl font-medium text-white">No templates found</h3>
              <p className="text-gray-400 mt-2">
                Try adjusting your filters or search query
              </p>
            </div>
          )}

          {/* Pagination */}
          {pagination.pages > 1 && (
            <div className="flex justify-center gap-2 mt-8">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 rounded bg-gray-800 text-gray-400 disabled:opacity-50"
              >
                ← Prev
              </button>
              {Array.from({ length: pagination.pages }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`px-3 py-1 rounded ${
                    p === page
                      ? 'bg-cyan-500 text-white'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                  }`}
                >
                  {p}
                </button>
              ))}
              <button
                onClick={() => setPage((p) => Math.min(pagination.pages, p + 1))}
                disabled={page === pagination.pages}
                className="px-3 py-1 rounded bg-gray-800 text-gray-400 disabled:opacity-50"
              >
                Next →
              </button>
            </div>
          )}
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 mt-16">
        <div className="max-w-7xl mx-auto px-4 py-8 text-center text-gray-500 text-sm">
          <p>© 2024 CC-Claw Store. Built on CC-Claw.</p>
          <div className="flex justify-center gap-4 mt-2">
            <a href="#" className="hover:text-gray-400">Terms</a>
            <a href="#" className="hover:text-gray-400">Privacy</a>
            <a href="#" className="hover:text-gray-400">Support</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default StorePage;
