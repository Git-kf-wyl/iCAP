import { defineStore } from 'pinia';

export const useReportPreviewStore = defineStore('reportPreview', {
    state: () => ({
        isFullscreen: false,
    }),
    actions: {
        toggleFullscreen() {
            this.isFullscreen = !this.isFullscreen;
        },
        setFullscreen(val) {
            this.isFullscreen = val;
        },
    },
});