import { useEffect, useState } from 'react'
import { getProfilePictureUrl } from '../../utils/profilePicture.js'

export default function ProfileAvatar({
  profilePicture,
  initials = 'U',
  className = 'h-9 w-9',
  imageClassName = '',
}) {
  const imageUrl = getProfilePictureUrl(profilePicture)
  const [imageFailed, setImageFailed] = useState(false)

  useEffect(() => {
    setImageFailed(false)
  }, [imageUrl])

  if (imageUrl && !imageFailed) {
    return (
      <img
        src={imageUrl}
        alt="Profile"
        onError={() => setImageFailed(true)}
        className={`shrink-0 rounded-full object-cover ${className} ${imageClassName}`}
      />
    )
  }

  return (
    <span className={`flex shrink-0 items-center justify-center rounded-full bg-[var(--color-primary)] text-xs font-bold text-white ${className} ${imageClassName}`}>
      {initials}
    </span>
  )
}
