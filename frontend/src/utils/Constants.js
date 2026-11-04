export const URLS={BASE:window.location.origin,BASE_HTTPS:window.location.origin,SESSION:'/api/auth/me',WS:'/ws/monitor'};
export const STRINGS={EMPTY:'',DASH:'-'};
export const API_BASE_URL='/v1/';
export const API_AGENT_URL='/v1/';
export const DATA_FACTORY_API='/v1/data-factory/';
export const DATA_FACTORY_LOG_WS=(location.protocol==='https:'?'wss://':'ws://')+location.host+'/v1/data-factory/';
export const DEPLOY_API_BASE='/v1/deployment/';
export const API_MENSHEN_URL='/v1/performance';
export const PAYLOAD_MENSHEN={product:'LLM'};
export const DEFAULT_CONFIG = {
    headers: { 'Content-Type': 'application/json' },
    timeout: 5000,
};

export const AXIOS_POST_CONFIG = {
    headers: { 'Content-Type': 'application/json' },
    timeout: 20000,
};

export const INTERPRETATION_TAGS = ["ASR", "MT", "TTS"];

export const INTERPRETATIONS_TYPES = ["ASR", "MT", "TTS", "ASR+MT", "ASR+MT+TTS"];
