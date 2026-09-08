import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext.jsx'
import ClientLayout from '../../components/layout/ClientLayout.jsx'
import { clientApi } from '../../services/client.js'

const ACTIONS = [
  { key: 'show', label: 'Show' },
  { key: 'remove', label: 'Remove' },
  { key: 'add', label: 'Add' },
  { key: 'edit', label: 'Edit / Delete' },
]

const emptyForm = {
  name: '',
  route: '',
  query_params: '',
  feature_code: '',
  icon: '',
}

function optionLabel(item) {
  return item?.name || ''
}

export default function CustomizeNavigationPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [targetType, setTargetType] = useState('employee')
  const [action, setAction] = useState('show')
  const [employees, setEmployees] = useState([])
  const [admins, setAdmins] = useState([])
  const [targetUserId, setTargetUserId] = useState('')
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState([])
  const [selectAllEmployees, setSelectAllEmployees] = useState(false)
  const [tree, setTree] = useState([])
  const [selectedTopId, setSelectedTopId] = useState('')
  const [selectedLevel2Id, setSelectedLevel2Id] = useState('')
  const [selectedLevel3Id, setSelectedLevel3Id] = useState('')
  const [form, setForm] = useState(emptyForm)
  const [addingParent, setAddingParent] = useState('root')
  const [addFormOpen, setAddFormOpen] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const selectedTop = useMemo(
    () => tree.find((item) => String(item.id) === String(selectedTopId)) || null,
    [tree, selectedTopId],
  )

  const level2Options = selectedTop?.children || []
  const selectedLevel2 = useMemo(
    () => level2Options.find((item) => String(item.id) === String(selectedLevel2Id)) || null,
    [level2Options, selectedLevel2Id],
  )

  const level3Options = selectedLevel2?.children || []

  const loadData = async (nextTargetUserId = targetUserId) => {
    setLoading(true)
    setError('')
    try {
      const result = await clientApi.getNavigationCustomizeData(
        nextTargetUserId
          ? { target_user_id: nextTargetUserId}
          : {}  
      )
      setEmployees(result?.employees || [])
      setAdmins(result?.admins || [])
      setTree(result?.tree || [])
      if (nextTargetUserId && !result?.target_user) {
        setTargetUserId('')
      }
    } catch (err) {
      setError(err?.payload?.message || err?.message || 'Failed to load navigation customization.')
      setTree([])
    } finally {
      setLoading(false)
    }
  }

  // useEffect(() => {
  //   if (targetType === 'admin') {
  //     const currentId = user?.id || ''
  //     setTargetUserId(currentId)
  //     setSelectedEmployeeIds([])
  //     setSelectAllEmployees(false)
  //     loadData(currentId)
  //   } else {
  //     setTargetUserId('')
  //     setSelectedEmployeeIds([])
  //     setSelectAllEmployees(false)
  //     setSelectedTopId('')
  //     setSelectedLevel2Id('')
  //     setSelectedLevel3Id('')
  //     loadData('')
  //   }
  // }, [targetType, user?.id])

//   useEffect(() => {
//   setSelectedEmployeeIds([])
//   setSelectAllEmployees(false)
//   setSelectedTopId('')
//   setSelectedLevel2Id('')
//   setSelectedLevel3Id('')

//   if (targetType === 'admin') {
//     setTargetUserId('')
//     loadData('')
//   } else {
//     setTargetUserId('')
//     loadData('')
//   }
// }, [targetType, user?.id])

