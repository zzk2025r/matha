/**
 * Matha 认证模块 TypeScript 类型定义
 * 生成自 configs/auth_config.json
 */

// ============================================================
// JWT 配置
// ============================================================

export interface JwtAccessTokenConfig {
  exp_hours: number;
  alg: 'HS256';
}

export interface JwtRefreshTokenConfig {
  exp_days: number;
  alg: 'HS256';
}

export interface JwtConfig {
  secret_key: string;
  access_token: JwtAccessTokenConfig;
  refresh_token: JwtRefreshTokenConfig;
}

// ============================================================
// 密码策略
// ============================================================

export interface PasswordPolicy {
  min_length: number;
  max_length: number;
  require_alpha: boolean;
  require_digit: boolean;
  pbkdf2_rounds: number;
  hash_algorithm: 'sha256';
}

// ============================================================
// 角色与权限
// ============================================================

export interface RoleConfig {
  display_name: string;
  description: string;
  permissions: string[];
}

export interface RolesConfig {
  admin: RoleConfig;
  editor: RoleConfig;
  viewer: RoleConfig;
  guest: RoleConfig;
  [customRole: string]: RoleConfig;
}

export interface PermissionDescription {
  [action: string]: string;
}

export interface PermissionsConfig {
  doc: PermissionDescription;
  user: PermissionDescription;
  code: PermissionDescription;
  system: PermissionDescription;
}

// ============================================================
// 会话配置
// ============================================================

export interface SessionConfig {
  /** 单用户最大并发会话数 */
  max_concurrent_per_user: number;
  /** 空闲超时踢出（小时） */
  idle_timeout_hours: number;
  /** 会话清理间隔（秒） */
  cleanup_interval_seconds: number;
}

// ============================================================
// 日志配置
// ============================================================

export interface LogHandler {
  type: 'console' | 'file';
  path?: string;
  max_size_mb?: number;
  backup_count?: number;
}

export interface LoggingConfig {
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  format: string;
  handlers: LogHandler[];
}

// ============================================================
// 安全配置
// ============================================================

export interface RateLimitConfig {
  login_per_minute: number;
  register_per_minute: number;
  token_refresh_per_minute: number;
}

export interface SecurityConfig {
  max_login_attempts: number;
  lockout_duration_minutes: number;
  rate_limit: RateLimitConfig;
}

// ============================================================
// 根配置
// ============================================================

export interface AuthConfig {
  jwt: JwtConfig;
  password: PasswordPolicy;
  roles: RolesConfig;
  permissions: PermissionsConfig;
  session: SessionConfig;
  logging: LoggingConfig;
  security: SecurityConfig;
}

// ============================================================
// Token Payload 类型
// ============================================================

export interface JwtPayload {
  sub: string;       // 用户名
  type: 'access' | 'refresh';
  roles: string[];   // 用户角色列表
  jti: string;       // JWT 唯一标识符
  iat: number;       // 签发时间（Unix 时间戳）
  exp: number;       // 过期时间（Unix 时间戳）
}

// ============================================================
// 用户数据模型
// ============================================================

export interface User {
  username: string;
  email: string;
  password_hash: string;
  created_at: number;
  last_login: number | null;
  is_active: boolean;
  roles: string[];
}

// ============================================================
// 会话数据模型
// ============================================================

export interface Session {
  session_id: string;
  username: string;
  token: string;             // JWT access token
  refresh_token: string;     // JWT refresh token
  created_at: number;
  expires_at: number;
  is_valid: boolean;
}

// ============================================================
// 权限变更操作类型
// ============================================================

export type ChangeType = 'add_role' | 'remove_role' | 'set_role' | 'update_user';

export interface PermissionChangeRequest {
  operator: string;
  target_usernames: string[];
  change_type: ChangeType;
  new_roles?: string[];
  is_active?: boolean;
  reason?: string;
  timestamp: number;
}

export interface PermissionChangeResult {
  success: boolean;
  changed: string[];
  skipped: string[];
  errors: string[];
  change_type: string;
  operator: string;
}

// ============================================================
// 审计日志条目
// ============================================================

export interface AuditEntry {
  time: string;
  type: ChangeType;
  target: string;
  data: Record<string, unknown>;
  operator: string;
}

// ============================================================
// RBAC 中间件接口
// ============================================================

export interface RBACMiddleware {
  /** 检查用户是否拥有指定权限 */
  hasPermission(roles: string[], permission: string): boolean;
  /** 授权检查，无权限时抛出 AuthorizationError */
  authorize(roles: string[], permission: string, resource?: string): void;
  /** 获取用户所有角色合并后的权限集合 */
  getEffectivePermissions(roles: string[]): Set<string>;
  /** 注册或更新角色 */
  registerRole(name: string, permissions: string[]): void;
  /** 删除角色 */
  removeRole(name: string): boolean;
  /** 列出所有角色 */
  listRoles(): string[];
}

// ============================================================
// PermissionChangeAPI 接口
// ============================================================

export interface PermissionChangeAPI {
  /** 给用户添加角色 */
  addRole(username: string, roles: string[], operator: string): Promise<PermissionChangeResult>;
  /** 从用户移除角色 */
  removeRole(username: string, roles: string[], operator: string): Promise<PermissionChangeResult>;
  /** 完全替换用户角色列表 */
  setRoles(username: string, roles: string[], operator: string): Promise<PermissionChangeResult>;
  /** 批量更新用户属性 */
  updateUser(usernames: string[], props: Partial<User>, operator: string): Promise<PermissionChangeResult>;
  /** 查询用户当前角色列表 */
  getUserRoles(username: string): string[];
  /** 查询角色权限集合 */
  getRolePermissions(role: string): Set<string>;
  /** 列出所有角色 */
  listRoles(): string[];
  /** 审计日志（只读） */
  auditLog: AuditEntry[];
  /** 清空审计日志 */
  clearAuditLog(): number;
}
