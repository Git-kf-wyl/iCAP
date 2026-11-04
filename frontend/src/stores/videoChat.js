// stores/chat.js
import { defineStore } from 'pinia'
import { createChatActions } from './commonChatActions';

export const useVideoChatStore = defineStore('videoChat', {
    state: () => (
        {
            sessions: [
                // 示例数据，可按需初始化为空 []
                // {
                //     id: 'session-001',
                //     title: '默认对话',
                //     createdAt: getLocalISOString(),
                //     agents: [
                //         {
                //             threadId: IdUtils.generateGuid(),
                //             modelId: defaultModelId,
                //             params: {
                //                 max_tokens: 1000,
                //                 temperature: 0.7,
                //                 top_p: 0.9,
                //                 top_k: 40,
                //             },
                //             messages: [],
                //         }
                //     ],
                // },
            ],
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
        ...createChatActions()
    },

})
