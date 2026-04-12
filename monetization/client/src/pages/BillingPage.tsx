/**
 * CC-Claw Billing Page — React Component
 */

import React, { useState, useEffect } from 'react';

// Types
interface Tier {
  id: string;
  name: string;
  price: number;
  priceFormatted: string;
  priceAnnual?: number;
  priceAnnualFormatted?: string;
  features: {
    rateLimit: string;
    activeGoals: number | string;
    historyDays: number;
    tools: string[];
    apiEnabled: boolean;
    prioritySupport: boolean;
    dedicatedSupport?: boolean;
    customBranding?: boolean;
    onPremise?: boolean;
  };
}

interface Subscription {
  tier: string;
  status: string;
  currentPeriodEnd?: string;
  cancelAtPeriodEnd?: boolean;
  price?: number;
  priceFormatted?: string;
}

interface Usage {
  tier: string;
  rateLimit: number;
  requestsToday: number;
  requestsThisMonth: number;
  usagePercent: number;
}

// Mock data
const MOCK_TIERS: Tier[] = [
  {
    id: 'FREE',
    name: 'Free',
    price: 0,
    priceFormatted: '$0',
    features: {
      rateLimit: '60 req/min',
      activeGoals: 1,
      historyDays: 7,
      tools: ['file', 'scraper', 'api', 'process', 'git'],
      apiEnabled: false,
      prioritySupport: false,
    },
  },
  {
    id: 'PRO',
    name: 'Pro',
    price: 900,
    priceFormatted: '$9',
    priceAnnual: 9000,
    priceAnnualFormatted: '$90/year',
    features: {
      rateLimit: '300 req/min',
      activeGoals: 5,
      historyDays: 30,
      tools: ['file', 'scraper', 'api', 'process', 'git', 'system', 'docker', 'agentsolvehub'],
      apiEnabled: true,
      prioritySupport: true,
    },
  },
  {
    id: 'ENTERPRISE',
    name: 'Enterprise',
    price: 4900,
    priceFormatted: '$49',
    features: {
      rateLimit: 'Unlimited',
      activeGoals: 'Unlimited',
      historyDays: 365,
      tools: ['all'],
      apiEnabled: true,
      prioritySupport: true,
      dedicatedSupport: true,
      customBranding: true,
      onPremise: true,
    },
  },
];

// Components
const CheckIcon = () => (
  <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
);

const LockIcon = () => (
  <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
  </svg>
);

const FeatureRow: React.FC<{ label: string; value: string | boolean; locked?: boolean }> = ({
  label,
  value,
  locked,
}) => (
  <div className="flex items-center justify-between py-2">
    <span className={`text-sm ${locked ? 'text-gray-500' : 'text-gray-300'}`}>{label}</span>
    {typeof value === 'boolean' ? (
      value ? (
        <CheckIcon />
      ) : locked ? (
        <LockIcon />
      ) : (
        <span className="text-sm text-gray-500">—</span>
      )
    ) : (
      <span className={`text-sm font-medium ${locked ? 'text-gray-500' : 'text-white'}`}>
        {value}
      </span>
    )}
  </div>
);

const TierCard: React.FC<{
  tier: Tier;
  isCurrentTier: boolean;
  onSelect: () => void;
  loading?: boolean;
}> = ({ tier, isCurrentTier, onSelect, loading }) => {
  const isFree = tier.id === 'FREE';
  const isEnterprise = tier.id === 'ENTERPRISE';

  return (
    <div
      className={`relative rounded-2xl border p-6 transition-all ${
        isCurrentTier
          ? 'border-cyan-500 ring-2 ring-cyan-500/20'
          : 'border-gray-700 hover:border-gray-600'
      }`}
    >
      {isCurrentTier && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="bg-cyan-500 text-white text-xs font-medium px-3 py-1 rounded-full">
            Current Plan
          </span>
        </div>
      )}

      {/* Header */}
      <div className="text-center mb-6">
        <h3 className="text-xl font-bold text-white">{tier.name}</h3>
        <div className="mt-2">
          <span className="text-3xl font-bold text-white">{tier.priceFormatted}</span>
          {tier.price > 0 && <span className="text-gray-400">/month</span>}
        </div>
        {tier.priceAnnualFormatted && (
          <div className="mt-1 text-sm text-gray-400">
            or {tier.priceAnnualFormatted}
          </div>
        )}
      </div>

      {/* Features */}
      <div className="border-t border-gray-700 pt-4 space-y-0">
        <FeatureRow label="Rate Limit" value={tier.features.rateLimit} />
        <FeatureRow label="Active Goals" value={tier.features.activeGoals} />
        <FeatureRow label="History" value={`${tier.features.historyDays} days`} />
        <FeatureRow
          label="API Access"
          value={tier.features.apiEnabled}
          locked={!tier.features.apiEnabled}
        />
        <FeatureRow
          label="Priority Support"
          value={tier.features.prioritySupport}
          locked={!tier.features.prioritySupport}
        />
        <FeatureRow
          label="Dedicated Support"
          value={tier.features.dedicatedSupport || false}
          locked={!tier.features.dedicatedSupport}
        />
        <FeatureRow
          label="Custom Branding"
          value={tier.features.customBranding || false}
          locked={!tier.features.customBranding}
        />
        <FeatureRow
          label="On-Premise Deploy"
          value={tier.features.onPremise || false}
          locked={!tier.features.onPremise}
        />
      </div>

      {/* CTA */}
      <div className="mt-6">
        {isCurrentTier ? (
          <button
            disabled
            className="w-full py-2 rounded-lg bg-gray-700 text-gray-400 font-medium cursor-not-allowed"
          >
            Current Plan
          </button>
        ) : isFree ? (
          <button
            onClick={onSelect}
            disabled={loading}
            className="w-full py-2 rounded-lg border border-gray-600 text-gray-300 font-medium hover:bg-gray-800 transition-colors disabled:opacity-50"
          >
            Downgrade to Free
          </button>
        ) : isEnterprise ? (
          <button
            onClick={onSelect}
            disabled={loading}
            className="w-full py-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            Contact Sales
          </button>
        ) : (
          <button
            onClick={onSelect}
            disabled={loading}
            className="w-full py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-500 text-white font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {loading ? 'Processing...' : 'Upgrade to Pro'}
          </button>
        )}
      </div>
    </div>
  );
};

