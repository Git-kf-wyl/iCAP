import axios from "axios";
import { API_BASE_URL, AXIOS_POST_CONFIG } from "@/utils/Constants.js";

// 解析SSE消息格式
function parseSSEMessage(raw) {
    let result = '';
    if (raw === '\n') {
        return raw;
    }
    raw.split('\n').forEach(line => {
        const colonIndex = line.indexOf(':');
        if (colonIndex <= 0) {
            result = '\n';
            return;
        }
        const field = line.slice(0, colonIndex);
        let value = line.slice(colonIndex + 1);
        if (value.startsWith(' ')) value = value.slice(1);

        if (field === 'data') {
            result = result ? `${result}${value}` : value;
        }
        // else if (field in result) {
        //     result[field] = value;
        // }
    });

    // if (result) {
    //     try {
    //         result = JSON.parse(result);
    //     } catch (e) {
    //         // 保留原始数据格式
    //     }
    // }

    return result;
}


function isPPTFilePath(raw) {
    return raw.startsWith('file: ')
}

function isTaskId(raw) {
    return raw.startsWith('taskid: ')
}

function getPPTFilePath(raw) {
    return raw.substring(6);
}

function getTaskId(raw) {
    return raw.substring(8);
}

class AgentChatService {

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
            endpoint,
            taskid,
            query,
            generateType,
            filePath = '',
            user_id = 'admin',
            file,
        },
        updateMessage = (message) => {
            console.log(message)
        },
        onFinish = (message, error) => {
        },
        extraHeaders = {},
        notifyFilePath = (path) => { },
        notifyTaskId = (taskId) => { }
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
            // 创建 FormData 对象
            const formData = new FormData();

            // 添加原始数据（后台通过 request.form 获取）
            formData.append('taskid', taskid);
            formData.append('query', query);
            formData.append('generateType', generateType);
            formData.append('user_id', user_id);

            // 添加文件（假设 file 是 Blob/File 对象）
            formData.append('file', file);  // 字段名必须为 'file'

            // 复制 extraHeaders 并删除手动指定的 Content-Type
            const headers = new Headers(extraHeaders);
            // headers.delete('Content-Type');  // 让浏览器自动设置 multipart 边界

            // 发送请求
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: headers,  // 使用处理后的请求头
                body: formData     // 自动设置 multipart/form-data
            });
            // const response = await fetch(endpoint, {
            //     method: 'POST',
            //     headers: {
            //         'Content-Type': 'application/json',
            //         ...extraHeaders
            //     },
            //     body: JSON.stringify({
            //         taskid: taskid,
            //         query: query,
            //         generateType: generateType,
            //         user_id: user_id
            //     })
            // });
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

                    buffer = decoder.decode(value, { stream: true });
                    const messages = buffer.split('\n\n');
                    if (!messages.at(-1)) {
                        messages.pop();
                    }

                    for (const msg of messages) {
                        try {
                            if (isPPTFilePath(msg)) {
                                const pptFilePath = getPPTFilePath(msg);
                                if (pptFilePath) {
                                    notifyFilePath(pptFilePath)
                                }
                                continue
                            }
                            if (isTaskId(msg)) {
                                const taskId = getTaskId(msg);
                                if (taskId) {
                                    notifyTaskId(taskId)
                                }
                                continue
                            }
                            const parsed = parseSSEMessage(msg);
                            if (parsed === "[DONE]") {
                                onFinish(resBuffer, false)
                                console.log('DONE');
                                reader.closed
                                return
                            }
                            resBuffer += parsed;
                            resBuffer += '\n';
                            updateMessage(resBuffer);
                        } catch (e) {
                            console.error('解析SSE消息失败:', e);
                        }
                    }
                }
            } else {
                onFinish(errorMessage + "，有非200返回值", true)
            }
        } catch (e) {
            clearInterval(t);
            onFinish(errorMessage + "，响应中断，请联系管理员(w00649384)排查", true)
        }
    }
    static async sendDeepResearchMessage(
        {
            endpoint,
            taskid,
            query = '',
            user_id = 'admin',
            deepResearchType = 'fast',
            url_list='',
            is_search=true
        },
        updateMessage = msg => {
            console.log(msg)
        },
        onFinish = (msg, isError) => {
        }
    ) {
        // update teh loading text periodically
        let timeInterval = 100;
        const errorMessage = '获取DeepResearch失败';
        // display a loading animation when waiting response
        let base = this.updateLoadingStatusByCallBack(updateMessage, timeInterval, 0);
        let t = setInterval(
            () => {
                this.updateLoadingStatusByCallBack(updateMessage, timeInterval, base)
            },
            timeInterval)
            ;
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    taskid: taskid,
                    query: query,
                    user_id: user_id,
                    deepResearchType: deepResearchType,
                    url_list:url_list,
                    is_search:is_search
                })
            });
            // stop updating the loading text
            clearInterval(t);
            // handle the response accroding to status code
            if (response.status === 200) {
                // buffer for response text
                let buffer = "";
                let resBuffer = "";
                const decoder = new TextDecoder("utf-8");
                const reader = response.body.getReader();

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) {
                        onFinish(resBuffer, false)
                        console.log('DeepResearch流式传输结束');
                        reader.closed
                        return;
                    }

                    buffer = decoder.decode(value, { stream: true });
                    const messages = buffer.split('\n\n');
                    if (!messages.at(-1)) {
                        messages.pop();
                    }

                    for (const msg of messages) {
                        try {
                            const parsed = parseSSEMessage(msg);
                            if (parsed === "[DONE]") {
                                onFinish(resBuffer, false)
                                console.log('DONE');
                                reader.closed
                                return
                            }
                            resBuffer += parsed;
                            resBuffer += '\n';
                            updateMessage(resBuffer);
                        } catch (e) {
                            console.error('解析SSE消息失败:', e);
                        }
                    }
                }
            } else {
                onFinish(errorMessage + "，有非200返回值", true)
            }
        } catch (error) {
            // 异常情况
            clearInterval(t);
            onFinish(errorMessage, true);
        }
    }
    static async startDeepResearchMessage(
        {
            endpoint,
            taskid,
            query
        }
    ) {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                taskid: taskid,
                query: query,
            })
        });

        return response;
    }
}

export {
    AgentChatService
}