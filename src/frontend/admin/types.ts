/**
 * Matha Auth Admin - React 管理界面类型定义
 * 从 docs/auth_types.ts 导出，本地同步版本
 */

export interface JwtConfig {
  secret_key: string;
  access_token: { exp_hours: number; alg: 'HS256' };
  refresh_token: { exp_days: number; alg: 'HS256' };
}

export interface PasswordPolicy {
  min_length: number;
  max_length: number;
  require_alpha: boolean;
  require_digit: boolean;
  pbkdf2_rounds: number;
  hash_algorithm: 'sha256';
}

export interface RoleConfig {
  display_name: string;
  description: string;
  permissions: string[];
}

export interface User {
  username: string;
  email: string;
  roles: string[];
  active: boolean;
  last_login: number | null;
  created_at?: number;
}

export interface Session {
  session_id: string;
  username: string;
  token: string;
  refresh_token: string;
  created_at: number;
  expires_at: number;
  is_valid: boolean;
}

export interface AuditEntry {
  time: string;
  type: 'add_role' | 'remove_role' | 'set_role' | 'update_user';
  target: string;
  data: Record<string, unknown>;
  operator: string;
}

export interface SystemConfig {
  accessExp: number;
  refreshExp: number;
  minPw: number;
  maxSessions: number;
  lockAttempts: number;
  lockDuration: number;
}

export interface AuthState {
  users: Record<string, User>;
  roles: RoleConfig[];
  customRoles: Record<string, RoleConfig>;
  auditLog: AuditEntry[];
  config: SystemConfig;
  currentAdmin: string | null;
}
