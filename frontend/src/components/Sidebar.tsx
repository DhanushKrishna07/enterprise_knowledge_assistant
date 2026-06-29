import type { AskFilters, User } from '../types';

interface Props {
  user: User;
  filters: AskFilters;
  onFiltersChange: (filters: AskFilters) => void;
  onNewChat: () => void;
  onLogout: () => void;
  onShowAdmin: () => void;
  showAdmin: boolean;
}

/** Return the departments a given role is allowed to see */
function allowedDepartments(role: string, userDept: string): { value: string; label: string }[] {
  if (role === 'admin') {
    return [
      { value: 'general', label: 'General' },
      { value: 'hr', label: 'HR' },
      { value: 'it', label: 'IT' },
      { value: 'security', label: 'Security' },
    ];
  }
  // Non-admin: they can only see their own department (plus General)
  const base = [{ value: 'general', label: 'General' }];
  if (userDept && userDept !== 'general') {
    const label = userDept.charAt(0).toUpperCase() + userDept.slice(1);
    base.push({ value: userDept, label });
  }
  return base;
}

/** Capitalise first letter of a word */
function cap(s: string) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

export default function Sidebar({
  user,
  filters,
  onFiltersChange,
  onNewChat,
  onLogout,
  onShowAdmin,
  showAdmin,
}: Props) {
  const update = (key: keyof AskFilters, value: string) => {
    onFiltersChange({ ...filters, [key]: value || undefined });
  };

  const deptOptions = allowedDepartments(user.role, user.department);
  // Admin shows "all" role label — replace with a cleaner display
  const roleLabel = user.role === 'admin' ? 'Admin' : cap(user.role);
  const deptLabel = cap(user.department);

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">🧠</div>
          <span>EKA</span>
        </div>
      </div>

      <div className="sidebar-section">
        <button className="new-chat-btn" onClick={onNewChat}>
          ✨ New conversation
        </button>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-title">Search Filters</div>

        <div className="filter-group">
          <label>
            Department
            <span className="filter-hint"> — narrow results to a specific department</span>
          </label>
          <select
            value={filters.department || ''}
            onChange={(e) => update('department', e.target.value)}
          >
            <option value="">All accessible departments</option>
            {deptOptions.map((d) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>
            Document Type
            <span className="filter-hint"> — filter by document category</span>
          </label>
          <select
            value={filters.document_type || ''}
            onChange={(e) => update('document_type', e.target.value)}
          >
            <option value="">All types</option>
            <option value="policy">Policy</option>
            <option value="faq">FAQ</option>
            <option value="guide">Guide</option>
          </select>
        </div>

        <div className="filter-group">
          <label>
            Content Type
            <span className="filter-hint"> — text, tables, or OCR-scanned content</span>
          </label>
          <select
            value={filters.content_types?.[0] || ''}
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                content_types: e.target.value ? [e.target.value] : undefined,
              })
            }
          >
            <option value="">All content</option>
            <option value="text">Text</option>
            <option value="table">Table</option>
            <option value="ocr_text">OCR Text</option>
          </select>
        </div>

        <div className="filter-group">
          <label>
            Uploaded After
            <span className="filter-hint"> — only search documents added after this date</span>
          </label>
          <input
            type="date"
            value={filters.uploaded_after?.slice(0, 10) || ''}
            onChange={(e) => update('uploaded_after', e.target.value ? `${e.target.value}T00:00:00Z` : '')}
          />
        </div>
      </div>

      {user.role === 'admin' && (
        <div className="sidebar-section">
          <div className="sidebar-section-title">Admin</div>
          <button
            className={`btn btn-secondary`}
            style={{ width: '100%', fontSize: 13 }}
            onClick={onShowAdmin}
          >
            {showAdmin ? '💬 Back to Chat' : '📊 Dashboard'}
          </button>
        </div>
      )}

      <div className="sidebar-footer">
        <div className="user-info">
          <div className="user-avatar">{user.email[0].toUpperCase()}</div>
          <div className="user-details">
            <div className="user-email">{user.email}</div>
            <div className="user-role">{roleLabel} · {deptLabel}</div>
          </div>
        </div>
        <button className="btn btn-secondary" style={{ width: '100%', fontSize: 13 }} onClick={onLogout}>
          Sign out
        </button>
      </div>
    </aside>
  );
}