const UsageMeter: React.FC<{ usage: Usage }> = ({ usage }) => {
  const percent = Math.min(100, usage.usagePercent);
  const isNearLimit = percent > 80;
  const isAtLimit = percent >= 100;

  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
      <h3 className="text-lg font-semibold text-white mb-4">Current Usage</h3>

      <div className="mb-4">
        <div className="flex justify-between text-sm mb-2">
          <span className="text-gray-400">Today's Requests</span>
          <span className={isAtLimit ? 'text-red-400' : 'text-white'}>
            {usage.requestsToday.toLocaleString()} /{' '}
            {usage.rateLimit === Infinity ? '∞' : usage.rateLimit.toLocaleString()}
          </span>
        </div>

        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all ${
              isAtLimit ? 'bg-red-500' : isNearLimit ? 'bg-yellow-500' : 'bg-cyan-500'
            }`}
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      <div className="flex justify-between text-sm text-gray-400">
        <span>This month: {usage.requestsThisMonth.toLocaleString()} requests</span>
        {isAtLimit && (
          <span className="text-red-400">
            <a href="/billing?upgrade=pro" className="underline">
              Upgrade to Pro
            </a>{' '}
            for more
          </span>
        )}
      </div>
    </div>
  );
};

const ApiKeyCard: React.FC<{
  key: { id: string; name: string; key: string; lastUsedAt?: string };
  onDelete: (id: string) => void;
}> = ({ key, onDelete }) => (
  <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 flex items-center justify-between">
    <div>
      <div className="flex items-center gap-2">
        <h4 className="font-medium text-white">{key.name}</h4>
        <span className="text-xs bg-cyan-500/20 text-cyan-400 px-2 py-0.5 rounded">PRO</span>
      </div>
      <div className="mt-1 font-mono text-sm text-gray-400">{key.key}</div>
      {key.lastUsedAt && (
        <div className="mt-1 text-xs text-gray-500">
          Last used: {new Date(key.lastUsedAt).toLocaleDateString()}
        </div>
      )}
    </div>
    <button
      onClick={() => onDelete(key.id)}
      className="text-gray-400 hover:text-red-400 transition-colors"
    >
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
        />
      </svg>
    </button>
  </div>
);

// Main Page Component
const BillingPage: React.FC = () => {
  const [tiers] = useState<Tier[]>(MOCK_TIERS);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showNewKeyModal, setShowNewKeyModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');

  // Load data
  useEffect(() => {
    // Mock data loading
    setSubscription({
      tier: 'FREE',
      status: 'active',
    });

    setUsage({
      tier: 'FREE',
      rateLimit: 60,
      requestsToday: 23,
      requestsThisMonth: 847,
      usagePercent: 38,
    });

    setApiKeys([]);
  }, []);

  const handleUpgrade = async (tierId: string) => {
    if (tierId === 'FREE') {
      // Show downgrade confirmation
      return;
    }

    setLoading(true);

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // In production, this would redirect to Stripe checkout
    alert(`Redirecting to Stripe checkout for ${tierId}...`);

    setLoading(false);
  };

  const handleCreateApiKey = async () => {
    if (!newKeyName.trim()) return;

    // Mock API key creation
    const newKey = {
      id: Date.now().toString(),
      name: newKeyName,
      key: `sk_live_xxxx...${Math.random().toString(36).slice(-4)}`,
      lastUsedAt: null,
    };

    setApiKeys([...apiKeys, newKey]);
    setNewKeyName('');
    setShowNewKeyModal(false);
  };

  const handleDeleteApiKey = async (id: string) => {
    if (!confirm('Are you sure you want to delete this API key?')) return;

    setApiKeys(apiKeys.filter((k) => k.id !== id));
  };

  const currentTier = subscription?.tier || 'FREE';
  const isProOrHigher = currentTier === 'PRO' || currentTier === 'ENTERPRISE';

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800/50 border-b border-gray-700">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🦞</span>
              <span className="font-bold text-xl">CC-Claw</span>
            </div>
            <nav className="flex items-center gap-6">
              <a href="/dashboard" className="text-gray-400 hover:text-white">
                Dashboard
              </a>
              <a href="/settings" className="text-gray-400 hover:text-white">
                Settings
              </a>
              <a href="/billing" className="text-white font-medium">
                Billing
              </a>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-2">Billing & Subscription</h1>
        <p className="text-gray-400 mb-8">Manage your subscription and API keys</p>

        {/* Usage (for current tier) */}
        {usage && <div className="mb-8">{/* <UsageMeter usage={usage} /> */}</div>}

        {/* Tiers */}
        <section className="mb-12">
          <h2 className="text-xl font-semibold mb-6">Choose Your Plan</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {tiers.map((tier) => (
              <TierCard
                key={tier.id}
                tier={tier}
                isCurrentTier={tier.id === currentTier}
                onSelect={() => handleUpgrade(tier.id)}
                loading={loading}
              />
            ))}
          </div>
        </section>

        {/* API Keys (PRO+) */}
        <section className="mb-12">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-semibold">API Keys</h2>
              <p className="text-sm text-gray-400 mt-1">
                {isProOrHigher
                  ? 'Manage your API keys for programmatic access'
                  : 'Upgrade to PRO to get API access'}
              </p>
            </div>
            {isProOrHigher && (
              <button
                onClick={() => setShowNewKeyModal(true)}
                className="px-4 py-2 bg-cyan-500 text-white rounded-lg font-medium hover:bg-cyan-600 transition-colors"
              >
                + New API Key
              </button>
            )}
          </div>

          {!isProOrHigher ? (
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-8 text-center">
              <div className="text-4xl mb-3">🔑</div>
              <h3 className="text-lg font-medium mb-2">API Access Requires PRO</h3>
              <p className="text-gray-400 mb-4">
                Upgrade to PRO to get API keys for programmatic access to CC-Claw.
              </p>
              <button
                onClick={() => handleUpgrade('PRO')}
                className="px-6 py-2 bg-gradient-to-r from-cyan-500 to-purple-500 text-white rounded-lg font-medium"
              >
                Upgrade to PRO — $9/month
              </button>
            </div>
          ) : apiKeys.length === 0 ? (
            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-8 text-center">
              <div className="text-4xl mb-3">🔑</div>
              <h3 className="text-lg font-medium mb-2">No API Keys Yet</h3>
              <p className="text-gray-400 mb-4">
                Create your first API key to start integrating with CC-Claw.
              </p>
              <button
                onClick={() => setShowNewKeyModal(true)}
                className="px-6 py-2 bg-cyan-500 text-white rounded-lg font-medium hover:bg-cyan-600 transition-colors"
              >
                Create API Key
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {apiKeys.map((key) => (
                <ApiKeyCard key={key.id} key={key} onDelete={handleDeleteApiKey} />
              ))}
            </div>
          )}
        </section>

        {/* Billing History */}
        <section>
          <h2 className="text-xl font-semibold mb-6">Billing History</h2>
          <div className="bg-gray-800/50 border border-gray-700 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-700/50">
                <tr>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">
                    Date
                  </th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">
                    Description
                  </th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">
                    Amount
                  </th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">
                    Status
                  </th>
                  <th className="text-right px-4 py-3 text-sm font-medium text-gray-400">
                    Receipt
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                <tr>
                  <td className="px-4 py-4 text-sm text-gray-400" colSpan={5}>
                    No billing history yet
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </main>

      {/* New API Key Modal */}
      {showNewKeyModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">Create API Key</h3>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Key Name
              </label>
              <input
                type="text"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                placeholder="e.g., Production, Development"
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="bg-gray-900 rounded-lg p-4 mb-4">
              <p className="text-sm text-gray-400">
                Your new API key will be displayed once. Make sure to copy it now as it
                won't be shown again.
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowNewKeyModal(false)}
                className="flex-1 px-4 py-2 border border-gray-600 text-gray-300 rounded-lg hover:bg-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateApiKey}
                disabled={!newKeyName.trim()}
                className="flex-1 px-4 py-2 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600 transition-colors disabled:opacity-50"
              >
                Create Key
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BillingPage;
