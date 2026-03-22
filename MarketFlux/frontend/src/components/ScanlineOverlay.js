import { useLocation } from 'react-router-dom';

export default function ScanlineOverlay() {
  const location = useLocation();
  if (location.pathname === '/fund-os') {
    return null;
  }
  return <div className="scanline-overlay" aria-hidden="true" />;
}
