import { INTERPRETATION_TAGS } from "@/utils/Constants.js";
import { useAIModelStore } from "@/stores/aiModel.js";

export function isModelAvailable(model) {
    if (model.info.tags.includes("native")) {
        return true;
    }
    return model.is_available && model.status;
}

export function isLocalChatModel(model) {
    if (model.info.tags.includes("native")) {
        return true;
    }
    return model.status && model.is_available && !(model.info.tags.length === 1 && INTERPRETATION_TAGS.includes(model.info.tags[0].toUpperCase()))
}

export function isModelAvailableById(modelId) {
    const model = useAIModelStore().getModelById(modelId)
    if (!model) return false
    return model.status && model.is_available
}

export function isMLLMModelById(modelId) {
    const model = useAIModelStore().getModelById(modelId)
    if (!model) return false
    return model.info.category[0].toUpperCase() === 'MLLM'
}

export function isLocalChatModelById(modelId) {
    if (modelId) {
        const model = useAIModelStore().getModelById(modelId)
        if (!model) return false
        const modelInfo = model.info
        return model.status && model.is_available && !(modelInfo.tags.length === 1 && INTERPRETATION_TAGS.includes(modelInfo.tags[0].toUpperCase()))
    }
}
