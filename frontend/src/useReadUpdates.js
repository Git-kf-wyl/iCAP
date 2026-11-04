import {onMounted,onActivated,onDeactivated,onBeforeUnmount} from 'vue'
import {onReadUpdate} from './readCache.js'

// Only mounted/visible readers repaint on background updates; forms are untouched.
export function useReadUpdates(paths,refresh) {
  let active=true,unsubscribe,timer,seenActivation=false,running=false,again=false
  const run=async()=>{
    if(!active)return
    if(running){again=true;return}
    running=true
    try{await refresh()}catch{}finally{running=false;if(again){again=false;schedule()}}
  }
  const schedule=()=>{clearTimeout(timer);timer=setTimeout(run,0)}
  onMounted(()=>{unsubscribe=onReadUpdate(path=>{if(active&&(path==='*'||paths.includes(path)))schedule()})})
  onActivated(()=>{active=true;if(seenActivation)schedule();seenActivation=true})
  onDeactivated(()=>{active=false;clearTimeout(timer)})
  onBeforeUnmount(()=>{active=false;clearTimeout(timer);unsubscribe?.()})
}
