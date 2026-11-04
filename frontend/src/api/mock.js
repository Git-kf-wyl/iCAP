// 将所有接口封装为异步请求方法
const mockService = {
    getModelRanking: async () => {
        try {
            const module = await import('@/assets/mockData/modelRanking.json');
            return module.default.data;
        } catch (error) {
            return null;
        }
    },
    getCurrentFullRes: async () => {
        try {
            const module = await import('@/assets/mockData/currentFullRes.json');
            return module.default;
        } catch (error) {
            return null;
        }
    },
};

// 一次性导出所有 API
export default mockService;