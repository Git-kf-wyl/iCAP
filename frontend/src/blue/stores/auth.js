import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api'
import {clearReadCache} from '../../readCache.js'

export const useAuth = defineStore('auth', () => {
  const token = ref(localStorage.getItem('ic_token') || '')
  const username = ref(localStorage.getItem('ic_user') || '')
  const userId = ref(localStorage.getItem('ic_user_id') || '')
  const role = ref(localStorage.getItem('ic_role') || '')
  const securityQuestionsConfigured = ref(localStorage.getItem('ic_has_security_questions') === 'true')
  let verifiedToken = ''
  let verifiedAt = 0
  let profileRequest = null
  let logoutRequest = null
  let pageSessionRequest = null

  async function restorePageSession(element) {
    const session=token.value
    try {
      const saved=JSON.parse(element.textContent || '{}')
      if(!saved.profile || saved.expires_at*1000<=Date.now() || !globalThis.crypto?.subtle)return false
      const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(session))
      const fingerprint=[...new Uint8Array(bytes)].map(value=>value.toString(16).padStart(2,'0')).join('')
      if(fingerprint!==saved.fingerprint || token.value!==session)return false
      saveProfile(saved.profile)
      verifiedToken=session
      verifiedAt=Date.now()
      return true
    } catch { return false }
  }
  function saveProfile(result) {
    username.value = result.username || result.email || result.phone || ''
    userId.value = result.id == null ? '' : String(result.id)
    role.value = result.role || ''
    if (typeof result.has_security_questions === 'boolean') {
      securityQuestionsConfigured.value = result.has_security_questions
      localStorage.setItem('ic_has_security_questions', String(result.has_security_questions))
    }
    localStorage.setItem('ic_user', username.value)
    localStorage.setItem('username', username.value)
    if (userId.value) localStorage.setItem('ic_user_id', userId.value)
    else localStorage.removeItem('ic_user_id')
    if (role.value) localStorage.setItem('ic_role', role.value)
    else localStorage.removeItem('ic_role')
  }
  function saveSession(result) {
    token.value = result.access_token
    localStorage.setItem('ic_token', token.value)
    saveProfile(result)
    verifiedToken = token.value
    verifiedAt = Date.now()
  }
  async function login(credentials) {
    saveSession(await api.post('/auth/login', credentials, { publicAuth: true, silentError: true }))
  }
  async function register(details) {
    saveSession(await api.post('/auth/register', details, { publicAuth: true, silentError: true }))
  }
  function getSecurityQuestions(username) {
    return api.get('/auth/security-questions', { params: { username }, publicAuth: true, silentError: true })
  }
  function resetPassword(details) {
    return api.post('/auth/password/reset', details, { publicAuth: true, silentError: true })
  }
  function changePassword(details) {
    return api.post('/auth/password/change', details, { silentError: true })
  }
  async function setupSecurityQuestions(details) {
    const result = await api.put('/auth/security-questions', details, { silentError: true })
    securityQuestionsConfigured.value = true
    localStorage.setItem('ic_has_security_questions', 'true')
    return result
  }
  async function refreshProfile() {
    if (!token.value) return false
    const session = token.value
    if (profileRequest?.token === session) return profileRequest.promise
    const request = { token: session }
    request.promise = (async () => {
      try {
        const profile = await api.get('/auth/me', { silentError: true, skipAuthRedirect: true })
        // A previous login's response must never overwrite the current session.
        if (token.value !== session) return false
        saveProfile(profile)
        verifiedToken = session
        verifiedAt = Date.now()
        return true
      } catch (error) {
        if (token.value !== session) return false
        if (error.response?.status === 401) {
          clearSession()
          return false
        }
        throw error
      } finally {
        if (profileRequest === request) profileRequest = null
      }
    })()
    profileRequest = request
    return request.promise
  }
  function validateNavigation(onInvalid) {
    if (!token.value) return Promise.resolve(false)
    if (verifiedToken === token.value) {
      // API requests and feature files still enforce server-side authorization.
      // Revalidate in the background instead of gating every menu click on WAN RTT.
      if (Date.now() - verifiedAt > 60000 && !profileRequest) refreshProfile().then(valid => {
        if (!valid && !token.value) onInvalid?.()
      }).catch(() => {})
      return Promise.resolve(true)
    }
    const bootstrap=typeof document==='undefined'?null:document.getElementById('icap-session')
    if(bootstrap){
      if(!pageSessionRequest)pageSessionRequest=restorePageSession(bootstrap)
      return pageSessionRequest.then(restored=>restored || refreshProfile())
    }
    return refreshProfile()
  }
  function clearSession() {
    clearReadCache()
    verifiedToken = ''
    verifiedAt = 0
    token.value = ''
    username.value = ''
    userId.value = ''
    role.value = ''
    securityQuestionsConfigured.value = false
    localStorage.removeItem('ic_token')
    localStorage.removeItem('ic_user')
    localStorage.removeItem('username')
    localStorage.removeItem('ic_user_id')
    localStorage.removeItem('ic_role')
    localStorage.removeItem('ic_has_security_questions')
  }
  async function logout() {
    if (logoutRequest) return logoutRequest
    logoutRequest = (async () => {
      let revoked = true
      try {
        if (token.value) await api.post('/auth/logout', null, { silentError: true, skipAuthRedirect: true })
      } catch { revoked = false }
      finally { clearSession() }
      return revoked
    })()
    try { return await logoutRequest } finally { logoutRequest = null }
  }
  return { token, username, userId, role, securityQuestionsConfigured, login, register, getSecurityQuestions, resetPassword, changePassword, setupSecurityQuestions, refreshProfile, validateNavigation, logout }
})
