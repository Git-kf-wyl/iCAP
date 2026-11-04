// stores/chat.js
import { IdUtils } from "@/utils/IdUtils.js";
import { getLocalISOString } from "@/utils/TimeUtils.js";

const defaultModelId = 'deepseek-r1-distill-qwen-32b'

const defaultParam = {
    max_tokens: 1000,
    temperature: 0.7,
    top_p: 0.9,
    top_k: 40,
    presence_penalty: 0,
    frequency_penalty: 0
}

export function createChatActions() {
    return {
        // 切换当前会话
        switchSession(sessionId) {
            const exists = this.sessions.some(s => s.id === sessionId)
            if (exists) {
                this.currentSessionId = sessionId
            } else {
                console.warn(`Session ${sessionId} 不存在`)
            }
        },

        // 创建新会话
        createSession(title = '新对话', modelId = defaultModelId, params = defaultParam) {
            const id = IdUtils.generateGuid()
            const now = getLocalISOString()
            const newSession = {
                id,
                title,
                createdAt: now,
                agents: [
                    {
                        threadId: IdUtils.generateGuid(),
                        modelId,
                        params: { ...defaultParam, ...params },
                        messages: [],
                    },
                ],
            }
            this.sessions = [newSession, ...this.sessions]
            this.currentSessionId = id
            return id
        },

        createSessionFromCurrent(title = '新对话') {
            const id = IdUtils.generateGuid()
            const now = getLocalISOString()
            const newSession = {
                id,
                title,
                createdAt: now,
                agents: JSON.parse(JSON.stringify([...this.currentSession.agents])),
            }
            newSession.agents.forEach(agent => {
                agent.threadId = IdUtils.generateGuid()
                agent.messages = []
            })
            this.sessions = [newSession, ...this.sessions]
            this.currentSessionId = id
            return id
        },

        updateSessionTitle(sessionId, title) {
            const s = this.sessions.find(s => s.id === sessionId)
            if (s) {
                s.title = title
            }
        },

        /**
         * 向当前会话添加一个新的 agent
         * @param {string} modelId       模型标识
         * @param {object} [params]      调参，默认 { max_tokens:1000, temperature:0.7, top_p:0.9, top_k:40 }
         */
        addAgent(modelId, params = defaultParam) {
            const session = this.currentSession
            if (!session) {
                console.warn('当前会话不存在，无法添加 agent')
                return
            }
            // 推入新的 agent
            session.agents.push({
                threadId: IdUtils.generateGuid(),
                modelId,
                params: { ...params },
                messages: [],
            })
        },

        // 删除会话
        deleteSession(sessionId) {
            const idx = this.sessions.findIndex(s => s.id === sessionId)
            if (idx === -1) {
                console.warn(`Session ${sessionId} 不存在`)
                return
            }

            // 如果只有一个会话，并且要删除的是它，则不删除会话，只清空消息
            if (this.sessions.length === 1 && this.sessions[0].id === sessionId) {
                const session = this.sessions[0]
                session.agents.forEach(agent => {
                    agent.messages = []
                })
                return
            }

            // 否则正常删除
            const isCurrent = this.currentSessionId === sessionId
            this.sessions.splice(idx, 1)

            // 如果删掉的是当前会话，则切换到第一个
            if (isCurrent) {
                this.currentSessionId = this.sessions[0].id
            }
        },

        // 添加用户消息到当前会话所有 agent
        addUserMessage(content) {
            const session = this.currentSession
            if (!session) {
                console.warn('当前会话不存在，无法添加消息')
                return
            }
            const msg = {
                role: 'user',
                content,
                timestamp: getLocalISOString(),
            }
            session.agents.forEach(agent => {
                agent.messages.push({ ...msg })
            })
        },

        // 添加 assistant 消息到指定 model
        addAssistantMessage(content, threadId) {
            const session = this.currentSession
            if (!session) {
                console.warn('当前会话不存在，无法添加消息')
                return
            }
            const agent = session.agents.find(a => a.threadId === threadId)
            if (!agent) {
                console.warn(`模型 ${threadId} 不在当前会话中`)
                return
            }
            const msg = {
                role: 'assistant',
                content,
                timestamp: getLocalISOString(),
                like: 0,
                isFinished: false
            }
            agent.messages.push(msg)
            return agent.messages[agent.messages.length - 1]  // 把刚 push 的原始对象返回
        },

        updateAssistantMessageLike(likeValue, msgId, threadId) {
            const session = this.currentSession
            const agent = session.agents.find(a => a.threadId === threadId)
            agent.messages[msgId].like = likeValue
        },

        /**
         * 清空指定线程的所有消息
         * @param {string} threadId  要清空消息的 threadId
         */
        clearThreadMessages(threadId) {
            const session = this.currentSession
            if (!session) {
                console.warn('当前会话不存在，无法清空消息')
                return
            }
            const agent = session.agents.find(a => a.threadId === threadId)
            if (!agent) {
                console.warn(`线程 ${threadId} 不存在于当前会话中`)
                return
            }
            agent.messages = []
        },

        resetParams(threadId, params) {
            const session = this.currentSession
            if (!session) {
                console.warn('当前会话不存在，无法清空消息')
                return
            }
            const agent = session.agents.find(a => a.threadId === threadId)
            if (!agent) {
                console.warn(`线程 ${threadId} 不存在于当前会话中`)
                return
            }
            agent.params = params;
            console.log('agent params', agent.params)
        },


        // 移除当前会话里的某个 agent，但至少保留一个
        removeAgent(threadId) {
            const session = this.currentSession
            if (!session) {
                console.warn('当前会话不存在，无法移除 agent')
                return
            }
            if (session.agents.length <= 1) {
                console.warn('至少要保留一个 agent，操作已取消')
                return
            }
            const idx = session.agents.findIndex(a => a.threadId === threadId)
            if (idx === -1) {
                console.warn(`模型 ${threadId} 不在当前会话中`)
                return
            }
            session.agents.splice(idx, 1)
        },

        loadHistory(logData, type = 'text') {
            const newSessions = [];
            // 按chat_id分组
            const sessionsMap = new Map();

            // 首先按chat_id分组存储数据
            logData.forEach(info => {
                // console.log('info')
                // console.log(info)
                if (info.active) {
                    const chatId = info.chat_id;
                    if (!sessionsMap.has(chatId)) {
                        sessionsMap.set(chatId, []);
                    }
                    sessionsMap.get(chatId).push(info);
                }
            });
            if (sessionsMap.size > 0) {

                // 处理每个chat_id组
                sessionsMap.forEach((infos, chatId) => {
                    // 按时间戳升序排序（最早到最晚）
                    infos.sort((a, b) => a.timestamp - b.timestamp);

                    // 获取第一条记录的时间（用于createdAt）
                    const firstInfo = infos[0];
                    const roundedTimestamp = Math.round(firstInfo.timestamp);
                    const date = new Date(roundedTimestamp);

                    // 格式化时间字符串
                    const year = date.getUTCFullYear();
                    const month = String(date.getUTCMonth() + 1).padStart(2, '0');
                    const day = String(date.getUTCDate()).padStart(2, '0');
                    const hours = String(date.getUTCHours()).padStart(2, '0');
                    const minutes = String(date.getUTCMinutes()).padStart(2, '0');
                    const seconds = String(date.getUTCSeconds()).padStart(2, '0');
                    const milliseconds = String(date.getUTCMilliseconds()).padStart(3, '0');
                    const createdAt = `${year}-${month}-${day}T${hours}:${minutes}:${seconds}.${milliseconds}Z`;

                    // 合并所有消息（按时间顺序）
                    const allMessages = [];
                    infos.forEach(info => {
                        console.log('info')
                        console.log(info)
                        if (info.type !== 'text') {
                            allMessages.push({
                                content: { text: info.query, previewUrl: info.file_base64 },
                                role: 'user',
                                timestamp: info.timestamp,
                            })
                        }
                        else {
                            allMessages.push({
                                content: info.query,
                                role: 'user',
                                timestamp: info.timestamp,
                            })
                        }
                        allMessages.push({
                            content: info.response,
                            role: 'assistant',
                            isFinished: true,
                            like: 0,
                            timestamp: info.end_time,
                        })
                    });

                    // 获取最后一条记录的配置（用于params）
                    const lastInfo = infos[infos.length - 1];

                    newSessions.push({
                        id: chatId,
                        title: infos[0].query.length > 15 ? infos[0].query.slice(0, 15) + "..." : infos[0].query.slice(0, 15),
                        createdAt,
                        agents: [
                            {
                                threadId: IdUtils.generateGuid(),
                                modelId: lastInfo.model_id,
                                params: { ...defaultParam, ...lastInfo.config },
                                messages: allMessages,  // 合并后的消息数组
                            },
                        ],
                    });
                });

                this.sessions = [...newSessions.reverse()];
                this.currentSessionId = newSessions.length > 0 ? newSessions[0].id : null;
            }
        },

        setHasLoadedLog(val) {
            this.hasLoadedLog = val
        }
    };
}