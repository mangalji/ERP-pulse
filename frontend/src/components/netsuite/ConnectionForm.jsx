import { useState } from 'react'
import Input from '../ui/Input.jsx'
import Button from '../ui/Button.jsx'

export default function ConnectionForm({ onSubmit, isLoading, initialData = {} }) {
  const [form, setForm] = useState({
    client_name: initialData.client_name || '',
    environment: initialData.environment || 'sandbox',
    client_id: initialData.client_id || '',
    client_secret: initialData.client_secret || '',
    netsuite_account_id: initialData.netsuite_account_id || '',
  })

  const handleChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit(form)
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <Input label="Connection Name" value={form.client_name} onChange={handleChange('client_name')} required />
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-[var(--color-ink-soft)]">Environment</span>
        <select
          value={form.environment}
          onChange={handleChange('environment')}
          className="rounded-lg border border-[var(--color-border)] px-3.5 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-soft)]"
        >
          <option value="sandbox">Sandbox</option>
          <option value="production">Production</option>
        </select>
      </label>
      <Input label="NetSuite Account ID" value={form.netsuite_account_id} onChange={handleChange('netsuite_account_id')} required />
      <Input label="Client ID" value={form.client_id} onChange={handleChange('client_id')} required />
      <Input label="Client Secret" type="password" value={form.client_secret} onChange={handleChange('client_secret')} required />
      <Button type="submit" isLoading={isLoading} className="w-full">
        {initialData.client_name ? 'Update Connection' : 'Create Connection'}
      </Button>
    </form>
  )
}
