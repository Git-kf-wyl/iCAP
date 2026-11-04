export const dimensionKeys = {
  attention_status: "注意力大类",
  attention_category: "注意力小类",
  sitting_posture_status: "坐姿大类",
  sitting_posture_category: "坐姿小类",
  distance_status: "视距检测",
  seat_status: "离座检测",
};

export const attentionEnum = [
  "集中",
  "离座",
  "睡觉",
  "使用电子设备",
  "玩玩具",
  "吃零食",
  "东张西望",
  "遮挡",
  "其他",
];

export const sittingPostureEnum = [
  "正常",
  "离座",
  "趴桌",
  "低头",
  "歪头",
  "斜肩",
  "仰躺",
  "仰头",
  "托腮",
  "遮挡",
  "其他",
];

export const distanceEnum = [
  "视距正常",
  "视距过近",
  "视线不在书本上",
  "视线不可见",
  "离座",
];

export const seatStatusEnum = ["离座状态", "在座状态", "画面遮挡"];

export const excludedDimensions = ["注意力大类", "坐姿大类"];

export const statusDimensionNameMap: Record<string, string> = {
  attention_status: "注意力大类",
  attention_category: "注意力小类",
  sitting_posture_status: "坐姿大类",
  sitting_posture_category: "坐姿小类",
  distance_status: "视距检测",
  seat_status: "离座检测",
};

export const compositeCategoryMap: Record<string, string> = {
  attention_category: "异常组合类",
  sitting_posture_category: "异常组合类",
  distance_status: "异常组合类",
  seat_status: "组合类",
};

export const dimensionNames: Record<string, string> = {
  attention_category: "注意力小类",
  distance_status: "视距检测",
  sitting_posture_category: "坐姿小类",
  seat_status: "离座检测",
};