export const NETSUITE_REAUTH_CODE = 'NETSUITE_REAUTH_REQUIRED'

/** True when an API error means "NetSuite authorization must be renewed". */
export function isNetSuiteReauthError(err) {
  const code = err?.response?.data?.code ?? err?.payload?.code
  return code === NETSUITE_REAUTH_CODE
}

/** True when a finished batch job reports at least one reauth failure. */
export function isNetSuiteReauthJob(job) {
  return (
    Array.isArray(job?.results) &&
    job.results.some((item) => item?.code === NETSUITE_REAUTH_CODE)
  )
}

/** Only Company Admins (and platform staff) can reconnect NetSuite. */
export function isCompanyAdminUser(user) {
  if (user?.is_superadmin || user?.is_staff) return true

  return (Array.isArray(user?.roles) ? user.roles : []).some((role) => {
    const value =
      typeof role === 'string'
        ? role
        : role?.name ?? role?.code ?? role?.key ?? ''

    return ['company_admin', 'company admin'].includes(
      String(value).trim().toLowerCase(),
    )
  })
}