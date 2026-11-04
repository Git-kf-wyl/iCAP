const state = () => ({
    allData: [],
    dataSets: [],
    label: '',
    MTDataset: [],
    directoryA: '',
    directoryB: '',
    directoryC: [],
    directoryD: [],
    labelDirectoryC: '',
    MTDirectionC: '',
    MTDirectionD: '',
    openDatasetInfo: false,
    openLabelInfo: false,
    openMTDatasetInfo: false,
});

const mutations = {
    setAllData(state, allData) {
        state.allData = allData;
    },
    setDataSets(state, dataSets) {
        state.dataSets = dataSets;
    },
    setLabel(state, label) {
        state.label = label;
    },
    setMTDataset(state, MTDataset) {
        state.MTDataset = MTDataset;
    },
    setDirectoryA(state, directoryA) {
        state.directoryA = directoryA;
    },
    setDirectoryB(state, directoryB) {
        state.directoryB = directoryB;
    },
    setDirectoryC(state, directoryC) {
        state.directoryC = directoryC;
    },
    setDirectoryD(state, directoryD) {
        state.directoryD = directoryD;
    },
    setLabelDirectoryC(state, labelDirectoryC) {
        state.labelDirectoryC = labelDirectoryC;
    },
    setMTDirectionC(state, MTDirectionC) {
        state.MTDirectionC = MTDirectionC;
    },
    setMTDirectionD(state, MTDirectionD) {
        state.MTDirectionC = MTDirectionD;
    },
    setOpenDatasetInfo(state, openDatasetInfo) {
        state.openDatasetInfo = openDatasetInfo;
    },
    setOpenLabelInfo(state, openLabelInfo) {
        state.openLabelInfo = openLabelInfo;
    },
    setOpenMTDatasetInfo(state, openMTDatasetInfo) {
        state.openMTDatasetInfo = openMTDatasetInfo;
    }
};

const actions = {
    updateAllData({ commit }, allData) {
        commit('setAllData', allData);
    },
    updateDataSets({ commit }, dataSets) {
        commit('setDataSets', dataSets);
    },
    updateLabel({ commit }, label) {
        commit('setLabel', label);
    },
    updateMTDataset({ commit }, MTDataset) {
        commit('setMTDataset', MTDataset);
    },
    updateDirectoryA({ commit }, directoryA) {
        commit('setDirectoryA', directoryA);
    },
    updateDirectoryB({ commit }, directoryB) {
        commit('setDirectoryB', directoryB);
    },
    updateDirectoryC({ commit }, directoryC) {
        commit('setDirectoryC', directoryC);
    },
    updateDirectoryD({ commit }, directoryD) {
        commit('setDirectoryD', directoryD);
    },
    updateLabelDirectoryC({ commit }, labelDirectoryC) {
        commit('setLabelDirectoryC', labelDirectoryC);
    },
    updateMTDirectionC({ commit }, MTDirectionC) {
        commit('setMTDirectionC', MTDirectionC);
    },
    updateMTDirectionD({ commit }, MTDirectionD) {
        commit('setMTDirectionD', MTDirectionD);
    },
    updateOpenDatasetInfo({ commit }, openDatasetInfo) {
        commit('setOpenDatasetInfo', openDatasetInfo);
    },
    updateOpenLabelInfo({ commit }, openLabelInfo) {
        commit('setOpenLabelInfo', openLabelInfo);
    },
    updateOpenMTDatasetInfo({ commit }, openMTDatasetInfo) {
        commit('setOpenMTDatasetInfo', openMTDatasetInfo);
    }
};

const getters = {
    getAllData: state => state.allData,
    getDataSets: state => state.dataSets,
    getLabel: state => state.label,
    getMTDataset: state => state.MTDataset,
    getDirectoryA: state => state.directoryA,
    getDirectoryB: state => state.directoryB,
    getDirectoryC: state => state.directoryC,
    getDirectoryD: state => state.directoryD,
    getLabelDirectoryC: state => state.labelDirectoryC,
    getMTDirectionC: state => state.MTDirectionC,
    getMTDirectionD: state => state.MTDirectionD,
    getOpenDatasetInfo: state => state.openDatasetInfo,
    getOpenLabelInfo: state => state.openLabelInfo,
    getOpenMTDatasetInfo: state => state.openMTDatasetInfo
};

export default {
    namespaced: true,
    state,
    mutations,
    actions,
    getters
};
