import { computed } from 'vue'
import { useAuth } from './blue/stores/auth'

export function useEvaluationAccess() {
  const auth=useAuth()
  return {canEvaluate:computed(()=>auth.role==='admin')}
}
