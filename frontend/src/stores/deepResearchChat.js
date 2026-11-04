// stores/chat.js
import { defineStore } from 'pinia'
import { createChatActions } from './commonChatActions';

export const useDeepSearchChatStore = defineStore('deepSearch', {
    state: () => (
        {
            sessions: [],
            currentSessionId: '', // 初始指向默认会话
        }
    ),

    getters: {
        // 获取当前会话对象（或 null）
        currentSession(state) {
            return state.sessions.find(s => s.id === state.currentSessionId) || null
        },
    },

    actions: {
        ...createChatActions(),
    },

})
