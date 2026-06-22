import { NavLink, Outlet } from 'react-router-dom'
import { logout } from '../lib/auth'
import styles from './Layout.module.css'

const NAV = [
  { to: '/',             label: '🏠 대시보드', end: true  },
  { to: '/events',       label: '📋 이벤트 목록', end: true },
  { to: '/review-queue', label: '⚠️ 의심 큐',  end: false },
  { to: '/stats',        label: '📊 통계',      end: true  },
]

export default function Layout() {
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.logo}>🛡️ GateGuard</div>
        <nav className={styles.nav}>
          {NAV.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `${styles.link} ${isActive ? styles.active : ''}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <button className={styles.logout} onClick={logout}>
          로그아웃
        </button>
      </aside>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
