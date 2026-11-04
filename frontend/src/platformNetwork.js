import axios from 'axios'
import {installReadCache,clearReadCache,retryReads} from './readCache.js'
installReadCache(axios)
// Keep credentials on the authenticated same-origin adapter only.
function secureHeaders(url, headers, publicAuth = false) {
  const target = new URL(typeof url === 'string' ? url : url instanceof URL ? url.href : url.url, location.origin)
  if (target.origin !== location.origin) throw new Error('该服务尚未接入本机 adapter，请联系管理员配置')
  const value = new Headers(headers || {})
  const token = localStorage.getItem('ic_token')
  if (token && !publicAuth) value.set('Authorization', `Bearer ${token}`)
  return value
}
axios.interceptors.request.use(config => {
  const url = new URL(config.url, config.baseURL ? new URL(config.baseURL, location.origin) : location.origin)
  config.headers = Object.fromEntries(secureHeaders(url.href, config.headers, config.publicAuth).entries())
  return config
})
axios.interceptors.response.use(response => response, error => {
  if (error.response?.status === 401 && (error.config?.headers?.get?.('Authorization') || error.config?.headers?.Authorization || error.config?.headers?.authorization)===`Bearer ${localStorage.getItem('ic_token')}` && !['/login','/register','/password/reset'].includes(location.pathname)) {
    clearReadCache()
    for (const key of ['ic_token','ic_user','ic_user_id','ic_role','username']) localStorage.removeItem(key)
    location.assign(`/login?redirect=${encodeURIComponent(location.pathname+location.search)}`)
  }
  return Promise.reject(error)
})
window.addEventListener('icap:session-expired',()=>{
  for(const key of ['ic_token','ic_user','ic_user_id','ic_role','username'])localStorage.removeItem(key)
  location.assign('/login')
})
window.addEventListener('storage',event=>{if(event.key==='ic_token'){clearReadCache();location.reload()}})
window.addEventListener('online',retryReads)
let lastFocus=Date.now()
window.addEventListener('focus',()=>{if(Date.now()-lastFocus>30000){lastFocus=Date.now();retryReads()}})
const nativeFetch = window.fetch.bind(window)
window.fetch = (input, init = {}) => {
  try { return nativeFetch(input, {...init,headers:secureHeaders(input,init.headers || (input instanceof Request ? input.headers : undefined))}) }
  catch (error) { return Promise.reject(error) }
}
