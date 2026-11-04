import axios from "axios";
import { API_BASE_URL, AXIOS_POST_CONFIG } from "@/utils/Constants.js";
import { ElMessage } from "element-plus";

// 解析SSE消息格式
function parseSSEMessage(raw) {
    return raw.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).replace(/^ /,'')).join('\n');
}

class ChatService {

    static updateLoadingStatusByCallBack = (updateMessage, timeInterval = 100, base = 0) => {
        let frames = ["◜", "◠", "◝", "◞", "◡", "◟"];
        let time = Math.floor(new Date().getTime() / timeInterval);
        if (base === 0) {
            base = time;
        }
        let frameNum = (time - base) % frames.length;
        updateMessage(frames[frameNum] + " Loading" + ".".repeat(frameNum));
        return base;
    }

    static async sendMsgStream(
        {
            chatId,
            endpoint,
            model,
            config,
            signal,
            query,
            filePath = '',
            userId = 'admin',
            isDeepResearch = false,
            deepResearchType = 'fast',
            isThink=false
        },
        updateMessage = (message) => {
            console.log(message)
        },
        onFinish = (message, error) => {
        },
        extraHeaders = {}
    ) {
        // update teh loading text periodically
        let timeInterval = 100;
        const errorMessage = '获取模型响应失败';
        // display a loading animation when waiting response
        let base = this.updateLoadingStatusByCallBack(updateMessage, timeInterval, 0);
        let t = setInterval(
            () => {
                this.updateLoadingStatusByCallBack(updateMessage, timeInterval, base)
            },
            timeInterval)
            ;
        try {
            console.log('start sendMsgStream, filePath', filePath)
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...extraHeaders
                },
                body: JSON.stringify({
                    chat_id: chatId,
                    model: model,
                    query: query,
                    file_path: filePath,
                    config: config,
                    user_id: userId,
                    isDeepResearch: isDeepResearch,
                    deepResearchType: deepResearchType,
                    isThink:isThink
                }),
                signal    // 透传 signal，用于中断
            });
            // stop updating the loading text
            clearInterval(t);
            // handle the response accroding to status code
            if (response.status === 200) {
                // buffer for response text
                let reasoningBuffer = '';
                let buffer = "";
                let resBuffer = "";
                const decoder = new TextDecoder("utf-8");
                const reader = response.body.getReader();

                // 第一种解析SSE格式
                // function read() {
                //     reader.read().then(({ done, value }) => {
                //         if (done) {
                //             console.log('done')
                //             onFinish(buffer, false)
                //             // eventSource.close();
                //             reader.closed
                //             return;
                //         }
                //         const text = decoder.decode(value);
                //         // 处理 SSE 格式
                //         text.split("\n\n").forEach(chunk => {
                //             if (chunk.startsWith("data:")) {
                //                 const data = chunk.slice(6);
                //                 if (data !== "[DONE]") {
                //                     buffer += data
                //                     updateMessage(buffer)
                //                 }
                //             }
                //         });
                //         read();
                //     });
                // }
                // read();

                // 第二种解析SSE格式
                let thinkFlag = false;
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) {
                        onFinish(resBuffer, false)
                        console.log('流式传输结束');
                        reader.closed
                        return;
                    }

                    buffer += decoder.decode(value, { stream: true });
                    const messages = buffer.split('\n\n');
                    buffer = messages.pop() || '';

                    for (const msg of messages) {
                        try {
                            const parsed = parseSSEMessage(msg);
                            if (parsed === "[DONE]") {
                                onFinish(resBuffer, false)
                                console.log('DONE');
                                reader.closed
                                return
                            }
                            // 正常消息处理
                            resBuffer += parsed;
                            updateMessage(resBuffer);
                        } catch (e) {
                            console.error('解析SSE消息失败:', e);
                        }
                    }
                }
            } else {
                onFinish(errorMessage, true)
            }
        } catch (e) {
            clearInterval(t);
            onFinish(errorMessage, true)
        }
    }

    static async sendCompanyApiMessage(
        {
            endpoint,
            apiKey,
            model,
            messages,
            signal
        },
        updateMessage = msg => {
            console.log(msg)
        },
        onFinish = (msg, isError) => {
        },
        extraHeaders = {}
    ) {
        // 1. 启动 loading 动画
        const errorMessage = '请求失败';
        const timeInterval = 100;
        let base = this.updateLoadingStatusByCallBack(updateMessage, timeInterval, 0);
        const timer = setInterval(() => {
            this.updateLoadingStatusByCallBack(updateMessage, timeInterval, base);
        }, timeInterval);

        try {
            // 2. 组织请求体，取最后一条消息 content 作为 query
            const last = messages.slice(-1)[0] || {content: ''};
            const body = JSON.stringify({
                model: model,
                query: last.content
            });

            // 3. 发送 fetch 请求
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${apiKey}`,
                    ...extraHeaders
                },
                body,
                signal
            });

            // 4. 停止 loading
            clearInterval(timer);

            if (!res.ok) {
                // 非 2xx
                const msg = `请求失败，状态码 ${res.status}`;
                updateMessage(msg);
                onFinish(msg, true);
                return;
            }

            // 5. 读取并解析返回值
            const data = await res.json();
            // 示例返回 { result: "...", thinking: "..." }
            const {result = '', thinking = ''} = data;
            let text = '';
            if (thinking) {
                text += ` <think>${thinking}</think>`;
            }
            text += result;
            updateMessage(text);
            onFinish(text, false);
        } catch (error) {
            // 异常情况
            clearInterval(timer);
            updateMessage(errorMessage);
            onFinish(errorMessage, true);
        }
    }

    static async sendMsgNotStream(payload,
                                  updateMessage = msg => {console.log(msg)},
                                  onFinish = (msg, isError) => {},) {
        const url = `${API_BASE_URL}chat`;
        const timeInterval = 100;
        let base = this.updateLoadingStatusByCallBack(updateMessage, timeInterval, 0);
        const timer = setInterval(() => {
            this.updateLoadingStatusByCallBack(updateMessage, timeInterval, base);
        }, timeInterval);

        try {
            console.log('start sendMsgNotStream')
            const res = await axios.post(url, payload, AXIOS_POST_CONFIG);
            clearInterval(timer);
            console.log('send chat res', res)
            if (res.status === 200) {
                // 示例返回 { result: "...", thinking: "..." }
                const {result = '', thinking = ''} = res.data;
                let text = '';
                if (thinking) {
                    text += ` <think>${thinking}</think>`;
                }
                text += result;
                onFinish(text.length === 0 ? '响应为空！' : text, false)
            } else {
                onFinish(`未收到响应： ${res.status}`, false)
            }
        } catch (e) {
            clearInterval(timer);
            onFinish("请求失败", true)
        }

    }

    static async upLoadFile(payload,
                            onFinish = (msg, isError) => {}) {
        const url = `${API_BASE_URL}chat/upload_file`;
        try {
            const response = await axios.post(url, payload, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });
            if (response.status === 200) {
                onFinish(response.data, false);
            } else {
                onFinish(`未收到响应： ${response.status}`, false)
            }
        } catch (e) {
            onFinish("请求失败", true)
        }
    }

    static async isEndpointReachable(
        { endpoint, apiKey, extraHeaders = {} }
    ) {
        try {
            const res = await fetch(endpoint, {
                method: 'OPTIONS',
                headers: {
                    'Authorization': `Bearer ${apiKey}`,
                    ...extraHeaders
                },
            })
            return res.status !== 0 // 只要没抛错就算可达，或者你也可以判断 res.ok
        } catch {
            return false
        }
    }
}

export {
    ChatService
}
