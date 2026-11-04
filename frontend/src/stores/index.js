import { createStore } from 'vuex';
import rankingScore from './rankingScoreVuex.js';
import taskTable from './taskTable.js';
import resultTable from './resultTable.js';
import interpretation from './interpretation.js';

export default createStore({
    modules: {
        rankingScore,
        taskTable,
        resultTable,
        interpretation
    },
    state: {
        selectedCategories: [],
        selectedTags: [],
        selectedSizeRange: { label: "全部", min: 0, max: Infinity },
        deployType: 'all',
        tags: [],
        screeningType: 'all',
        viewMode: 'card',
        shownIntroduction: true
    },
    mutations: {
        setSelectedCategories(state, categories) {
            state.selectedCategories = categories;
        },
        setSelectedTags(state, selectedTags) {
            state.selectedTags = selectedTags;
        },
        setSelectedSizeRange(state, sizeRange) {
            state.selectedSizeRange = sizeRange;
        },
        setDeployType(state, type) {
            state.deployType = type;
        },
        setTags(state, tags) {
            state.tags = tags;
        },
        setScreeningType(state, screeningType) {
            state.screeningType = screeningType;
        },
        setViewMode(state, viewMode) {
            state.viewMode = viewMode;
        },
        setShownIntroduction(state, shownIntroduction) {
            state.shownIntroduction = shownIntroduction;
        }
    },
    actions: {
        updateSelectedCategories({ commit }, selectedCategories) {
            commit('setSelectedCategories', selectedCategories);
        },
        updateSelectedTags({ commit }, selectedTags) {
            commit('setSelectedTags', selectedTags);
        },
        updateSelectedSizeRange({ commit }, selectedSizeRange) {
            commit('setSelectedSizeRange', selectedSizeRange);
        },
        updateDeployType({ commit }, deployType) {
            commit('setDeployType', deployType);
        },
        updateTags({ commit }, tags) {
            commit('setTags', tags);
        },
        updateScreeningType({ commit }, screeningType) {
            commit('setScreeningType', screeningType);
        },
        updateViewMode({ commit }, viewMode) {
            commit('setViewMode', viewMode);
        },
        updateShownIntroduction({ commit }, shownIntroduction) {
            commit('setShownIntroduction', shownIntroduction);
        }
    },
    getters: {
        getSelectedCategories: state => state.selectedCategories,
        getSelectedTags: state => state.selectedTags,
        getSelectedSizeRange: state => state.selectedSizeRange,
        getDeployType: state => state.deployType,
        getTags: state => state.tags,
        getScreeningType: state => state.screeningType,
        getViewMode: state => state.viewMode,
        getShownIntroduction: state => state.shownIntroduction
    }
});