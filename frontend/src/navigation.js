import { ref } from 'vue'

export const navigationPending = ref(false)
let destination = ''
export function beginNavigation(path) {
  destination = path
  navigationPending.value = true
}
export function endNavigation(path) {
  if (!path || destination === path) navigationPending.value = false
}
