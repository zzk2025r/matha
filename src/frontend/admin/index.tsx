import { useState, useMemo } from 'react';
import type { User, AuditEntry, RoleConfig } from './types';

// ============================================================
// Mock API - 对接 src/auth/api.py PermissionChangeAPI
// ============================================================
const API = {
  async register(username: string, email: string, password: string, roles: string[]) {
    return new Promise<void>((resolve, reject) =>
      setTimeout(() => {
        if (roles.length === 0) reject(new Error('至少选择一个角色'));
        else resolve();
      }, 50)
    );
  },
  async login(username: string, _password: string) {
    return new Promise<{ roles: string[]; username: string }>((resolve, reject) =>
      setTimeout(() => {
        if (username === 'admin_user') resolve({ roles: ['admin'], username });
        else reject(new Error('用户名或密码错误'));
      }, 30)
    );
  },
  async addRole(username: string, roles: string[], _operator: string) {
    return new Promise<void>((resolve) => setTimeout(resolve, 50));
  },
  async removeRole(username: string, roles: string[], _operator: string) {
    return new Promise<void>((resolve) => setTimeout(resolve, 50));
  },
  async setRoles(username: string, roles: string[], _operator: string) {
    return new Promise<void>((resolve) => setTimeout(resolve, 50));
  },
  async updateUser(username: string, props: Partial<User>, _operator: string) {
    return new Promise<void>((resolve) => setTimeout(resolve, 50));
  },
  async getUsers() {
    return new Promise<User[]>((resolve) =>
      setTimeout(() => resolve(Object.values(state.users)), 30)
    );
  },
  async getAuditLog() {
    return new Promise<AuditEntry[]>((resolve) =>
      setTimeout(() => resolve([...state.auditLog]), 20)
    );
  },
};

// ============================================================
// State (模拟)
// ============================================================
const defaultRoles: RoleConfig[] = [
  { name: 'admin',    displayName: '管理员',  description: '拥有所有权限',             permissions: ['doc:*', 'user:*', 'code:*', 'system:*'] },
  { name: 'editor',   displayName: '编辑者',  description: '可读写文档，执行代码',     permissions: ['doc:read', 'doc:write', 'code:run'] },
  { name: 'viewer',   displayName: '查看者',  description: '只读文档，可执行代码',     permissions: ['doc:read', 'code:run'] },
  { name: 'guest',    displayName: '访客',    description: '只能阅读文档',             permissions: ['doc:read'] },
];

const state = {
  users: {
    admin_user:  { username: 'admin_user',  email: 'admin@test.com',     roles: ['admin'],    active: true,  last_login: Date.now() },
    editor_user: { username: 'editor_user', email: 'editor@test.com',    roles: ['editor'],   active: true,  last_login: Date.now() - 3600000 },
    viewer_user: { username: 'viewer_user', email: 'viewer@test.com',    roles: ['viewer'],   active: true,  last_login: Date.now() - 7200000 },
    guest_user:  { username: 'guest_user',  email: 'guest@test.com',     roles: ['guest'],    active: false, last_login: null },
  },
  roles: defaultRoles,
  customRoles: {} as Record<string, RoleConfig>,
  auditLog: [] as AuditEntry[],
};

let _id = 0;
function genId() { return String(++_id); }

function addAudit(type: AuditEntry['type'], target: string, data: Record<string, unknown>) {
  state.auditLog.unshift({
    time: new Date().toLocaleString('zh-CN'),
    type, target, data,
    operator: 'admin_user',
  });
  if (state.auditLog.length > 200) state.auditLog.length = 200;
}

