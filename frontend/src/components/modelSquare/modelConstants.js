export const AUDIO_REPORT_DATASETS = ["librispeech_asr", "MELD", "MMAU"]
export const VISION_REPORT_DATASETS = ["MMMU", "MMStar", "Video-MME"]
export const AV_REPORT_DATASETS = ["librispeech_asr", "MELD", "MMAU", "MMMU", "MMStar", "Video-MME", "WorldSense"]

export const REPORT_TYPE = {
  DOWNLOAD: 0,
  GENERATE: 1
};

export const LLM_REPORT_DATASETS = ["om", "32b", "8b", "4b"]

export const LLM_DATASET_TO_REPORT_TYPE = {
  "om": 1,
  "32b": 2,
  "8b": 3,
  "4b": 4
};