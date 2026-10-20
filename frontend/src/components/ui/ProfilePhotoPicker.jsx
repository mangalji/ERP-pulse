import { useEffect, useState } from 'react'
import ProfileAvatar from './ProfileAvatar.jsx'

const MAX_PROFILE_PICTURE_BYTES = 5 * 1024 * 1024

export default function ProfilePhotoPicker({ id = 'profile-picture', profilePicture, initials, onChange }) {
  const [previewUrl, setPreviewUrl] = useState('')
  const [error, setError] = useState('')

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  const handleChange = (event) => {
    const file = event.target.files?.[0]
    setError('')

    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('Choose an image file.')
      event.target.value = ''
      return
    }
    if (file.size > MAX_PROFILE_PICTURE_BYTES) {
      setError('Profile picture must be 5 MB or smaller.')
      event.target.value = ''
      return
    }

    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current)
      return URL.createObjectURL(file)
    })
    onChange(file)
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium text-[var(--color-ink-soft)]">Profile picture</span>
      <div className="flex flex-wrap items-center gap-4">
        <ProfileAvatar
          profilePicture={previewUrl || profilePicture}
          initials={initials}
          className="h-16 w-16"
          imageClassName="border border-[var(--color-border)]"
        />
        <div className="flex min-w-0 flex-col gap-1.5">
          <input
            id={id}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            onChange={handleChange}
            className="block w-full max-w-sm cursor-pointer rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-ink)] file:mr-3 file:rounded-md file:border-0 file:bg-[var(--color-primary-soft)] file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-[var(--color-primary-dark)] hover:file:bg-[var(--color-primary-soft)]"
          />
          <p className="text-xs text-[var(--color-muted)]">PNG, JPG, WEBP, or GIF up to 5 MB.</p>
        </div>
      </div>
      {error && <p className="text-xs text-[var(--color-negative)]">{error}</p>}
    </div>
  )
}
