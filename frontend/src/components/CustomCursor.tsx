import { useEffect, useState } from 'react'

function CustomCursor() {
  const [pos, setPos] = useState({ x: -100, y: -100 })

  useEffect(() => {
    const handleMove = (e: MouseEvent) => setPos({ x: e.clientX, y: e.clientY })
    window.addEventListener('mousemove', handleMove)
    return () => window.removeEventListener('mousemove', handleMove)
  }, [])

  return (
    <div
      style={{
        position: 'fixed',
        top: pos.y,
        left: pos.x,
        width: '32px',
        height: '32px',
        backgroundColor: '#ffffff',
        borderRadius: '50%',
        mixBlendMode: 'difference',
        pointerEvents: 'none',
        zIndex: 999999,
        transform: 'translate(-50%, -50%)',
      }}
      className="hidden md:block"
    />
  )
}

export default CustomCursor
