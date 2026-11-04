// src/stores/aiModel.js
import {defineStore} from 'pinia'
import {ModelService} from "@/services/modelService.js";

export const useAIModelStore = defineStore('aiModel', {
    // state: 返回一个对象，包含所有可响应的数据
    state: () => ({
        models: [],
        applyDeployModels: []
    }),

    // getters: 类似计算属性，接收 state 作为第一个参数
    getters: {
        // 返回所有 model_id
        allIds(state) {
            return state.models.map(m => m.model_id)
        },
        // 根据 id 查模型，注意这里要返回一个函数，以便传参
        getModelById(state) {
            return (id) => state.models.find(m => m.model_id === id)
        },

        getModelName(state) {
            return (id) => state.models.find(m => m.model_id === id)?.info.model_name || id
        },

        getFirstAvailableId(state) {
            return state.models.find(m => m.status && m.is_available)?.model_id || ''
        }
    },

    // actions: 可以是同步也可以是异步，方法里的 this 指向 state 和 getters
    actions: {
        // 初始化或刷新列表
        setModels(list) {
            this.models = (Array.isArray(list) ? list.sort((a, b) => {
                return b.is_available === a.is_available ? b.status - a.status : b.is_available - a.is_available;
            }) : [])
        },

        // 增
        addModel(model) {
            if (!this.models.find(m => m.model_id === model.model_id)) {
                this.models.push(model)
            }
        },

        // 改
        updateModel(updated) {
            const idx = this.models.findIndex(m => m.model_id === updated.model_id)
            if (idx !== -1) this.models.splice(idx, 1, updated)
        },

        // 删
        removeModel(id) {
            const idx = this.models.findIndex(m => m.model_id === id)
            if (idx !== -1) this.models.splice(idx, 1)
        },

        // 异步拉取
        async fetchModels() {
            try {
                const data = await ModelService.getAllModelInfo();
                this.setModels(data)
            } catch (err) {
                console.error('获取 AI 模型失败', err)
            }
        },

        setApplyDeployModels(list) {
            this.models = (Array.isArray(list) ? list.sort((a, b) => {
                return b.is_available === a.is_available ? b.status - a.status : b.is_available - a.is_available;
            }) : [])
        },
    }
})
