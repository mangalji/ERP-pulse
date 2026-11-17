/**
 * In-memory, per-tab cache for list/summary data fetched by pages.
 *
 * Problem it solves: every SuperAdmin/Client page fetches on mount and
 * starts `loading` as true, so navigating back to a page already visited
 * in this session re-shows the empty skeleton before the same data pops
 * back in. That flash is the thing this cache removes.
 *
 * It is intentionally a plain module-level Map, not sessionStorage:
 *  - it must reset on a real page reload (so a refresh always shows fresh
 *    data), which a Map does automatically and sessionStorage would not.
 *  - it never needs to survive a browser restart.
 *
 * Usage pattern (see superadmin DashboardPage/CompaniesPage/PlansPage/
 * EmployeesPage for worked examples):
 *   1. Read `getCachedData(key)` once, synchronously, when the component
 *      is created, and use it as the initial state for rows/count/summary
 *      and for `loading` (false when a cache hit exists).
 *   2. On mount, call the normal load function, passing `silent: true`
 *      when step 1 found a cache hit, so the fetch happens quietly in the
 *      background instead of flipping `loading` back to true.
 *   3. On every successful fetch, call `setCachedData(key, value)` so the
 *      next visit benefits.
 *
 * Only cache the *default* view of a page (no search term, first page,
 * default sort). A filtered/sorted/paginated view is rarely revisited with
 * the exact same parameters, so it is cheaper and safer to always fetch it
 * fresh with a normal loading state.
 */
const store = new Map()

export function getCachedData(key) {
  return store.get(key)
}

export function setCachedData(key, value) {
  store.set(key, value)
}
