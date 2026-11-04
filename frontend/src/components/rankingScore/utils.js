import { STRINGS } from "@/utils/Constants.js";

export const formatValue = (value) => {
    if (value === STRINGS.DASH) return value;
    if (value === -1) return STRINGS.DASH;
    const numberValue = parseFloat(value) * 100;
    return isNaN(numberValue) ? STRINGS.DASH : numberValue.toFixed(1);
};

export const formatDate = (timestamp) => {
    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
        return STRINGS.DASH;
    }
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}/${month}/${day}`;
};