import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { clientApi } from '../../services/client.js'

/**
 * Reusable Client Company Portal layout.
 * Desktop keeps the original hover navigation.
 * Compact screens use a measured one-line nav with overflow in a More menu.
 */
export default function ClientLayout({ title, breadcrumb, children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const refreshCounterRef = useRef(0)

  const [openMenuKey, setOpenMenuKey] = useState(null)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [databaseNavItems, setDatabaseNavItems] = useState([])
  const [visibleNavCount, setVisibleNavCount] = useState(0)
  const [moreMenuOpen, setMoreMenuOpen] = useState(false)
  const [compactMenu, setCompactMenu] = useState(null)
  const [compactOpenPaths, setCompactOpenPaths] = useState({})
  const [compactMenuPosition, setCompactMenuPosition] = useState(null)

  const userMenuRef = useRef(null)
  const navRef = useRef(null)
  const measureNavRef = useRef(null)
  const moreButtonRef = useRef(null)
  const moreMenuRef = useRef(null)
  const compactMenuRef = useRef(null)
  const compactTriggerRefs = useRef(new Map())
  const resizeObserverRef = useRef(null)

  const companyName = user?.company_name || user?.company?.name || ''

  const isCompactNav = useCompactBreakpoint()

  const handleNavClick = (event, to) => {
    const target = new URL(to, window.location.origin)

    if (
      target.pathname !== location.pathname ||
      target.search !== location.search
    ) {
      return
    }

    event.preventDefault()
    closeAllMenus()

    refreshCounterRef.current += 1

    navigate(
      {
        pathname: location.pathname,
        search: location.search,
      },
      {
        replace: true,
        state: {
          ...(location.state || {}),
          __refreshKey: refreshCounterRef.current,
        },
      },
    )
  }

  function closeAllMenus() {
    setOpenMenuKey(null)
    setUserMenuOpen(false)
    setMoreMenuOpen(false)
    setCompactMenu(null)
    setCompactOpenPaths({})
    setCompactMenuPosition(null)
  }

  useEffect(() => {
    const loadNavigationMenu = async () => {
      try {
        const res = await clientApi.getNavigationMenu(user?.id)
        setDatabaseNavItems(Array.isArray(res) ? res : [])
      } catch (error) {
        console.error('Failed to load navigation menu:', error)
        setDatabaseNavItems([])
      }
    }

    loadNavigationMenu()
  }, [user?.id])

  useEffect(() => {
    if (!isCompactNav) {
      setMoreMenuOpen(false)
      setCompactMenu(null)
      setCompactOpenPaths({})
      setCompactMenuPosition(null)
    } else {
      setOpenMenuKey(null)
    }
  }, [isCompactNav])

  const calculateVisibleNav = useCallback(() => {
    const nav = navRef.current
    const measureNav = measureNavRef.current

    if (!nav || !measureNav || !databaseNavItems.length || !isCompactNav) {
      setVisibleNavCount(databaseNavItems.length)
      return
    }

    const availableWidth = nav.clientWidth
    const nodes = Array.from(measureNav.children)
    const widths = nodes.map((node) => Math.ceil(node.getBoundingClientRect().width))
    const gap = 4
    const moreWidth = 40
    const safety = 4

    let used = 0
    let count = 0

    for (let index = 0; index < widths.length; index += 1) {
      const next = used + (count > 0 ? gap : 0) + widths[index]
      const reserveMore = index < widths.length - 1 ? gap + moreWidth : 0
      if (next + reserveMore + safety > availableWidth) break
      used = next
      count += 1
    }

    setVisibleNavCount(count)
  }, [databaseNavItems, isCompactNav])

  useEffect(() => {
    calculateVisibleNav()

    const nav = navRef.current
    if (!nav || !isCompactNav || typeof ResizeObserver === 'undefined') return undefined

    const observer = new ResizeObserver(() => calculateVisibleNav())
    observer.observe(nav)
    resizeObserverRef.current = observer

    return () => {
      observer.disconnect()
      if (resizeObserverRef.current === observer) {
        resizeObserverRef.current = null
      }
    }
  }, [calculateVisibleNav, isCompactNav])

  const getCompactMenuPosition = useCallback((element) => {
    if (!element) return null

    const rect = element.getBoundingClientRect()
    const width = Math.min(280, Math.max(180, window.innerWidth - 16))
    const left = Math.min(
      Math.max(8, rect.right - width),
      Math.max(8, window.innerWidth - width - 8),
    )

    return {
      top: Math.min(rect.bottom + 6, window.innerHeight - 8),
      left,
      width,
      maxHeight: Math.max(180, Math.min(560, window.innerHeight - rect.bottom - 16)),
    }
  }, [])

  const openCompactMenu = useCallback((type, itemKey, element) => {
    const next = type === 'more'
      ? { type: 'more' }
      : { type: 'item', key: itemKey }

    setCompactMenu(next)
    setCompactOpenPaths({})
    setMoreMenuOpen(type === 'more')
    setOpenMenuKey(null)
    setCompactMenuPosition(getCompactMenuPosition(element))
  }, [getCompactMenuPosition])

  useEffect(() => {
    if (!isCompactNav || !compactMenu) return undefined

    const reposition = () => {
      const element = compactMenu.type === 'more'
        ? moreButtonRef.current
        : compactTriggerRefs.current.get(compactMenu.key)
      setCompactMenuPosition(getCompactMenuPosition(element))
    }

    window.addEventListener('resize', reposition)
    window.addEventListener('scroll', reposition, true)
    reposition()

    return () => {
      window.removeEventListener('resize', reposition)
      window.removeEventListener('scroll', reposition, true)
    }
  }, [compactMenu, getCompactMenuPosition, isCompactNav])

  useEffect(() => {
    const handleClickOutside = (event) => {
      const target = event.target

      if (userMenuRef.current && !userMenuRef.current.contains(target)) {
        setUserMenuOpen(false)
      }

      if (
        compactMenuRef.current &&
        !compactMenuRef.current.contains(target) &&
        !Array.from(compactTriggerRefs.current.values()).some((node) => node?.contains(target)) &&
        !moreButtonRef.current?.contains(target)
      ) {
        setCompactMenu(null)
        setCompactOpenPaths({})
        setMoreMenuOpen(false)
        setCompactMenuPosition(null)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleLogout = async () => {
    closeAllMenus()
    await logout()
    navigate('/login', { replace: true })
  }

  const initials = user
    ? `${user.first_name?.[0] || ''}${user.last_name?.[0] || ''}`.toUpperCase() || 'U'
    : 'U'

  const buildMenuSearch = (queryParams = {}) => {
    const search = new URLSearchParams()
    Object.entries(queryParams || {}).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        search.set(key, String(value))
      }
    })
    const text = search.toString()
    return text ? `?${text}` : ''
  }

  // Desktop navigation: intentionally kept close to the last known-good implementation.
  const renderDesktopMenuItem = (item, level = 0) => {
    const children = Array.isArray(item?.children) ? item.children : []
    const hasChildren = children.length > 0
    const route = item.route ? `${item.route}${buildMenuSearch(item.query_params)}` : ''

    if (level === 0) {
      const isMenuOpen = openMenuKey === item.key

      return (
        <div
          key={item.key}
          className="group/top relative shrink-0"
          onMouseEnter={() => {
            if (hasChildren) setOpenMenuKey(item.key)
          }}
          onMouseLeave={() => {
            setOpenMenuKey(null)
          }}
        >
          {hasChildren ? (
            <div className="flex items-center rounded-md">
              {route ? (
                <NavLink
                  to={route}
                  onClick={(event) => handleNavClick(event, route)}
                  className={({ isActive }) =>
                    `flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]'
                        : 'text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]'
                    }`
                  }
                >
                  <span className="whitespace-nowrap">{item.name}</span>
                </NavLink>
              ) : (
                <span className="px-3 py-2 text-sm font-medium text-[var(--color-ink-soft)] whitespace-nowrap">
                  {item.name}
                </span>
              )}

              <button
                type="button"
                aria-label={`Open ${item.name} menu`}
                aria-expanded={isMenuOpen}
                onClick={(event) => {
                  event.preventDefault()
                  event.stopPropagation()
                  setOpenMenuKey((current) => current === item.key ? null : item.key)
                }}
                className="rounded-r-md px-1.5 py-2 text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3.5 w-3.5">
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </button>
            </div>
          ) : route ? (
            <NavLink
              to={route}
              onClick={(event) => handleNavClick(event, route)}
              className={({ isActive }) =>
                `flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]'
                    : 'text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]'
                }`
              }
            >
              <span className="whitespace-nowrap">{item.name}</span>
            </NavLink>
          ) : (
            <button type="button" className="flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]">
              <span className="whitespace-nowrap">{item.name}</span>
            </button>
          )}

          {hasChildren && (
            <div className={`absolute left-0 top-full z-50 mt-1 min-w-56 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-1 shadow-xl transition-all ${isMenuOpen ? 'visible opacity-100' : 'invisible opacity-0'}`}>
              {children.map((child) => renderDesktopMenuItem(child, 1))}
            </div>
          )}
        </div>
      )
    }

    return (
      <div key={item.key} className="group/submenu relative">
        {route ? (
          <NavLink
            to={route}
            onClick={(event) => handleNavClick(event, route)}
            className={({ isActive }) => `flex w-full items-center justify-between gap-4 rounded-md px-3 py-2 text-left text-sm transition-colors ${isActive ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]' : 'text-[var(--color-ink)] hover:bg-[var(--color-canvas)]'}`}
          >
            <span className="min-w-0 truncate">{item.name}</span>
            {hasChildren && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3.5 w-3.5 shrink-0"><path d="m9 6 6 6-6 6" /></svg>}
          </NavLink>
        ) : (
          <button type="button" className="flex w-full items-center justify-between gap-4 rounded-md px-3 py-2 text-left text-sm text-[var(--color-ink)] hover:bg-[var(--color-canvas)]">
            <span className="min-w-0 truncate">{item.name}</span>
            {hasChildren && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3.5 w-3.5 shrink-0"><path d="m9 6 6 6-6 6" /></svg>}
          </button>
        )}
        {hasChildren && (
          <div className="invisible absolute left-full top-0 z-50 ml-1 min-w-56 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-1 opacity-0 shadow-xl transition-all group-hover/submenu:visible group-hover/submenu:opacity-100 group-focus-within/submenu:visible group-focus-within/submenu:opacity-100">
            {children.map((child) => renderDesktopMenuItem(child, level + 1))}
          </div>
        )}
      </div>
    )
  }

  const renderCompactMenuItem = (item, path = '') => {
    const children = Array.isArray(item?.children) ? item.children : []
    const hasChildren = children.length > 0
    const route = item.route ? `${item.route}${buildMenuSearch(item.query_params)}` : ''
    const currentPath = path ? `${path}/${item.key}` : String(item.key)
    const isOpen = Boolean(compactOpenPaths[currentPath])

    if (!hasChildren) {
      return route ? (
        <NavLink
          key={currentPath}
          to={route}
          onClick={() => {
            setCompactMenu(null)
            setMoreMenuOpen(false)
            setCompactOpenPaths({})
            setCompactMenuPosition(null)
          }}
          className={({ isActive }) => `flex w-full min-w-0 items-center rounded-md px-3 py-2.5 text-sm ${isActive ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]' : 'text-[var(--color-ink)] hover:bg-[var(--color-canvas)]'}`}
        >
          <span className="min-w-0 truncate">{item.name}</span>
        </NavLink>
      ) : (
        <span key={currentPath} className="block w-full px-3 py-2.5 text-sm text-[var(--color-ink)]">
          {item.name}
        </span>
      )
    }

    return (
      <div key={currentPath} className="min-w-0">
        <div className="flex min-w-0 items-center gap-1">
          {route ? (
            <NavLink
              to={route}
              onClick={(event) => handleNavClick(event, route)}
              className={({ isActive }) => `min-w-0 flex-1 rounded-md px-3 py-2.5 text-sm ${isActive ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]' : 'text-[var(--color-ink)] hover:bg-[var(--color-canvas)]'}`}
            >
              <span className="block truncate">{item.name}</span>
            </NavLink>
          ) : (
            <span className="min-w-0 flex-1 px-3 py-2.5 text-sm text-[var(--color-ink)]">{item.name}</span>
          )}
          <button
            type="button"
            aria-label={`${isOpen ? 'Close' : 'Open'} ${item.name} submenu`}
            aria-expanded={isOpen}
            onClick={(event) => {
              event.preventDefault()
              event.stopPropagation()
              setCompactOpenPaths((current) => ({
                ...current,
                [currentPath]: !current[currentPath],
              }))
            }}
            className="shrink-0 rounded-md p-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}>
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        </div>
        {isOpen && (
          <div className="ml-3 mt-1 border-l border-[var(--color-border)] pl-2">
            {children.map((child) => renderCompactMenuItem(child, currentPath))}
          </div>
        )}
      </div>
    )
  }

  const compactPortal = isCompactNav && compactMenu && compactMenuPosition
    ? createPortal(
        <div
          ref={compactMenuRef}
          className="fixed z-[200] overflow-x-hidden overflow-y-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-2 shadow-xl"
          style={{
            top: compactMenuPosition.top,
            left: compactMenuPosition.left,
            width: compactMenuPosition.width,
            maxWidth: 'calc(100vw - 16px)',
            maxHeight: compactMenuPosition.maxHeight,
          }}
        >
          {compactMenu.type === 'more'
            ? databaseNavItems.slice(visibleNavCount).map((item) => renderCompactMenuItem(item))
            : databaseNavItems
                .filter((item) => item.key === compactMenu.key)
                .flatMap((item) => item.children || [])
                .map((item) => renderCompactMenuItem(item))}
        </div>,
        document.body,
      )
    : null

  return (
    <div className="flex min-h-screen min-w-0 flex-col overflow-x-hidden bg-[var(--color-canvas)]">
      <header className="relative z-[150] border-b border-[var(--color-border)] bg-[var(--color-surface)] shadow-sm">
        <div className="flex min-h-16 min-w-0 items-center justify-between gap-2 px-3 sm:gap-4 sm:px-6">
          <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-4">
            <NavLink to="/app" onClick={(event) => handleNavClick(event, '/app')} className="flex shrink-0 items-center gap-2" aria-label="Go to Dashboard">
              {/* <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--color-primary)] text-sm font-bold text-white">E</span> */}
              <span className="hidden font-[var(--font-display)] text-lg font-semibold text-[var(--color-ink)] sm:inline">AGSuite ERP</span>
            </NavLink>

            <nav ref={navRef} className="relative flex min-w-0 flex-1 items-center" aria-label="Main navigation">
              {!isCompactNav ? (
                <div className="flex min-w-0 items-center gap-1 overflow-visible">
                  {databaseNavItems.map((item) => renderDesktopMenuItem(item, 0))}
                </div>
              ) : (
                <>
                  <div className="flex min-w-0 flex-1 items-center gap-1 overflow-hidden">
                    {databaseNavItems.slice(0, visibleNavCount).map((item) => {
                      const hasChildren = Array.isArray(item?.children) && item.children.length > 0
                      const route = item.route ? `${item.route}${buildMenuSearch(item.query_params)}` : ''
                      const isOpen = compactMenu?.type === 'item' && compactMenu.key === item.key

                      return (
                        <div
                          key={item.key}
                          ref={(node) => {
                            if (node) compactTriggerRefs.current.set(item.key, node)
                            else compactTriggerRefs.current.delete(item.key)
                          }}
                          className="relative flex shrink-0 items-center"
                        >
                          {hasChildren ? (
                            <div className="flex items-center rounded-md">
                              {route ? (
                                <NavLink
                                  to={route}
                                  onClick={(event) => handleNavClick(event, route)}
                                  className={({ isActive }) => `flex items-center rounded-l-md px-3 py-2 text-sm font-medium whitespace-nowrap ${isActive ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]' : 'text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]'}`}
                                >
                                  {item.name}
                                </NavLink>
                              ) : (
                                <span className="px-3 py-2 text-sm font-medium whitespace-nowrap text-[var(--color-ink-soft)]">{item.name}</span>
                              )}
                              <button
                                type="button"
                                aria-label={`Open ${item.name} menu`}
                                aria-expanded={isOpen}
                                onClick={(event) => {
                                  event.preventDefault()
                                  event.stopPropagation()
                                  if (isOpen) {
                                    setCompactMenu(null)
                                    setCompactOpenPaths({})
                                    setCompactMenuPosition(null)
                                  } else {
                                    openCompactMenu('item', item.key, event.currentTarget.closest('[data-compact-trigger]') || event.currentTarget.parentElement)
                                  }
                                }}
                                data-compact-trigger
                                className="rounded-r-md px-1.5 py-2 text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)]"
                              >
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={`h-3.5 w-3.5 transition-transform ${isOpen ? 'rotate-180' : ''}`}>
                                  <path d="m6 9 6 6 6-6" />
                                </svg>
                              </button>
                            </div>
                          ) : route ? (
                            <NavLink to={route} onClick={(event) => handleNavClick(event, route)} className={({ isActive }) => `shrink-0 rounded-md px-3 py-2 text-sm font-medium whitespace-nowrap ${isActive ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]' : 'text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]'}`}>
                              {item.name}
                            </NavLink>
                          ) : null}
                        </div>
                      )
                    })}
                  </div>

                  {visibleNavCount < databaseNavItems.length && (
                    <button
                      ref={moreButtonRef}
                      type="button"
                      aria-label="More navigation items"
                      aria-expanded={moreMenuOpen}
                      onClick={(event) => {
                        event.preventDefault()
                        event.stopPropagation()
                        if (moreMenuOpen) {
                          setMoreMenuOpen(false)
                          setCompactMenu(null)
                          setCompactOpenPaths({})
                          setCompactMenuPosition(null)
                        } else {
                          openCompactMenu('more', null, event.currentTarget)
                        }
                      }}
                      className={`ml-1 flex h-9 w-10 shrink-0 items-center justify-center rounded-md ${moreMenuOpen ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-dark)]' : 'text-[var(--color-ink-soft)] hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]'}`}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
                        <path strokeLinecap="round" d="M4 7h16M4 12h16M4 17h16" />
                      </svg>
                    </button>
                  )}

                  <div ref={measureNavRef} aria-hidden="true" className="pointer-events-none absolute left-0 top-0 flex w-max items-center gap-1 opacity-0">
                    {databaseNavItems.map((item) => (
                      <div key={`measure-${item.key}`} className="flex shrink-0 items-center rounded-md">
                        <span className="px-3 py-2 text-sm font-medium whitespace-nowrap">{item.name}</span>
                        {Array.isArray(item?.children) && item.children.length > 0 && (
                          <span className="px-1.5 py-2 text-sm">⌄</span>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </nav>
          </div>

          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            <div className="hidden max-w-48 truncate text-right lg:block">
              {companyName && <span className="text-sm font-semibold capitalize text-[var(--color-ink)]">{companyName}</span>}
            </div>
            <div className="relative" ref={userMenuRef}>
              <button onClick={() => setUserMenuOpen((prev) => !prev)} className="flex items-center gap-2 rounded-full bg-[var(--color-primary-soft)] px-2 py-1 pr-1 text-sm font-semibold text-[var(--color-primary-dark)]" aria-label="User menu">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--color-primary)] text-xs font-bold text-white">{initials}</span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-3 w-3"><path d="M6 9l6 6 6-6" /></svg>
              </button>
              {userMenuOpen && (
                <div className="absolute right-0 mt-2 w-56 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] py-2 shadow-lg z-[180]">
                  <div className="px-4 py-3"><p className="text-sm font-semibold text-[var(--color-ink)]">{user ? `${user.first_name} ${user.last_name}`.trim() : 'User'}</p><p className="mt-0.5 text-xs text-[var(--color-muted)]">{user?.email || ''}</p></div>
                  <div className="border-t border-[var(--color-border)]" />
                  <NavLink to="/app/profile" onClick={() => setUserMenuOpen(false)} className="block w-full px-4 py-2 text-left text-sm text-[var(--color-ink)] hover:bg-[var(--color-canvas)]">Profile</NavLink>
                  <button onClick={handleLogout} className="block w-full px-4 py-2 text-left text-sm text-[var(--color-negative)] hover:bg-[var(--color-canvas)]">Logout</button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>
      <main className="min-w-0 flex-1 px-1 py-1 sm:px-2 sm:py-2 lg:px-1">{children}</main>
      {compactPortal}
    </div>
  )
}

function useCompactBreakpoint() {
  const [isCompact, setIsCompact] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < 768 : false,
  )

  useEffect(() => {
    if (typeof window === 'undefined') return undefined

    const query = window.matchMedia('(max-width: 767px)')
    const sync = () => setIsCompact(query.matches)
    sync()
    query.addEventListener?.('change', sync)
    return () => query.removeEventListener?.('change', sync)
  }, [])

  return isCompact
}