useEffect(() => {
  setSelectedEmployeeIds([])
  setSelectAllEmployees(false)
  setSelectedTopId('')
  setSelectedLevel2Id('')
  setSelectedLevel3Id('')
  setError('')
  setMessage('')

  setTargetUserId('')
  loadData('')
}, [targetType, user?.id])

  const selectTop = (value) => {
    setSelectedTopId(value)
    setSelectedLevel2Id('')
    setSelectedLevel3Id('')
    setAddingParent('root')
    setMessage('')
  }

  const selectLevel2 = (value) => {
    setSelectedLevel2Id(value)
    setSelectedLevel3Id('')
    setAddingParent('top')
    setMessage('')
  }

  const selectLevel3 = (value) => {
    setSelectedLevel3Id(value)
    setAddingParent('level2')
    setMessage('')
  }

  const resetAddForm = (parentLevel = 'root') => {
    setAddingParent(parentLevel)
    setAddFormOpen(true)
    setForm(emptyForm)
    setError('')
  }

  const performAccessAction = async (tabLevel, tabId, nextAction) => {
  const targetIds =
    targetType === 'employee'
      ? selectedEmployeeIds
      : admins.map((admin) => String(admin.id))

    if (targetIds.length === 0) {
      setError(
        targetType === 'employee'
          ? 'Select at least one employee.'
          : 'No Company Admins found.'
      )
      return
    }

  setSaving(true)
  setError('')
  setMessage('')

  try {
    const result = await clientApi.updateNavigationAccess({
      target_user_ids: targetIds,
      tab_level: tabLevel,
      tab_id: tabId,
      action: nextAction,
    })

    await loadData(
      targetType === 'admin' ? targetUserId : null
    )

    setMessage(
      result?.message ||
      `Navigation item ${
        nextAction === 'show' ? 'shown' : 'removed'
      } successfully.`
    )
  } catch (err) {
    setError(
      err?.payload?.message ||
      err?.message ||
      'Unable to update navigation access.'
    )
  } finally {
    setSaving(false)
  }
}

  const addTab = async (parentLevel, parentId) => {
    if (!form.name.trim()) {
      setError('Tab name is required.')
      return
    }
    if (!form.route.trim()) {
      setError('Tab route is required.')
      return
    }
    setSaving(true)
    setError('')
    setMessage('')

    let parsedQueryParams = {}
    try {
      parsedQueryParams = form.query_params.trim() ? JSON.parse(form.query_params) : {}
      if (
        parsedQueryParams === null ||
        Array.isArray(parsedQueryParams) ||
        typeof parsedQueryParams !== 'object'
      ) {
        throw new Error('Query params must be a JSON object.')
      }
      await clientApi.createNavigationTab({
        parent_level: parentLevel,
        parent_id: parentId || null,
        name: form.name.trim(),
        route: form.route.trim(),
        query_params: parsedQueryParams,
        feature_code: form.feature_code.trim(),
        icon: form.icon.trim(),
      })
      await loadData(targetUserId)
      setForm(emptyForm)
      setAddFormOpen(false)
      setMessage('Navigation tab created successfully.')
    } catch (err) {
      setError(err?.payload?.message || err?.message || 'Unable to create navigation tab.')
    } finally {
      setSaving(false)
    }
  }

  const updateTab = async () => {
  if (!editingItem) return

  if (!form.name.trim()) {
    setError('Tab name is required.')
    return
  }

  if (!form.route.trim()) {
    setError('Tab route is required.')
    return
  }

  setSaving(true)
  setError('')
  setMessage('')

  try {
    let parsedQueryParams = {}

    if (form.query_params.trim()) {
      parsedQueryParams = JSON.parse(form.query_params)

      if (
        parsedQueryParams === null ||
        Array.isArray(parsedQueryParams) ||
        typeof parsedQueryParams !== 'object'
      ) {
        throw new Error('Query params must be a JSON object.')
      }
    }

    await clientApi.updateNavigationTab(
      editingItem.level,
      editingItem.id,
      {
        name: form.name.trim(),
        route: form.route.trim(),
        query_params: parsedQueryParams,
        feature_code: form.feature_code.trim(),
        icon: form.icon.trim(),
      }
    )

    await loadData(targetUserId)

    setEditingItem(null)
    setForm(emptyForm)
    setMessage('Navigation tab updated successfully.')
  } catch (err) {
    setError(
      err?.payload?.message ||
      err?.message ||
      'Unable to update navigation tab.'
    )
  } finally {
    setSaving(false)
  }
}

  const deleteTab = async (item) => {
  if (!item || item.system) return

  const confirmed = window.confirm(
    `Delete "${item.name}"? This will also deactivate its child tabs.`
  )

  if (!confirmed) return

  setSaving(true)
  setError('')
  setMessage('')

  try {
    await clientApi.deleteNavigationTab(item.level, item.id)

    await loadData(targetUserId)

    setSelectedTopId('')
    setSelectedLevel2Id('')
    setSelectedLevel3Id('')
    setEditingItem(null)
    setForm(emptyForm)

    setMessage(`"${item.name}" deleted successfully.`)
  } catch (err) {
    setError(
      err?.payload?.message ||
      err?.message ||
      'Unable to delete navigation tab.'
    )
  } finally {
    setSaving(false)
  }
}

