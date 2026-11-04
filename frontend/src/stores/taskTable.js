const state = () => ({
    pageNum: 1,
});


const mutations = {
    setPageNum(state, pageNum) {
        state.pageNum = pageNum;
    },
};

const actions = {
    updatePageNum({ commit }, pageNum) {
        commit('setPageNum', pageNum);
    },
};

const getters = {
    getPageNum: state => state.pageNum,
};

export default {
    namespaced: true,
    state,
    mutations,
    actions,
    getters
};