// ============================================================
// CSS-in-JS styles
// ============================================================
const styles = {
  root: { display: 'flex', minHeight: '100vh', fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif', background: '#f8fafc', color: '#1e293b', fontSize: 14 } as React.CSSProperties,
  sidebar: { width: 240, background: '#1e1b4b', color: '#c7d2fe', display: 'flex', flexDirection: 'column', flexShrink: 0 } as React.CSSProperties,
  sidebarHeader: { padding: '20px 16px', borderBottom: '1px solid #312e81' } as React.CSSProperties,
  sidebarTitle: { fontSize: 16, fontWeight: 700, color: '#e0e7ff' } as React.CSSProperties,
  sidebarSub: { fontSize: 11, color: '#a5b4fc', marginTop: 4 } as React.CSSProperties,
  nav: { flex: 1, padding: 8 } as React.CSSProperties,
  navItem: (active: boolean) => ({
    display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 6,
    color: active ? '#e0e7ff' : '#c7d2fe', cursor: 'pointer', fontSize: 13,
    background: active ? '#312e81' : 'transparent', transition: 'background .15s',
  }) as React.CSSProperties,
  main: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' } as React.CSSProperties,
  topbar: { background: '#fff', borderBottom: '1px solid #e2e8f0', padding: '12px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' } as React.CSSProperties,
  content: { flex: 1, padding: 24, overflowY: 'auto' } as React.CSSProperties,
  card: { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, padding: 20, marginBottom: 20 } as React.CSSProperties,
  cardTitle: { fontSize: 15, fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 } as React.CSSProperties,
  badge: { fontSize: 11, padding: '2px 8px', borderRadius: 10, background: '#e0e7ff', color: '#4f46e5', fontWeight: 500 } as React.CSSProperties,
  stats: { display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, marginBottom: 20 } as React.CSSProperties,
  statCard: { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '16px 20px' } as React.CSSProperties,
  statValue: { fontSize: 28, fontWeight: 700, color: '#4f46e5' } as React.CSSProperties,
  statLabel: { fontSize: 12, color: '#64748b', marginTop: 4 } as React.CSSProperties,
  table: { width: '100%', borderCollapse: 'collapse' } as React.CSSProperties,
  th: { padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: '#64748b', fontSize: 12, textTransform: 'uppercase', letterSpacing: '.5px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' } as React.CSSProperties,
  td: { padding: '10px 14px', borderBottom: '1px solid #e2e8f0', fontSize: 13 } as React.CSSProperties,
  trHover: { transition: 'background .1s' } as React.CSSProperties,
  search: { display: 'flex', gap: 10, marginBottom: 16 } as React.CSSProperties,
  input: { padding: '9px 12px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 14, width: 280 } as React.CSSProperties,
  select: { padding: '9px 12px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 13, background: '#fff' } as React.CSSProperties,
  btnPrimary: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 500, background: '#4f46e5', color: '#fff', transition: 'background .15s' } as React.CSSProperties,
  btnDanger: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 500, background: '#ef4444', color: '#fff', transition: 'background .15s' } as React.CSSProperties,
  btnOutline: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 6, border: '1px solid #e2e8f0', cursor: 'pointer', fontSize: 13, fontWeight: 500, background: '#fff', color: '#1e293b', transition: 'background .15s' } as React.CSSProperties,
  btnSm: { padding: '4px 10px', fontSize: 12 } as React.CSSProperties,
  roleTag: (role: string) => {
    const colors: Record<string, { bg: string; color: string }> = {
      admin: { bg: '#fef3c7', color: '#92400e' }, editor: { bg: '#dbeafe', color: '#1e40af' },
      viewer: { bg: '#d1fae5', color: '#065f46' }, guest: { bg: '#f1f5f9', color: '#475569' },
    };
    const c = colors[role] || colors.guest;
    return { display: 'inline-block', padding: '2px 10px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: c.bg, color: c.color, margin: '1px 2px' } as React.CSSProperties;
  },
  statusDot: (active: boolean) => ({
    display: 'inline-block', width: 8, height: 8, borderRadius: '50%', marginRight: 6,
    background: active ? '#22c55e' : '#ef4444',
  }) as React.CSSProperties,
  checkboxGroup: { display: 'flex', flexWrap: 'wrap', gap: 8 } as React.CSSProperties,
  checkboxItem: (checked: boolean) => ({
    display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px',
    border: checked ? '2px solid #4f46e5' : '1px solid #e2e8f0',
    borderRadius: 6, cursor: 'pointer', transition: 'all .15s', fontSize: 13,
    background: checked ? '#eef2ff' : '#fff', color: checked ? '#4f46e5' : '#1e293b',
  }) as React.CSSProperties,
  // Modal
  overlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 } as React.CSSProperties,
  modal: { background: '#fff', borderRadius: 12, width: 520, maxWidth: '90vw', maxHeight: '85vh', overflow: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,.2)' } as React.CSSProperties,
  modalHeader: { padding: '20px 24px 16px', borderBottom: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' } as React.CSSProperties,
  modalBody: { padding: '20px 24px' } as React.CSSProperties,
  modalFooter: { padding: '16px 24px', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end', gap: 8 } as React.CSSProperties,
  formGroup: { marginBottom: 16 } as React.CSSProperties,
  formLabel: { display: 'block', fontSize: 12, fontWeight: 600, color: '#64748b', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '.5px' } as React.CSSProperties,
  formInput: { width: '100%', padding: '9px 12px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 14 } as React.CSSProperties,
  formHint: { fontSize: 12, color: '#64748b', marginTop: 4 } as React.CSSProperties,
  // Audit
  auditEntry: { display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 0', borderBottom: '1px solid #e2e8f0', fontSize: 13 } as React.CSSProperties,
  auditTime: { color: '#64748b', fontSize: 12, whiteSpace: 'nowrap', minWidth: 140 } as React.CSSProperties,
  auditType: (type: string) => {
    const colors: Record<string, { bg: string; color: string }> = {
      add_role: { bg: '#d1fae5', color: '#065f46' }, remove_role: { bg: '#fee2e2', color: '#991b1b' },
      set_role: { bg: '#dbeafe', color: '#1e40af' }, update_user: { bg: '#fef3c7', color: '#92400e' },
    };
    const c = colors[type] || colors.update_user;
    return { display: 'inline-block', padding: '1px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, background: c.bg, color: c.color, marginRight: 8 } as React.CSSProperties;
  },
  toast: (type: 'success' | 'error' | 'info') => ({
    padding: '12px 20px', borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 500,
    boxShadow: '0 4px 12px rgba(0,0,0,.15)', marginBottom: 8,
    background: type === 'success' ? '#16a34a' : type === 'error' ? '#dc2626' : '#4f46e5',
  }) as React.CSSProperties,
};

// ============================================================
// Toast
// ============================================================
function showToast(message: string, type: 'success' | 'error' | 'info' = 'info') {
  const container = document.getElementById('mta-toasts');
  if (!container) return;
  const el = document.createElement('div');
  el.style.cssText = styles.toast(type).cssText;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(() => el.remove(), 300); }, 3000);
}

// ============================================================
// Stat Card
// ============================================================
function StatCard({ value, label }: { value: number | string; label: string }) {
  return (
    <div style={styles.statCard}>
      <div style={styles.statValue}>{value}</div>
      <div style={styles.statLabel}>{label}</div>
    </div>
  );
}

// ============================================================
// User Modal
// ============================================================
interface UserModalProps {
  editing?: User | null;
  onClose: () => void;
}
function UserModal({ editing, onClose }: UserModalProps) {
  const isEdit = !!editing;
  const [username, setUsername] = useState(editing?.username ?? '');
  const [email, setEmail] = useState(editing?.email ?? '');
  const [password, setPassword] = useState('');
  const [roles, setRoles] = useState<string[]>(editing?.roles ?? ['viewer']);
  const allRoles = ['admin', 'editor', 'viewer', 'guest'];

  const toggleRole = (r: string) => {
    setRoles(prev => prev.includes(r) ? prev.filter(x => x !== r) : [...prev, r]);
  };

  const handleSubmit = async () => {
    if (!username.trim() || !email.trim() || !isEdit && !password) {
      showToast('请填写完整信息', 'error'); return;
    }
    try {
      if (isEdit) {
        await API.setRoles(username, roles, 'admin_user');
        state.users[username] = { ...state.users[username], email, roles };
        addAudit('set_role', username, { roles });
        showToast(`已更新 ${username}`, 'success');
      } else {
        await API.register(username, email, password, roles);
        state.users[username] = { username, email, roles, active: true, last_login: null };
        addAudit('add_role', username, { roles });
        showToast(`已创建用户 ${username}`, 'success');
      }
      onClose();
      window.dispatchEvent(new Event('mta-reload'));
    } catch (e: unknown) {
      showToast((e as Error).message, 'error');
    }
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()}>
        <div style={styles.modalHeader}>
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>{isEdit ? `编辑用户: ${username}` : '添加用户'}</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: '#64748b' }}>&times;</button>
        </div>
        <div style={styles.modalBody}>
          <div style={styles.formGroup}>
            <label style={styles.formLabel}>用户名</label>
            <input style={styles.formInput} value={username}
              onChange={e => setUsername(e.target.value.toLowerCase().replace(/\s/g, '_'))}
              placeholder="zhangsan" disabled={isEdit} />
            <div style={styles.formHint}>小写字母、数字、下划线</div>
          </div>
          <div style={styles.formGroup}>
            <label style={styles.formLabel}>邮箱</label>
            <input style={styles.formInput} type="email" value={email}
              onChange={e => setEmail(e.target.value)} placeholder="user@example.com" />
          </div>
          {!isEdit && (
            <div style={styles.formGroup}>
              <label style={styles.formLabel}>密码</label>
              <input style={styles.formInput} type="password" value={password}
                onChange={e => setPassword(e.target.value)} placeholder="至少 6 位，含字母和数字" />
            </div>
          )}
          <div style={styles.formGroup}>
            <label style={styles.formLabel}>角色</label>
            <div style={styles.checkboxGroup}>
              {allRoles.map(r => (
                <div key={r} style={styles.checkboxItem(roles.includes(r))}
                  onClick={() => toggleRole(r)}>
                  <span style={{ width: 16, height: 16, border: '2px solid', borderRadius: 3,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10,
                    borderColor: roles.includes(r) ? '#4f46e5' : '#e2e8f0',
                    background: roles.includes(r) ? '#4f46e5' : 'transparent', color: '#fff' }}>
                    {roles.includes(r) ? '✓' : ''}
                  </span>
                  {r}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div style={styles.modalFooter}>
          <button style={styles.btnOutline} onClick={onClose}>取消</button>
          <button style={styles.btnPrimary} onClick={handleSubmit}>保存</button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// User Table
// ============================================================
function UserTable() {
  const [users, setUsers] = useState<User[]>(Object.values(state.users));
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);

  window.addEventListener('mta-reload', () => {
    setUsers(Object.values(state.users));
  });

  const filtered = users.filter(u =>
    (!search || u.username.includes(search) || u.email.includes(search)) &&
    (!roleFilter || u.roles.includes(roleFilter))
  );

  const openEdit = (u: User) => { setEditing(u); setModalOpen(true); };
  const openAdd = () => { setEditing(null); setModalOpen(true); };

  const handleDelete = (u: User) => {
    if (!confirm(`确定删除用户 "${u.username}"？`)) return;
    delete state.users[u.username];
    addAudit('remove_role', u.username, { roles: u.roles });
    setUsers(Object.values(state.users));
    showToast(`已删除 ${u.username}`, 'success');
  };

  const handleToggle = async (u: User) => {
    try {
      await API.updateUser(u.username, { active: !u.active }, 'admin_user');
      u.active = !u.active;
      addAudit('update_user', u.username, { is_active: u.active });
      setUsers([...Object.values(state.users)]);
      showToast(`已${u.active ? '启用' : '禁用'} ${u.username}`, 'success');
    } catch { /* ignored */ }
  };

  return (
    <div>
      <div style={styles.card}>
        <div style={styles.cardTitle}>用户列表 <span style={styles.badge}>{filtered.length} 人</span></div>
        <div style={styles.search}>
          <input style={styles.input} placeholder="搜索用户名 / 邮箱..." value={search}
            onChange={e => setSearch(e.target.value)} />
          <select style={styles.select} value={roleFilter}
            onChange={e => setRoleFilter(e.target.value)}>
            <option value="">全部角色</option>
            <option value="admin">admin</option>
            <option value="editor">editor</option>
            <option value="viewer">viewer</option>
            <option value="guest">guest</option>
          </select>
          <button style={styles.btnPrimary} onClick={openAdd}>+ 添加用户</button>
        </div>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>用户名</th><th style={styles.th}>邮箱</th>
              <th style={styles.th}>角色</th><th style={styles.th}>状态</th>
              <th style={styles.th}>最后登录</th><th style={styles.th}>操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(u => (
              <tr key={u.username} style={styles.trHover}
                onMouseEnter={e => (e.currentTarget.style.background = '#f8fafc')}
                onMouseLeave={e => (e.currentTarget.style.background = '')}>
                <td style={styles.td}><strong>{u.username}</strong></td>
                <td style={styles.td}>{u.email}</td>
                <td style={styles.td}>{u.roles.map(r => <span key={r} style={styles.roleTag(r)}>{r}</span>)}</td>
                <td style={styles.td}><span style={styles.statusDot(u.active)} />{u.active ? '启用' : '禁用'}</td>
                <td style={styles.td}>{u.last_login ? new Date(u.last_login).toLocaleString('zh-CN') : '从未'}</td>
                <td style={styles.td}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button style={{ ...styles.btnOutline, ...styles.btnSm }} onClick={() => openEdit(u)}>编辑</button>
                    <button style={{ ...styles.btnOutline, ...styles.btnSm }} onClick={() => handleToggle(u)}>{u.active ? '禁用' : '启用'}</button>
                    <button style={{ ...styles.btnDanger, ...styles.btnSm }} onClick={() => handleDelete(u)}>删除</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {modalOpen && <UserModal editing={editing} onClose={() => setModalOpen(false)} />}
    </div>
  );
}

// ============================================================
// Role Matrix
// ============================================================
function RoleMatrix() {
  const allPerms = [
    { key: 'doc:read', label: '读取' }, { key: 'doc:write', label: '编辑' },
    { key: 'doc:delete', label: '删除' }, { key: 'user:manage', label: '用户管理' },
    { key: 'code:run', label: '运行' }, { key: 'code:debug', label: '调试' },
    { key: 'system:*', label: '系统' },
  ];

  const roles = [...state.roles, ...Object.entries(state.customRoles).map(([k, v]) => ({ name: k, ...v }))];

  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>角色权限矩阵</div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>角色</th>
            {allPerms.map(p => <th key={p.key} style={styles.th}>{p.label}</th>)}
            <th style={styles.th}>操作</th>
          </tr>
        </thead>
        <tbody>
          {roles.map(r => {
            const isDefault = state.roles.some(d => d.name === r.name);
            return (
              <tr key={r.name}>
                <td style={styles.td}><strong>{r.name}</strong>{!isDefault && <span style={{ ...styles.badge, marginLeft: 6 }}>自定义</span>}</td>
                {allPerms.map(p => {
                  const has = (r as RoleConfig & { permissions?: string[] }).permissions?.some(
                    perm => perm === p.key || (perm.endsWith(':*') && perm.split(':')[0] === p.key.split(':')[0])
                  ) ?? false;
                  return <td key={p.key} style={{ ...styles.td, textAlign: 'center' }}>{has ? <span style={{ color: '#22c55e' }}>✓</span> : <span style={{ color: '#94a3b8' }}>—</span>}</td>;
                })}
                <td style={styles.td}>
                  {isDefault
                    ? <span style={{ color: '#94a3b8', fontSize: 12 }}>内置</span>
                    : <button style={{ ...styles.btnDanger, ...styles.btnSm }} onClick={() => {
                        delete state.customRoles[r.name];
                        Object.values(state.users).forEach(u => { const i = u.roles.indexOf(r.name); if (i > -1) u.roles.splice(i, 1); });
                        addAudit('remove_role', `[role:${r.name}]`, {});
                        window.dispatchEvent(new Event('mta-reload'));
                        showToast(`已删除角色 ${r.name}`, 'success');
                      }}>删除</button>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ============================================================
// Audit Log
// ============================================================
function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>(state.auditLog);

  window.addEventListener('mta-reload', () => setEntries([...state.auditLog]));

  const typeLabel: Record<string, string> = {
    add_role: '添加角色', remove_role: '移除角色', set_role: '设置角色', update_user: '更新用户',
  };

  const clearAll = () => {
    if (!confirm('清空所有审计日志？')) return;
    state.auditLog = [];
    setEntries([]);
    showToast('审计日志已清空', 'info');
  };

  return (
    <div style={styles.card}>
      <div style={{ ...styles.cardTitle, justifyContent: 'space-between' }}>
        <span>审计日志</span>
        <button style={{ ...styles.btnOutline, ...styles.btnSm }} onClick={clearAll}>清空日志</button>
      </div>
      {entries.length === 0
        ? <div style={{ color: '#94a3b8', padding: 20, fontSize: 13 }}>暂无审计记录。</div>
        : entries.map((e, i) => (
            <div key={i} style={styles.auditEntry}>
              <span style={styles.auditTime}>{e.time}</span>
              <span style={styles.auditType(e.type)}>{typeLabel[e.type] || e.type}</span>
              <span style={{ color: '#1e293b' }}>
                目标: <strong>{e.target}</strong>
                {'roles' in e.data && <span> → {JSON.stringify(e.data.roles)}</span>}
                {'is_active' in e.data && <span> → 启用={e.data.is_active}</span>}
              </span>
              <span style={{ color: '#94a3b8', fontSize: 12, marginLeft: 'auto' }}>操作者: {e.operator}</span>
            </div>
          ))
      }
    </div>
  );
}

// ============================================================
// System Config
// ============================================================
function SystemConfig() {
  const [cfg, setCfg] = useState({ ...state.config });

  const update = (key: keyof typeof cfg, val: number) => setCfg(p => ({ ...p, [key]: val }));

  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>系统配置</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {[
          ['accessExp', 'Access Token 有效期 (小时)', cfg.accessExp],
          ['refreshExp', 'Refresh Token 有效期 (天)', cfg.refreshExp],
          ['minPw', '密码最小长度', cfg.minPw],
          ['maxSessions', '单用户最大会话数', cfg.maxSessions],
          ['lockAttempts', '登录失败锁定次数', cfg.lockAttempts],
          ['lockDuration', '锁定持续时间 (分钟)', cfg.lockDuration],
        ].map(([key, label, val]) => (
          <div key={key as string} style={styles.formGroup}>
            <label style={styles.formLabel}>{label}</label>
            <input style={styles.formInput} type="number" value={val as number}
              onChange={e => update(key as keyof typeof cfg, Number(e.target.value))} />
          </div>
        ))}
      </div>
      <div style={{ marginTop: 16 }}>
        <button style={styles.btnPrimary} onClick={() => {
          state.config = cfg;
          showToast('配置已保存', 'success');
        }}>保存配置</button>
      </div>
    </div>
  );
}

// ============================================================
// Main App
// ============================================================
export default function MathaAdminApp() {
  const [activeTab, setActiveTab] = useState('users');
  const [users] = useState(Object.values(state.users));
  const [auditCount, setAuditCount] = useState(state.auditLog.length);

  window.addEventListener('mta-reload', () => setAuditCount(state.auditLog.length));

  const titles: Record<string, string> = { users: '用户管理', roles: '角色管理', audit: '审计日志', config: '系统配置' };

  return (
    <div style={styles.root}>
      {/* Sidebar */}
      <aside style={styles.sidebar}>
        <div style={styles.sidebarHeader}>
          <div style={styles.sidebarTitle}>🔐 Matha Admin</div>
          <div style={styles.sidebarSub}>权限管理系统 v3.1</div>
        </div>
        <nav style={styles.nav}>
          {(['users', 'roles', 'audit', 'config'] as const).map(tab => (
            <div key={tab} style={styles.navItem(activeTab === tab)}
              onClick={() => setActiveTab(tab)}>
              <span style={{ fontSize: 16, width: 20, textAlign: 'center' }}>
                {tab === 'users' ? '👥' : tab === 'roles' ? '🛡️' : tab === 'audit' ? '📋' : '⚙️'}
              </span>
              {titles[tab]}
            </div>
          ))}
        </nav>
      </aside>

      {/* Main */}
      <main style={styles.main}>
        <div style={styles.topbar}>
          <div style={{ fontSize: 18, fontWeight: 600 }}>{titles[activeTab]}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#64748b' }}>
            <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#4f46e5', color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 600 }}>A</div>
            <span>Admin</span>
            <span style={{ ...styles.roleTag('admin'), marginLeft: 8 }}>admin</span>
          </div>
        </div>

        <div style={styles.content}>
          {/* Stats */}
          <div style={styles.stats}>
            <StatCard value={users.length} label="总用户数" />
            <StatCard value={users.filter(u => u.active).length} label="在线会话" />
            <StatCard value={state.roles.length + Object.keys(state.customRoles).length} label="角色数量" />
            <StatCard value={auditCount} label="审计记录" />
          </div>

          {/* Tab Content */}
          {activeTab === 'users' && <UserTable />}
          {activeTab === 'roles' && <><RoleMatrix /></>}
          {activeTab === 'audit' && <AuditLog />}
          {activeTab === 'config' && <SystemConfig />}
        </div>
      </main>

      {/* Toast Container */}
      <div id="mta-toasts" style={{ position: 'fixed', top: 20, right: 20, zIndex: 200, display: 'flex', flexDirection: 'column', gap: 8 }} />
    </div>
  );
}
