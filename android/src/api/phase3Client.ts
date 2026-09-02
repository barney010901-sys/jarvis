import { getJson, postJson } from './client';
import type { JarvisSettings } from '../config/settings';

/**
 * Typed wrappers over backend/app/api/phase3_routes.py. Every function
 * mirrors that file's response shape exactly — if the backend route
 * changes, update both places together (same convention as api/events.ts).
 */

export type SystemComponentHealth = { component: string; status: string; detail: string };

export type DashboardSummary = {
  system_health: SystemComponentHealth[];
  suggestions: { id: string; title: string; priority: string; reason: string }[];
  pending_approvals: { id: string; kind: string; title: string; risk: string }[];
  wallet: { balance_usd: number; weekly_spent: number; weekly_limit: number } | null;
  business: { revenue_total_usd: number; surplus_usd: number; stage: string } | null;
};

export async function getDashboard(settings: JarvisSettings) {
  return getJson<DashboardSummary>(settings, '/dashboard');
}

export async function getSystemHealth(settings: JarvisSettings) {
  return getJson<{ components: SystemComponentHealth[] }>(settings, '/system/health');
}

export type Approval = {
  id: string;
  kind: string;
  title: string;
  description: string;
  risk: string;
  cost_usd: number | null;
  status: string;
  task_id: string | null;
  requested_at: string;
};

export async function getApprovals(settings: JarvisSettings, status?: 'PENDING') {
  const query = status ? `?status=${status}` : '';
  return getJson<{ approvals: Approval[] }>(settings, `/approvals${query}`);
}

export type AuditEntry = {
  event_type: string;
  component: string;
  action: string;
  task_id: string | null;
  result: string | null;
  confirmation_state: string | null;
  created_at: string;
};

export async function getAudit(settings: JarvisSettings, params: { taskId?: string; component?: string } = {}) {
  const search = new URLSearchParams();
  if (params.taskId) search.set('task_id', params.taskId);
  if (params.component) search.set('component', params.component);
  const query = search.toString() ? `?${search.toString()}` : '';
  return getJson<{ entries: AuditEntry[] }>(settings, `/audit${query}`);
}

export type MemorySearchResult = {
  memories: { id: string; content: string; tags: string[] }[];
  knowledge: { id: string; category: string; title: string; content: string; confidence: number; status: string }[];
};

export async function searchMemory(settings: JarvisSettings, query: string, project = 'default') {
  return getJson<MemorySearchResult>(settings, `/memory/search?q=${encodeURIComponent(query)}&project=${encodeURIComponent(project)}`);
}

export type TaskSummary = {
  id: string;
  project: string;
  request: string;
  status: string;
  error: string | null;
  created_at: string;
  completed_at: string | null;
};

export async function getTasks(settings: JarvisSettings, sessionId?: string) {
  const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
  return getJson<{ tasks: TaskSummary[] }>(settings, `/tasks${query}`);
}

export type ProjectSummary = { slug: string; name: string; status: string; goals: string[]; technologies: string[]; last_active_at: string };

export async function getProjects(settings: JarvisSettings) {
  return getJson<{ projects: ProjectSummary[] }>(settings, '/projects');
}

export type GoalSummary = { id: string; title: string; description: string; status: string };

export async function getProjectGoals(settings: JarvisSettings, slug: string) {
  return getJson<{ goals: GoalSummary[] }>(settings, `/projects/${encodeURIComponent(slug)}/goals`);
}

export type WalletOverview = {
  balance_usd: number;
  weekly_limit_usd: number;
  weekly_spent_usd: number;
  monthly_limit_usd: number;
  monthly_spent_usd: number;
  per_transaction_limit_usd: number;
  approved_categories: string[];
  blocked_categories: string[];
  approved_vendors: string[];
  transactions: { id: string; amount_usd: number; vendor: string; category: string; purpose: string; policy_decision: string; status: string; created_at: string }[];
};

export async function getWallet(settings: JarvisSettings) {
  return getJson<WalletOverview>(settings, '/wallet');
}

export async function updateWalletLimits(settings: JarvisSettings, limits: Partial<Pick<WalletOverview, 'weekly_limit_usd' | 'monthly_limit_usd' | 'per_transaction_limit_usd'>>) {
  return postJson(settings, '/wallet/limits', limits);
}

export type BusinessSummary = { revenue_total_usd: number; monthly_operating_cost_usd: number; surplus_usd: number; stage: string };

export async function getBusinessSummary(settings: JarvisSettings) {
  return getJson<BusinessSummary>(settings, '/business/summary');
}

export type Opportunity = { id: string; title: string; description: string; score: number; status: string };

export async function getOpportunities(settings: JarvisSettings) {
  return getJson<{ opportunities: Opportunity[] }>(settings, '/business/opportunities');
}

export type Customer = { id: string; name: string; stage: string; notes: string };

export async function getCustomers(settings: JarvisSettings) {
  return getJson<{ customers: Customer[] }>(settings, '/business/customers');
}

export type Capability = { id: string; name: string; type?: string; purpose?: string; source: string; verification_status: string };

export async function getCapabilities(settings: JarvisSettings) {
  return getJson<{ capabilities: Capability[] }>(settings, '/capabilities');
}

export async function searchCapabilities(settings: JarvisSettings, query: string, purpose: string) {
  return postJson<{ capabilities: Capability[] }>(settings, '/capabilities/search', { query, purpose });
}

export type Contact = { id: string; name: string; relationship: string; role: string; channel: string; active: boolean };

export async function getContacts(settings: JarvisSettings) {
  return getJson<{ contacts: Contact[] }>(settings, '/contacts');
}

export async function createContact(settings: JarvisSettings, contact: { name: string; role: string; channel: string; relationship?: string }) {
  return postJson<Contact>(settings, '/contacts', contact);
}

export async function getAutonomyLevel(settings: JarvisSettings) {
  return getJson<{ level: number; name: string }>(settings, '/settings/autonomy');
}

export async function setAutonomyLevel(settings: JarvisSettings, level: number) {
  return postJson<{ level: number; name: string }>(settings, '/settings/autonomy', { level });
}
