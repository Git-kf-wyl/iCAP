import { defineStore } from 'pinia';
import { startRunTest } from '@/api/dataService.js'; // 你的API方法

export const useTaskStore = defineStore('tasks', {
    state: () => ({
        tasks: []
    }),
    getters: {
        getTaskById: (state) => (id) => {
            return state.tasks.filter((item) => item.ID === id)
        },
        getTasks: (state) => {
            return state.tasks
        },
    },
    actions: {
        // 初始化或刷新列表
        setTasks(tasks) {
            this.tasks = tasks
        },
        // 增
        addDataset(dataType, dataset) {
            if(dataType === 'ruler1'){
                if (!this.ruler1Task.find((k, v) => dataset.k)) {
                    this.ruler1Task.push(dataset)
                }
            }else if(dataType === 'ruler2') {
                if (!this.ruler2Task.find((k, v) => dataset.k)) {
                    this.ruler2Task.push(dataset)
                }
            } else {
                if (!this.ruler3Task.find((k, v) => dataset.k)) {
                    this.ruler3Task.push(dataset)
                }
            }
        },

        // 改
        updateDataset(dataset) {
            if(dataType === 'ruler1'){
                for (const [outerKey, innerObj] of Object.entries(dataset)) {
                    if (this.ruler1Task[outerKey]) {
                    // 更新或添加内层字典的键值对
                        this.ruler1Task[outerKey] = innerObj
                    }
                }
            }else if(dataType === 'ruler2'){
                for (const [outerKey, innerObj] of Object.entries(dataset)) {
                    if (this.ruler2Task[outerKey]) {
                    // 更新或添加内层字典的键值对
                        this.ruler2Task[outerKey] = innerObj
                    }
                }
            } else {

                for (const [outerKey, innerObj] of Object.entries(dataset)) {
                    if (this.ruler3Task[outerKey]) {
                    // 更新或添加内层字典的键值对
                        this.ruler3Task[outerKey] = innerObj
                    }
                }
            }
        },

        // 删
        removeDataset(id) {
            if(dataType === 'ruler1'){
                if (this.ruler1Task.find((k, v) => dataset.k)) {
                    delete this.ruler1Task.id
                }
            }else if(dataType === 'ruler2'){
                if (this.ruler2Task.find((k, v) => dataset.k)) {
                    delete this.ruler2Task.id
                }
            } else {
                if (this.ruler3Task.find((k, v) => dataset.k)) {
                    delete this.ruler3Task.id
                }
            }
        }
    }
});
