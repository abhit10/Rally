/// <reference types="vite/client" />
const origin = (import.meta.env.VITE_BACKEND_ORIGIN || '').replace(/\/$/, '');
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.has('demo_key')) {
  sessionStorage.setItem('rally_demo_key', fragment.get('demo_key') || '');
  history.replaceState(null, '', location.pathname + location.search);
}
const key = origin ? (sessionStorage.getItem('rally_demo_key') || '') : '';
export function backendUrl(path:string, websocket=false) {
  const url = new URL(path, origin || location.origin);
  if (key) url.searchParams.set('demo_key', key);
  if (websocket) url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.toString();
}
export function mediaUrl(path?:string) { return path ? backendUrl(path) : undefined; }
