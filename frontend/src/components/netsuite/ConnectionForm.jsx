import { useState } from 'react'
import Input from '../ui/Input.jsx'
import Button from '../ui/Button.jsx'

export default function ConnectionForm({ onSubmit, isLoading, initialData = {} }) {
  const [form, setForm] = useState({
    client_name: initialData.client_name || '',
    client_id: initialData.client_id || '',
    client_secret: initialData.client_secret || '',
    netsuite_account_id: initialData.netsuite_account_id || '',
    // Keep this optional post-connect redirect disabled in the UI. The backend
    // uses its default Integration page redirect when it is omitted.
    // callback_uri: initialData.callback_uri || '',
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
      <Input label="NetSuite Account ID" value={form.netsuite_account_id} onChange={handleChange('netsuite_account_id')} required />
      <Input label="Client ID" type="password" value={form.client_id} onChange={handleChange('client_id')} required />
      <Input label="Client Secret" type="password" value={form.client_secret} onChange={handleChange('client_secret')} required />
      {/*
        This is an optional AGSuite post-connect redirect, not NetSuite's OAuth
        redirect URI. Keep it hidden so users rely on the backend default.
        <Input label="Callback URI" value={form.callback_uri} onChange={handleChange('callback_uri')} placeholder="Enter callback URI" maxlength={500} />
      */}
      <Button type="submit" isLoading={isLoading} className="w-full">
        {initialData.client_name ? 'Update Connection' : 'Create Connection'}
      </Button>
    </form>
  )
}
