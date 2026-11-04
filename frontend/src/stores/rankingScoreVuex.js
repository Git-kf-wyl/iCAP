const state = () => ({
    activeTab: 'ruler1',
    activeSphereTab: 'operations',
});


const mutations = {
    setActiveTab(state, activeTab) {
        state.activeTab = activeTab;
    },
    setActiveSphereTab(state, activeSphereTab) {
        state.activeSphereTab = activeSphereTab;
    },
};

const actions = {
    updateActiveTab({ commit }, activeTab) {
        commit('setActiveTab', activeTab);
    },
    updateActiveSphereTab({ commit }, activeSphereTab) {
        commit('setActiveSphereTab', activeSphereTab);
    },
};

const getters = {
    getActiveTab: state => state.activeTab,
    getActiveSphereTab: state => state.activeSphereTab,
};

export default {
    namespaced: true,
    state,
    mutations,
    actions,
    getters
};