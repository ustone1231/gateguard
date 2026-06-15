import axios from 'axios'

const BASE = import.meta.env.VITE_API_BASE_URL

export async function login(username: string, password: string) {
  const { data } = await axios.post(`${BASE}/auth/login`, { username, password })
  localStorage.setItem('access_token', data.access_token)
  localStorage.setItem('refresh_token', data.refresh_token)
  return data
}

export async function logout() {
  const refreshToken = localStorage.getItem('refresh_token')
  if (refreshToken) {
    await axios.post(`${BASE}/auth/logout`, null, {
      headers: { Authorization: `Bearer ${refreshToken}` },
    }).catch(() => {})
  }
  localStorage.clear()
  window.location.href = '/login'
}

export function getAccessToken() {
  return localStorage.getItem('access_token')
}

export function isLoggedIn() {
  return !!localStorage.getItem('access_token')
}
