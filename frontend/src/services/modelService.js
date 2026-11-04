const defaultIcon = '/images/icap-mark-v1.svg'
import qwen from '@/assets/qwen.png'
import deepseek from '@/assets/deepseek.png'
import llama from '@/assets/llama.png'
import openBmb from '@/assets/openBmb.webp'
import mistral from '@/assets/mistral.jfif'
import openai from '@/assets/openai.jpg'
import gemini from '@/assets/gemini.svg'
import zai from '@/assets/z-icon.svg'
import minimax from '@/assets/minimax.png'
import gemma from '@/assets/gemma.png'
import doubao from '@/assets/doubao_avatar.png'
import longcat from '@/assets/longcat.png'

import axios from "axios";
import { API_BASE_URL, DEFAULT_CONFIG } from "@/utils/Constants.js";

class ModelService {
    static catalog = [];

    static async registerModel(modelData) {
        const url = `${API_BASE_URL}register_model`;
        const res = await axios.post(url, modelData, DEFAULT_CONFIG);
        return res.data;
    }

    // 修改已有模型
    static async modifyModel(modelData) {
        const url = `${API_BASE_URL}modify_model`;
        const res = await axios.post(url, modelData, DEFAULT_CONFIG);
        return res.data;
    }

    static async getAllModelInfo() {
        const url = `${API_BASE_URL}get_model_info`;
        const payload = {};
        const res = await axios.get(url, payload, DEFAULT_CONFIG);
        // console.log(res.data)
        ModelService.catalog = Array.isArray(res.data) ? res.data : [];
        return res.data;
    }

    // 获取单个模型信息
    static async getOneModelInfo(modelId) {
        const url = `${API_BASE_URL}get_one_model_info`;
        const payload = { model_id: modelId };
        const res = await axios.post(url, payload, DEFAULT_CONFIG);
        // console.log(res.data)
        return res.data;
    }

    static async deleteModelInfo(modelId) {
        const url = `${API_BASE_URL}delete_model`;
        const payload = [modelId];
        const res = await axios.post(url, payload, DEFAULT_CONFIG);
        // console.log(res.data)
        return res.data;
    }

    static getParamName(paramId) {
        const paramIdToNameMap = {
            'max_tokens': '最大 Token 数量',
            'temperature': '温度',
            'top_p': 'Top P',
            'top_k': 'Top K',
            'presence_penalty': '存在惩罚',
            'frequency_penalty': '频率惩罚',
        }
        return paramIdToNameMap[paramId] || modelId
    }

    static getModelIcon(modelId) {
        if (!modelId) {
            return defaultIcon;
        }

        const lowerCaseModelId = modelId.toLowerCase();

        const iconMap = {
            'qwen': qwen,
            'qwq': qwen,
            'pangu': defaultIcon,
            'deepseek': deepseek,
            'llama': llama,
            'minicpm': openBmb,
            'mistral': mistral,
            'ministral': mistral,
            'gemini': gemini,
            'glm': zai,
            'minimax': minimax,
            'openai': openai,
            'gemma': gemma,
            'doubao': doubao,
            'longcat': longcat
        };

        for (const [key, icon] of Object.entries(iconMap)) {
            if (lowerCaseModelId.includes(key)) {
                return icon;
            }
        }

        return defaultIcon;
    }

    static getModelDesc(modelId) {
        return ModelService.catalog.find(m => m.model_id === modelId)?.info.model_desc || '已接入的模型服务'
    }

    // ── 模型颜色映射（全局固定分配） ──────────────────────────
    static #colorPool = [
        "#1F1F1F", "#1C7FF8", "#34A853", "#EB3568", "#FFBB00",
        "#9C27B0", "#FF5722", "#00BCD4", "#795548", "rgb(115, 108, 211)",
        "#3F51B5", "#8BC34A", "#FF9800", "#009688", "#673AB7",
        "#FFC107", "#607D8B", "#CDDC39", "#D81B60", "rgb(216, 152, 131)",
        "#5E35B1", "#43A047", "#FF7043", "#26C6DA", "#8D6E63",
        "#EC407A", "#3949AB", "#66BB6A", "#FDD835", "#7E57C2",
    ];
    static #modelColorMap = null;

    static getModelColor(modelName) {
        if (!this.#modelColorMap) {
            this.#modelColorMap = new Map();
        }
        if (!this.#modelColorMap.has(modelName)) {
            const color = this.#colorPool[this.#modelColorMap.size % this.#colorPool.length];
            this.#modelColorMap.set(modelName, color);
        }
        return this.#modelColorMap.get(modelName);
    }

    /** 重置颜色分配（仅在需要刷新时调用） */
    static resetModelColors() {
        this.#modelColorMap = null;
    }

    static async applyDeployModel(data) {
        const url = `${API_BASE_URL}apply_deploy_model`;
        const res = await axios.post(url, data, DEFAULT_CONFIG);
        return res.data;
    }

    static async getApplyDeployList() {
        const url = `${API_BASE_URL}get_apply_deploy_list`;
        const res = await axios.get(url, DEFAULT_CONFIG);
        return res.data;
    }
}

export {
    ModelService
}