const renderActionButton = (item) => {
  const hasAccessTarget =
    targetType === 'admin'
      ? admins.length > 0
      : selectedEmployeeIds.length > 0

  if (!hasAccessTarget) {
    return (
      <span className="shrink-0 text-xs text-[var(--color-muted)]">
        {targetType === 'admin'
          ? 'No Company Admins found'
          : 'Select employee'}
      </span>
    )
  }

  if (item?.system) {
    return (
      <span className="shrink-0 text-xs font-medium text-[var(--color-muted)]">
        System tab
      </span>
    )
  }

  const tabLevel = item.level

  if (action === 'show') {
    return (
      <button
        type="button"
        disabled={saving}
        onClick={() => performAccessAction(tabLevel, item.id, 'show')}
        className="shrink-0 rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold text-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-40"
      >
        Show
      </button>
    )
  }

  if (action === 'remove') {
    return (
      <button
        type="button"
        disabled={saving}
        onClick={() => performAccessAction(tabLevel, item.id, 'remove')}
        className="shrink-0 rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold text-[var(--color-negative)] disabled:cursor-not-allowed disabled:opacity-40"
      >
        Remove
      </button>
    )
  }

  if (action === 'add') {
    return null
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        disabled={saving}
        onClick={() => {
          setEditingItem(item)
          setAddFormOpen(false)
          setForm({
            name: item.name || '',
            route: item.route || '',
            query_params: item.query_params
              ? JSON.stringify(item.query_params, null, 2)
              : '',
            feature_code: item.feature_code || '',
            icon: item.icon || '',
          })
          setError('')
          setMessage('')
        }}
        className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold text-[var(--color-primary)] disabled:opacity-40"
      >
        Edit
      </button>

      <button
        type="button"
        disabled={saving}
        onClick={() => deleteTab(item)}
        className="rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold text-[var(--color-negative)] disabled:opacity-40"
      >
        Delete
      </button>
    </div>
  )
}

  const dropdownRow = (label, value, options, onChange, addParentLevel, selectedItem) => (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-2">
      <label className="block min-w-0">
        <span className="mb-1.5 block text-xs font-semibold text-[var(--color-ink-soft)]">{label}</span>
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-primary)]"
        >
          <option value="">Select {label.toLowerCase()}</option>
          {options.map((item) => (
            <option key={item.id} value={item.id}>{optionLabel(item)}</option>
          ))}
        </select>
      </label>
      <div className="flex items-center gap-2">
        {/* {action === 'add' && (
          <button type="button" onClick={() => resetAddForm(addParentLevel)} className="rounded-lg border border-[var(--color-primary)] px-3 py-2.5 text-xs font-semibold text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]">+ Add Tab</button>
        )} */}
        {action === 'add' && !selectedItem?.system && (
          <button
            type="button"
            onClick={() => {
              setEditingItem(null) 
              resetAddForm(addParentLevel)
            }}
            className="rounded-lg border border-[var(--color-primary)] px-3 py-2.5 text-xs font-semibold text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
          >
            + Add Tab
          </button>
        )}

        {action === 'edit' && selectedItem?.system && (
    <span className="shrink-0 text-xs font-medium text-[var(--color-muted)]">
      System tab
    </span>
  )}
    {action === 'edit' && selectedItem && renderActionButton(selectedItem)}
        {action !== 'add' && action !== 'edit' && selectedItem && renderActionButton(selectedItem)}

      </div>
    </div>
  )

  const renderAddForm = () => {
    const parentId = addingParent === 'root' ? null : addingParent === 'top' ? selectedTopId : selectedLevel2Id
    return (
      <div className="mt-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-[var(--color-ink)]">Add Tab</p>
            <p className="mt-0.5 text-xs text-[var(--color-muted)]">
              {addingParent === 'root'
                ? 'Create a new top-level tab.'
                : addingParent === 'top'
                  ? 'Create a new level-2 tab under the selected top-level tab.'
                  : 'Create a new level-3 tab under the selected level-2 tab.'}
            </p>
          </div>
          <button type="button" onClick={() => setAddFormOpen(false)} className="text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-ink)]">Cancel</button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Tab name" className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm" />
          <input value={form.route} onChange={(e) => setForm({ ...form, route: e.target.value })} placeholder="/app/your-path"  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm" />
          <textarea
  value={form.query_params}
  onChange={(e) => setForm({ ...form, query_params: e.target.value })}
  placeholder='Query params JSON (optional), e.g. {"view":"sales_orders"}'
  rows={3}
  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm"
/>
          <input value={form.feature_code} onChange={(e) => setForm({ ...form, feature_code: e.target.value })} placeholder="Feature code (optional)" className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm" />
          <input value={form.icon} onChange={(e) => setForm({ ...form, icon: e.target.value })} placeholder="Icon key (optional)" className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm" />
        </div>
        <div className="mt-3 flex justify-end">
          <button type="button" disabled={saving} onClick={() => addTab(addingParent, parentId)} className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Create Tab</button>
        </div>
      </div>
    )
  }

  return (
    <ClientLayout title="Customize" breadcrumb="Customize">
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-3 sm:p-6">
      <div className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4 sm:px-6">
          <div>
            <h1 className="text-lg font-semibold text-[var(--color-ink)]">Customize Navigation</h1>
            <p className="mt-0.5 text-xs text-[var(--color-muted)]">Manage the NetSuite-style navigation hierarchy without deleting master tabs.</p>
          </div>
          <button type="button" onClick={() => navigate('/app/settings')} className="rounded-lg p-2 text-[var(--color-muted)] hover:bg-[var(--color-canvas)]" aria-label="Close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>

        <div className="overflow-y-auto px-5 py-5 sm:px-6">
          <div className="grid grid-cols-2 gap-2 rounded-xl bg-[var(--color-canvas)] p-1">
            <button type="button" onClick={() => setTargetType('employee')} className={`rounded-lg px-4 py-2.5 text-sm font-semibold ${targetType === 'employee' ? 'bg-[var(--color-surface)] text-[var(--color-primary)] shadow-sm' : 'text-[var(--color-muted)]'}`}>Employee</button>
            <button type="button" onClick={() => setTargetType('admin')} className={`rounded-lg px-4 py-2.5 text-sm font-semibold ${targetType === 'admin' ? 'bg-[var(--color-surface)] text-[var(--color-primary)] shadow-sm' : 'text-[var(--color-muted)]'}`}>Admin</button>
          </div>

          <div className="mt-4">
            {targetType === 'employee' ? (
            <div>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-semibold text-[var(--color-ink-soft)]">
                  Select Employee
                </span>

                <label className="flex items-center gap-2 text-xs font-medium text-[var(--color-ink-soft)]">
                  <input
                    type="checkbox"
                    checked={
                      employees.length > 0 &&
                      selectAllEmployees
                    }
                    onChange={(e) => {
                      const checked = e.target.checked
                    
                      setSelectAllEmployees(checked)
                    
                      if (checked) {
                        setSelectedEmployeeIds(
                          employees.map((employee) => String(employee.id))
                        )
                      } else {
                        setSelectedEmployeeIds([])
                      }
                    
                      setSelectedTopId('')
                      setSelectedLevel2Id('')
                      setSelectedLevel3Id('')
                    }}
                    className="h-4 w-4 rounded border-[var(--color-border)]"
                  />

                  Select All Employees
                </label>
              </div>
                  
              <div className="max-h-56 space-y-2 overflow-y-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                {employees.length === 0 ? (
                  <p className="text-sm text-[var(--color-muted)]">
                    No employees found.
                  </p>
                ) : (
                  employees.map((employee) => {
                    const employeeId = String(employee.id)
                    const checked = selectedEmployeeIds.includes(employeeId)
                  
                    return (
                      <label
                        key={employee.id}
                        className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 hover:bg-[var(--color-canvas)]"
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            const isChecked = e.target.checked
                          
                            setSelectedEmployeeIds((current) => {
                              const next = isChecked
                                ? [...new Set([...current, employeeId])]
                                : current.filter((id) => id !== employeeId)
                            
                              setSelectAllEmployees(
                                employees.length > 0 &&
                                next.length === employees.length
                              )
                            
                              return next
                            })
                          
                            setSelectedTopId('')
                            setSelectedLevel2Id('')
                            setSelectedLevel3Id('')
                          }}
                          className="h-4 w-4 rounded border-[var(--color-border)]"
                        />

                        <span className="min-w-0 text-sm text-[var(--color-ink)]">
                          {employee.name}
                          <span className="ml-1 text-xs text-[var(--color-muted)]">
                            — {employee.email}
                          </span>
                        </span>
                      </label>
                    )
                  })
                )}
              </div>
              
              {selectedEmployeeIds.length > 0 && (
                <p className="mt-2 text-xs text-[var(--color-muted)]">
                  {selectedEmployeeIds.length} employee
                  {selectedEmployeeIds.length === 1 ? '' : 's'} selected
                </p>
              )}
            </div>
            ) : (
            <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-canvas)] px-3 py-2.5 text-sm text-[var(--color-ink)]">
              All Company Admins
              <span className="ml-1 text-xs text-[var(--color-muted)]">
                ({admins.length})
              </span>
            </div>
          )}
          </div>

          <div className="mt-5">
            <span className="mb-2 block text-xs font-semibold text-[var(--color-ink-soft)]">Action</span>
            <div className="flex gap-2">
              {ACTIONS.map((item) => <button key={item.key} type="button" onClick={() => { setAction(item.key); setMessage(''); setError('') }} className={`rounded-lg border px-4 py-2 text-sm font-semibold ${action === item.key ? 'border-[var(--color-primary)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]' : 'border-[var(--color-border)] text-[var(--color-ink-soft)]'}`}>{item.label}</button>)}
            </div>
          </div>

          {!loading && (
            <div className="mt-5 space-y-4">
              {dropdownRow('Tabs', selectedTopId, tree, selectTop, 'root', selectedTop)}
              {selectedTop && dropdownRow('Subtabs', selectedLevel2Id, level2Options, selectLevel2, 'top', selectedLevel2)}
              {selectedLevel2 && dropdownRow('Subtabs 2', selectedLevel3Id, level3Options, selectLevel3, 'level2', level3Options.find(
                (item) => String(item.id) === String(selectedLevel3Id)
              ) )}

              {action === 'add' && addFormOpen && renderAddForm()}
              {action === 'edit' && editingItem && (
  <div className="mt-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-canvas)] p-4">
    <div className="mb-3 flex items-center justify-between gap-3">
      <div>
        <p className="text-sm font-semibold text-[var(--color-ink)]">
          Edit Tab
        </p>
        <p className="mt-0.5 text-xs text-[var(--color-muted)]">
          {editingItem.name}
        </p>
      </div>

      <button
        type="button"
        onClick={() => {
          setEditingItem(null)
          setForm(emptyForm)
        }}
        className="text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-ink)]"
      >
        Cancel
      </button>
    </div>

    <div className="grid gap-3 sm:grid-cols-2">
      <input
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
        placeholder="Tab name"
        className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm"
      />

      <input
        value={form.route}
        onChange={(e) => setForm({ ...form, route: e.target.value })}
        placeholder="/app/your-path"
        className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm"
      />

      <textarea
        value={form.query_params}
        onChange={(e) => setForm({ ...form, query_params: e.target.value })}
        placeholder='Query params JSON (optional)'
        rows={3}
        className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm"
      />

      <input
        value={form.feature_code}
        onChange={(e) => setForm({ ...form, feature_code: e.target.value })}
        placeholder="Feature code (optional)"
        className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm"
      />

      <input
        value={form.icon}
        onChange={(e) => setForm({ ...form, icon: e.target.value })}
        placeholder="Icon key (optional)"
        className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm"
      />
    </div>

    <div className="mt-3 flex justify-end">
      <button
        type="button"
        disabled={saving}
        onClick={updateTab}
        className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        Save Changes
      </button>
    </div>
  </div>
)}
            </div>
          )}
          {targetType === 'admin' && admins.length === 0 && (
            <p className="mt-5 rounded-lg border border-dashed border-[var(--color-border)] px-4 py-5 text-center text-sm text-[var(--color-muted)]">
              No Company Admins found.
            </p>
          )}

          {loading && <p className="mt-5 py-6 text-center text-sm text-[var(--color-muted)]">Loading navigation…</p>}
          {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
          {message && <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[var(--color-border)] px-5 py-3 sm:px-6">
          <button type="button" onClick={() => navigate('/app/settings')} className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-sm font-semibold text-[var(--color-ink-soft)]">Done</button>
        </div>
      </div>
    </div>
    </ClientLayout>
  )
}
