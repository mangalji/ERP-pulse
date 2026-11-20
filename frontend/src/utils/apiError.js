export function getApiErrorMessage(error, fallback = 'Something went wrong.') {
  return (
    error?.payload?.message ||
    error?.payload?.detail ||
    error?.response?.data?.message ||
    error?.response?.data?.detail ||
    error?.message ||
    fallback
  )
}
