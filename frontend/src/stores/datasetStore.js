import { defineStore } from 'pinia';
import { get_datasets } from '@/api/dataSetApi'; // 你的API方法
import _ from 'lodash';

export const useDatasetStore = defineStore('dataset', {
    state: () => ({
        ruler1Datasets: {},
        ruler2Datasets: {},
        ruler3Datasets: {}
    }),
    getters: {
        getDatasetById: (state) => (dataType, id) => {
            if(dataType === 'ruler1'){
                return state.ruler1Datasets[id]
            }else if(dataType === 'ruler2') {
                return state.ruler2Datasets[id]
            } else {
                return state.ruler3Datasets[id]
            }
        },
        getDatasets: (state) => (dataType) => {
            if(dataType === 'ruler1'){
                return state.ruler1Datasets
            }else if(dataType === 'ruler2') {
                return state.ruler2Datasets
            }else {
                return state.ruler3Datasets
            }
        },
    },
    actions: {
        // 初始化或刷新列表
        setDatasets(dataType, map) {
            if(dataType === 'ruler1'){
                this.ruler1Datasets = map
            }else if(dataType === 'ruler2') {
                this.ruler2Datasets = map
            }else {
                this.ruler3Datasets = map
            }
        },
        // 增
        addDataset(dataType, dataset) {
            if(dataType === 'ruler1'){
                if (!this.ruler1Datasets.find((k, v) => dataset.k)) {
                    this.ruler1Datasets.push(dataset)
                } 
            }else if(dataType === 'ruler2') {
                if (!this.ruler2Datasets.find((k, v) => dataset.k)) {
                    this.ruler2Datasets.push(dataset)
                }
            } else {
                if (!this.ruler3Datasets.find((k, v) => dataset.k)) {
                    this.ruler3Datasets.push(dataset)
                }
            }
        },

        // 改
        updateDataset(dataset) {
            if(dataType === 'ruler1'){
                for (const [outerKey, innerObj] of Object.entries(dataset)) {
                    if (this.ruler1Datasets[outerKey]) {
                    // 更新或添加内层字典的键值对
                        this.ruler1Datasets[outerKey] = innerObj
                    }
            }
            }else if(dataType === 'ruler2'){
                for (const [outerKey, innerObj] of Object.entries(dataset)) {
                    if (this.ruler2Datasets[outerKey]) {
                    // 更新或添加内层字典的键值对
                        this.ruler2Datasets[outerKey] = innerObj
                    }
                }
            } else {
                
                for (const [outerKey, innerObj] of Object.entries(dataset)) {
                    if (this.ruler3Datasets[outerKey]) {
                    // 更新或添加内层字典的键值对
                        this.ruler3Datasets[outerKey] = innerObj
                    }
                }
            }
        },

        // 删
        removeDataset(id) {
            if(dataType === 'ruler1'){
                if (this.ruler1Datasets.find((k, v) => dataset.k)) {
                    delete this.ruler1Datasets.id
                } 
            }else if(dataType === 'ruler2'){
                if (this.ruler2Datasets.find((k, v) => dataset.k)) {
                    delete this.ruler2Datasets.id
                }
            } else {
                
                if (this.ruler3Datasets.find((k, v) => dataset.k)) {
                    delete this.ruler3Datasets.id
                }
            }
        },
        async fetchModels(dataType) {
            try {
                if(dataType === 'ruler1'){
                    get_datasets().then((res)=>{
                        console.log('res', res)
                        this.setDatasets('ruler1', res.data)
                        console.log(this.state)
                }, (err)=> {
                    console.error('获取数据集失败', err)
                })
                }else{
                    console.error('接口开发中')
                }
            } catch (err) {
                console.error('获取测试集失败', err)
            }
        }
    }
});
