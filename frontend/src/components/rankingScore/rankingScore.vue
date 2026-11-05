<template>
  <div class="container" style="display: flex; flex-direction: column">
    <el-tabs
      v-model="activeTab"
      class="tabsContainer"
      @tab-click="tabClick"
      :class="{ 'no-slide': disableSlide }"
    >
      <!-- =============== 尺子一：业界通用测评集榜单 =============== -->
      <el-tab-pane label="尺子一：通用榜单" name="ruler1">
        <el-container class="insideContainer">
          <div class="hint-bar">
            <div class="hint-text">榜单全平台共享，由管理员评测后发布。点击模型名称查看分数雷达图，可用模型以模型广场为准。</div>
          </div>
          <!-- 尺子一模态切换卡片 -->
          <div class="rankingTable">
            <div class="headerContainer">
              <div class="headerRow1">
                <div class="ruler2-tabs">
                  <span
                    v-for="mod in RULER1_MODALITIES"
                    :key="mod.key"
                    class="ruler2-tab"
                    :class="{ active: activeRuler1Modality === mod.key }"
                    @click="activeRuler1Modality = mod.key"
                  >{{ mod.label }}</span>
                </div>
                <div class="statistic_1mafc">
                  <el-tooltip
                    effect="dark"
                    :content="'两把尺子的选型逻辑，文本、视觉、音频模态的测试集选型指南'"
                    placement="top"
                  >
                    <el-link
                      href="https://wiki.huawei.com/domains/67832/wiki/278411/WIKI2026062311563537"
                      target="_blank"
                      style="font-size: 14px;font-weight:600px;line-height: 20px;text-align: center;"
                    >
                      <span style="color:white;margin-right: 5px;">点击查看：测评榜单展示逻辑</span>
                      <el-icon color="white" size="20">
                        <QuestionFilled />
                      </el-icon>
                    </el-link>
                  </el-tooltip>
                  <span class="updateTimeText">{{ currentRuler1Models.length }} 模型</span>
                  <span class="divider_1mafc"></span>
                  <span class="updateTimeText">{{ currentRuler1UpdateTime }}</span>
                  <el-button
                    class="export-btn"
                    type="primary"
                    size="small"
                    :icon="Download"
                    @click="exportRuler1Excel"
                  >导出Excel</el-button>
                </div>
              </div>
            </div>
            <el-table
              :key="'ruler1-' + activeRuler1Modality + '-' + isLoading"
              :data="currentRuler1Sorted"
              :header-cell-style="tableHeaderStyle"
              fit
              class="modelTableFull"
              :row-class-name="currentRuler1RowClassName"
              v-loading="isLoading && currentRuler1Models.length === 0"
              element-loading-text="加载中..."
              max-height="600"
            >
              <el-table-column label="名次" width="70" align="center" fixed>
                <!-- <template #default="{ row }">
                  <span>{{ row._computedRank }}</span>
                </template>-->
                <template #default="{ row }">
                  <div class="rank-cell">
                    <template v-if="row._computedRank === 1">
                      <img src="/images/rank1.svg" class="model-icon" />
                    </template>
                    <template v-else-if="row._computedRank === 2">
                      <img src="/images/rank2.svg" class="model-icon" />
                    </template>
                    <template v-else-if="row._computedRank === 3">
                      <img src="/images/rank3.svg" class="model-icon" />
                    </template>
                    <div v-else class="rank-container">
                      <img src="/images/rankBox.png" class="rank-icon" />
                      <span class="rank-number">{{ row._computedRank }}</span>
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="模型" :width="modelMinWidth" fixed>
                <template #default="{ row }">
                  <div class="nameAndScore">
                    <el-tooltip :content="row.name" effect="dark" placement="top">
                      <span class="model-name" @click="handleClickName(row)">{{ row.name }}</span>
                    </el-tooltip>
                    <el-tooltip v-if="row._isPending" effect="dark" placement="top">
                      <template #content>
                        <div
                          style="max-width: 360px"
                        >新模型发布后，平台将第一时间启动部署工作，启动测评后，该模型将显示"评测中"，底色为黄色，7天后刷新评测报告</div>
                      </template>
                      <el-icon color="#999" size="16" style="margin-left: 2px">
                        <InfoFilled />
                      </el-icon>
                    </el-tooltip>
                  </div>
                  <div class="nameAndScore">
                    <span v-if="row._isNew" class="newrank">New</span>
                    <span class="publisherTag">{{ row.publisher }}</span>
                  </div>
                </template>
              </el-table-column>
              <!-- 均分在前（紧挨模型） -->
              <el-table-column width="80" align="center" fixed>
                <template #header>
                  <span class="sortable-header" @click="setSort('_avg')">
                    均分{{ getSortIcon('_avg') }}
                    <el-tooltip effect="dark" content="均分计算公式，各测试集实测分数取平均" placement="top">
                      <el-link
                        :href="getAverageScoreWikiUrl()"
                        target="_blank"
                        @click.stop
                        underline="never"
                      >
                        <el-icon
                          color="#1b3882"
                          size="16"
                          style="margin-left: 2px; vertical-align: middle;"
                        >
                          <QuestionFilled />
                        </el-icon>
                      </el-link>
                    </el-tooltip>
                  </span>
                </template>
                <template #default="{ row }">
                  <span class="low-style">{{ row._avg != null ? formatValue(row._avg) : '-' }}</span>
                </template>
              </el-table-column>
              <!-- 各测评集列（含子列：实测/官方/差值） -->
              <el-table-column
                v-for="ds in currentRuler1Datasets"
                :key="ds.key"
                align="center"
                :class-name="ruler1DatasetColumnClass(ds)"
                :min-width="isTempDataset(ds) ? 120 : undefined"
              >
                <template #header>
                  <span class="sortable-header">
                    <span class="ds-name" @click="goDatasetComparison(ds)">{{ ds.label }}</span>
                    <span
                      class="sort-arrow"
                      :class="{ active: sortArrowActive(ds.key) }"
                      @click.stop="setSort(ds.key)"
                    >
                      <el-icon :size="12"><component :is="sortArrowComp(ds.key)" /></el-icon>
                    </span>
                    <el-tooltip effect="dark" content="点击跳转：测试集说明" placement="top">
                      <el-link
                        :href="getDatasetWikiUrl(ds.key)"
                        target="_blank"
                        @click.stop
                        underline="never"
                      >
                        <el-icon
                          color="#1b3882"
                          size="16"
                          style="margin-left: 2px; vertical-align: middle;"
                        >
                          <QuestionFilled />
                        </el-icon>
                      </el-link>
                    </el-tooltip>
                  </span>
                </template>
                <el-table-column label="实测" align="center" :class-name="ruler1DatasetCellClass(ds)">
                  <template #default="{ row }">
                    <el-tooltip
                      v-if="row[ds.key] != null && !hasEvaluationTask(row, ds.key)"
                      effect="dark"
                      content="线下测试"
                      placement="top"
                    >
                      <span
                        :class="{ 'highest-score': isHighestScore(row, ds.key, currentRuler1MaxScores) }"
                      >{{ formatValue(row[ds.key]) }}</span>
                    </el-tooltip>
                    <span
                      v-else
                      :class="{ 'highest-score': isHighestScore(row, ds.key, currentRuler1MaxScores), 'score-clickable': row[ds.key] != null && hasEvaluationTask(row, ds.key) }"
                      @click="handleScoreClick(row, ds.key)"
                    >{{ row[ds.key] != null ? formatValue(row[ds.key]) : '-' }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="官方" align="center" :class-name="ruler1DatasetCellClass(ds)">
                  <template #default="{ row }">
                    <span>{{ row[ds.key + '_official'] != null ? formatValue(row[ds.key + '_official']) : '-' }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="差值" align="center" :class-name="ruler1DatasetCellClass(ds, 'diff-column')">
                  <template #default="{ row }">
                    <span
                      :style="diffColor(row[ds.key], row[ds.key + '_official'])"
                    >{{ computeDiff(row[ds.key], row[ds.key + '_official']) }}</span>
                  </template>
                </el-table-column>
              </el-table-column>
              <el-table-column label="评测时间" width="130" align="center">
                <template #header>
                  <span class="sortable-header">
                    评测时间
                    <el-tooltip effect="dark" content="本榜单只展示近两年的主流模型" placement="top">
                      <el-icon
                        color="#1b3882"
                        size="16"
                        style="margin-left: 2px; vertical-align: middle;"
                      >
                        <InfoFilled />
                      </el-icon>
                    </el-tooltip>
                  </span>
                </template>
                <template #default="{ row }">
                  <span>{{ row._updateTimeLabel }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div>
            <div class="hint-text">① 榜单测试结果均由AI创新平台测试工程实测得来，该测试工程与评估方法可信可用；</div>
            <div class="hint-text">
              ②
              针对部分与官方发布测评结果的分差
              >5分的测试集，我们进行了多次测试与badcase分析，并尝试从官网获取解释以及官方badcase，但无正式结论，测评结果公平公正，不作修改。
            </div>
          </div>
        </el-container>
      </el-tab-pane>

      <!-- =============== 尺子二：领域测评集榜单 =============== -->
      <el-tab-pane label="尺子二：领域榜单" name="ruler2">
        <el-container class="insideContainer">
          <div class="hint-bar">
            <div class="hint-text">点击模型名称可以已查看榜单分数雷达图</div>
          </div>
          <div class="rankingTable">
            <div class="headerContainer">
              <!-- 一级目录标签 -->
              <div class="headerRow1">
                <div class="ruler2-tabs">
                  <span
                    v-for="cat in ruler2Categories"
                    :key="cat.key"
                    class="ruler2-tab"
                    :class="{ active: activeRuler2Category === cat.key }"
                    @click="activeRuler2Category = cat.key; activeRuler2SubCategory = null"
                  >{{ cat.label }}</span>
                </div>
                <div class="statistic_1mafc">
                  <el-tooltip
                    effect="dark"
                    :content="'两把尺子的选型逻辑，文本、视觉、音频模态的测试集选型指南'"
                    placement="top"
                  >
                    <el-link
                      href="https://wiki.huawei.com/domains/67832/wiki/278411/WIKI2026062311563537"
                      target="_blank"
                      style="font-size: 14px;font-weight:600px;line-height: 20px;text-align: center;"
                    >
                      <span style="color:white;margin-right: 5px;">点击查看：测评榜单展示逻辑</span>
                      <el-icon color="white" size="20">
                        <QuestionFilled />
                      </el-icon>
                    </el-link>
                  </el-tooltip>
                  <span class="updateTimeText">{{ currentRuler2Data.length }} 模型</span>
                  <span class="divider_1mafc"></span>
                  <span class="updateTimeText">{{ currentRuler2UpdateTime }}</span>
                  <el-button
                    class="export-btn"
                    type="primary"
                    size="small"
                    :icon="Download"
                    @click="exportRuler2Excel"
                  >导出Excel</el-button>
                </div>
              </div>
            </div>
            <!-- 二级目录标签（仅多级榜单显示） -->
            <div
              v-if="currentRuler2Subs && currentRuler2Subs.length > 0"
              class="ruler2-sub-tabs-container"
            >
              <template v-for="group in currentRuler2Subs" :key="group.key">
                <div class="ruler2-sub-group">
                  <span
                    v-if="group.children"
                    class="ruler2-sub-tab ruler2-primary-sub"
                    :class="{ active: currentRuler2SubKey && group.children.some(c => c.key === currentRuler2SubKey) }"
                    @click="activeRuler2SubCategory = group.children[0]?.key || group.key"
                  >{{ group.label }}</span>
                  <div v-if="group.children" class="ruler2-sub-children">
                    <span
                      v-for="child in group.children"
                      :key="child.key"
                      class="ruler2-sub-tab ruler2-secondary-sub"
                      :class="{ active: currentRuler2SubKey === child.key }"
                      @click="activeRuler2SubCategory = child.key"
                    >{{ child.label }}</span>
                  </div>
                  <!-- 无子类别的（如 aisf_banxue 直接作为二级标签） -->
                  <span
                    v-if="!group.children"
                    class="ruler2-sub-tab ruler2-secondary-sub"
                    :class="{ active: currentRuler2SubKey === group.key }"
                    @click="activeRuler2SubCategory = group.key"
                  >{{ group.label }}</span>
                </div>
              </template>
            </div>
            <el-table
              :data="currentRuler2Data"
              :header-cell-style="tableHeaderStyle"
              fit
              class="modelTableFull"
              :expand-row-keys="expandedRowKeys"
              :row-key="row => row._uid"
              @expand-change="onExpandChange"
              v-loading="isLoading && currentRuler2Data.length === 0"
              element-loading-text="加载中..."
              max-height="600"
            >
              <el-table-column v-if="currentRuler2SubKey !== 'aisf_banxue'" type="expand" width="1">
                <template #default="{ row }">
                  <!-- 3级子场景展开（如伴学：注意力检测/坐姿检测下的细分子场景） -->
                  <div
                    v-if="row._triSubsets && row._triSubsets.length > 0 && row._triSubsets[0].subsets"
                    class="expanded-row-container"
                  >
                    <div
                      v-for="group in row._triSubsets"
                      :key="group.name"
                      class="expanded-sub-group"
                    >
                      <div class="expanded-group-title">
                        {{ group.name }}
                        <span
                          class="expanded-group-score"
                        >均分: {{ formatValue(group.score) }}</span>
                      </div>
                      <table
                        class="custom-score-table"
                        style="width: 100%; border-collapse: collapse;"
                      >
                        <thead>
                          <tr>
                            <th v-for="s in group.subsets" :key="s.name">{{ s.name }}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td v-for="s in group.subsets" :key="s.name">{{ formatValue(s.score) }}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <!-- 原有 tri_subsets 展开（其他数据集） -->
                  <div
                    v-else-if="row._triSubsets && row._triSubsets.length > 0"
                    class="expanded-row-container"
                  >
                    <table
                      class="custom-score-table"
                      style="width: 100%; border-collapse: collapse;"
                    >
                      <thead>
                        <tr>
                          <th v-for="s in row._triSubsets" :key="s.name">{{ s.name }}</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td v-for="s in row._triSubsets" :key="s.name">{{ formatValue(s.score) }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </template>
              </el-table-column>

              <el-table-column label="名次" width="70" align="center" fixed>
                <template #default="{ row, $index }">
                  <div class="rank-cell">
                    <template v-if="row._banxueRank != null">
                      <template v-if="row._banxueRank === 1">
                        <img src="/images/rank1.svg" class="model-icon" />
                      </template>
                      <template v-else-if="row._banxueRank === 2">
                        <img src="/images/rank2.svg" class="model-icon" />
                      </template>
                      <template v-else-if="row._banxueRank === 3">
                        <img src="/images/rank3.svg" class="model-icon" />
                      </template>
                      <div v-else class="rank-container">
                        <img src="/images/rankBox.png" class="rank-icon" />
                        <span class="rank-number">{{ row._banxueRank }}</span>
                      </div>
                    </template>
                    <template v-else>
                      <template v-if="$index + 1 === 1">
                        <img src="/images/rank1.svg" class="model-icon" />
                      </template>
                      <template v-else-if="$index + 1 === 2">
                        <img src="/images/rank2.svg" class="model-icon" />
                      </template>
                      <template v-else-if="$index + 1 === 3">
                        <img src="/images/rank3.svg" class="model-icon" />
                      </template>
                      <div v-else class="rank-container">
                        <img src="/images/rankBox.png" class="rank-icon" />
                        <span class="rank-number">{{ $index + 1 }}</span>
                      </div>
                    </template>
                  </div>
                </template>
              </el-table-column>
              <el-table-column
                label="模型"
                :min-width="ruler2ModelMinWidth"
                show-overflow-tooltip
                fixed
              >
                <template #default="{ row }">
                  <div class="nameAndScore">
                    <el-tooltip :content="row.name" effect="dark" placement="top">
                      <span class="model-name" @click="handleClickName(row)">{{ row.name }}</span>
                    </el-tooltip>
                  </div>
                  <div class="nameAndScore">
                    <span v-if="row._isNew" class="newrank">New</span>
                    <span class="publisherTag">{{ row.publisher }}</span>
                  </div>
                </template>
              </el-table-column>
              <!-- 伴学在外层不展示总均分，均分在各组列的子列中 -->
              <el-table-column
                v-if="currentRuler2SubKey !== 'aisf_banxue'"
                width="80"
                align="center"
                fixed
              >
                <template #header>
                  <span class="sortable-header" @click="setSort('_avg')">
                    均分{{ getSortIcon('_avg') }}
                    <el-tooltip
                      effect="dark"
                      :content="calcAverageContent(currentRuler2SubKey)"
                      placement="top"
                    >
                      <el-link
                        :href="getAverageScoreWikiUrl()"
                        target="_blank"
                        @click.stop
                        underline="never"
                      >
                        <el-icon
                          color="#1b3882"
                          size="16"
                          style="margin-left: 2px; vertical-align: middle;"
                        >
                          <QuestionFilled />
                        </el-icon>
                      </el-link>
                    </el-tooltip>
                  </span>
                </template>
                <template #default="{ row }">
                  <span class="low-style">{{ row._avg != null ? formatValue(row._avg) : '-' }}</span>
                </template>
              </el-table-column>
              <!-- 非伴学/非记忆：普通扁平列 -->
              <template v-if="currentRuler2SubKey !== 'aisf_banxue'">
                <el-table-column
                  v-for="(col, idx) in currentRuler2Columns"
                  :key="idx"
                  min-width="150"
                  align="center"
                >
                  <template #header>
                    <span class="sortable-header">
                      <span class="ds-name" @click="goDatasetComparison(col)">{{ col.label }}</span>
                      <span
                        class="sort-arrow"
                        :class="{ active: sortArrowActive(col.key) }"
                        @click.stop="setSort(col.key)"
                      >
                        <el-icon :size="12"><component :is="sortArrowComp(col.key)" /></el-icon>
                      </span>
                      <el-tooltip effect="dark" content="点击跳转：测试集说明" placement="top">
                        <el-link
                          :href="getDatasetWikiUrl(col.key, currentRuler2SubKey)"
                          target="_blank"
                          @click.stop
                          underline="never"
                        >
                          <el-icon
                            color="#1b3882"
                            size="16"
                            style="margin-left: 2px; vertical-align: middle;"
                          >
                            <QuestionFilled />
                          </el-icon>
                        </el-link>
                      </el-tooltip>
                    </span>
                  </template>
                  <template #default="{ row }">
                    <div class="table-cell-container">
                      <!-- 意图/改写/记忆场景：分数可点击跳转到测评结果 -->
                      <template
                        v-if="(currentRuler2SubKey === 'aisf_llm_yitu' || currentRuler2SubKey === 'aisf_llm_gaixie' || currentRuler2SubKey==='aisf_memory_cuiqu' || currentRuler2SubKey === 'aisf_memory_zhaohui') && row[col.key] != null"
                      >
                        <el-tooltip
                          v-if="!hasEvaluationTask(row, col.key)"
                          effect="dark"
                          content="线下测试"
                          placement="top"
                        >
                          <span
                            :class="{ 'highest-score': isHighestScore(row, col.key, ruler2MaxScores) }"
                          >{{ formatValue(row[col.key]) }}</span>
                        </el-tooltip>
                        <span
                          v-else
                          :class="{
                            'highest-score': isHighestScore(row, col.key, ruler2MaxScores),
                            'score-clickable': true
                          }"
                          @click="handleScoreClick(row, col.key)"
                        >{{ formatValue(row[col.key]) }}</span>
                      </template>
                      <span
                        v-else
                        :class="{ 'highest-score': isHighestScore(row, col.key, ruler2MaxScores) }"
                      >{{ row[col.key] != null ? formatValue(row[col.key]) : '-' }}</span>
                      <span
                        v-if="row._triMap && row._triMap[col.key] && row._triMap[col.key].length > 0"
                        class="expand-btn"
                        @click="toggleExpand(row, col.key)"
                      >
                        <img
                          :src="isExpandedFor(row, col.key) ? ArrowUp : ArrowDown"
                          class="expand-icon"
                        />
                      </span>
                    </div>
                  </template>
                </el-table-column>
              </template>
              <!-- 伴学/记忆：组列+子列（三级子场景作为子列） -->
              <template v-else>
                <el-table-column
                  v-for="group in banxueGroupColumns"
                  :key="group.key"
                  align="center"
                  class-name="dataset-column-group"
                >
                  <template #header>
                    <span class="sortable-header">
                      <span class="ds-name" @click="goDatasetComparison(group)">{{ group.label }}</span>
                      <span
                        class="sort-arrow"
                        :class="{ active: sortArrowActive(`_avg_${group.key}`) }"
                        @click.stop="setSort(`_avg_${group.key}`)"
                      >
                        <el-icon :size="12"><component :is="sortArrowComp(`_avg_${group.key}`)" /></el-icon>
                      </span>
                      <el-tooltip effect="dark" content="点击跳转：测试集说明" placement="top">
                        <el-link
                          :href="getDatasetWikiUrl(group.key, currentRuler2SubKey)"
                          target="_blank"
                          @click.stop
                          underline="never"
                        >
                          <el-icon
                            color="#1b3882"
                            size="16"
                            style="margin-left: 2px; vertical-align: middle;"
                          >
                            <QuestionFilled />
                          </el-icon>
                        </el-link>
                      </el-tooltip>
                    </span>
                  </template>
                  <el-table-column
                    v-for="child in group.children"
                    :key="child.key"
                    :label="child.label"
                    align="center"
                    class-name="banxue-sub-column"
                  >
                    <template #header>
                      <span class="sortable-header" @click="setSort(child.key)">
                        {{ child.label }}{{ getSortIcon(child.key) }}
                        <el-tooltip
                          effect="dark"
                          :content="currentRuler2SubKey === 'aisf_banxue' ? (group.label.includes('注意力') ?'正确率，排除注意力检测预期结果为遮挡和其他(无效用例)后计算':
                          '正确率，排除以下场景数据：a.注意力小类-单次结果取值为遮挡、其他（无效用例）b.坐姿小类 取值为 遮挡、其他、无（无效用例）c.实际注意力小类取值为\'睡觉\',\'玩电子设备\',\'使用电子设备\',\'玩玩具\',\'吃零食\',\'离座\' d.实际注意力小类取值为\'东张西望\'并且实际坐姿小类取值不是\'仰头\'、\'仰躺\'')
                          : '均分计算公式，各测试集实测分数取平均'"
                          placement="top"
                          v-if="child.label === '均分'"
                        >
                          <el-link
                            href="https://wiki.huawei.com/domains/67832/wiki/278411/WIKI2026062311563537?title=AISF-%E4%BC%B4%E5%AD%A6%E6%99%BA%E8%83%BD%E4%BD%93-"
                            target="_blank"
                            @click.stop
                            underline="never"
                          >
                            <el-icon
                              color="#1b3882"
                              size="16"
                              style="margin-left: 2px; vertical-align: middle;"
                            >
                              <QuestionFilled />
                            </el-icon>
                          </el-link>
                        </el-tooltip>
                      </span>
                    </template>
                    <template #default="{ row }">
                      <el-tooltip
                        v-if="row[child.key] != null && !hasEvaluationTask(row, group.key)"
                        effect="dark"
                        content="线下测试"
                        placement="top"
                      >
                        <span
                          :class="{ 'highest-score': isHighestScore(row, child.key, ruler2MaxScores) }"
                        >{{ formatValue(row[child.key]) }}</span>
                      </el-tooltip>
                      <span
                        v-else
                        :class="{
                          'highest-score': isHighestScore(row, child.key, ruler2MaxScores),
                          'score-clickable': row[child.key] != null && hasEvaluationTask(row, group.key)
                        }"
                        @click="handleScoreClick(row, group.key)"
                      >{{ row[child.key] != null ? formatValue(row[child.key]) : '-' }}</span>
                    </template>
                  </el-table-column>
                </el-table-column>
              </template>
              <el-table-column
                label="测评时间"
                width="130"
                align="center"
                fixed="right"
              >
                <template #header>
                  <span class="sortable-header">
                    测评时间
                    <el-tooltip effect="dark" content="该榜单对应测试集的最近一次测评时间" placement="top">
                      <el-icon
                        color="#1b3882"
                        size="16"
                        style="margin-left: 2px; vertical-align: middle;"
                      >
                        <InfoFilled />
                      </el-icon>
                    </el-tooltip>
                  </span>
                </template>
                <template #default="{ row }">
                  <span>{{ row.updateTime || '-' }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-container>
      </el-tab-pane>

      <!-- 模型竞技场（LMArena） - 保持原有逻辑不变 -->
      <el-tab-pane label="模型竞技场（LMArena）" name="arenaTable">
        <div class="insideContainer chartContainer">
          <el-button
            class="arena-export-btn"
            type="primary"
            size="small"
            :icon="Download"
            @click="exportArenaExcel"
          >导出Excel</el-button>
          <RouterLink
            :to="{ path: '/rankingScore/LMArenaDetails', query: { type: 'language' } }"
            class="toDetail"
          >查看全部 ></RouterLink>
          <div class="charDesc updateTime">{{ arenaModelsDate }}</div>
          <div class="charDesc updatePeriod">{{ arenaModelsUpdatePeriod }}</div>
          <div class="charDesc modelNumber">
            {{ arenaModelsNum }}
            <br />
            {{ arenaModels.length }}
          </div>
          <div class="charDesc speakerTitle">
            <img :src="speakerIcon" alt="speaker" />
            <el-tooltip effect="dark" placement="bottom">
              <template #content>
                <div style="max-width: 50rem">{{ arenaModelsSpeakerTitle }}</div>
              </template>
              <p>{{ arenaModelsSpeakerTitle }}</p>
            </el-tooltip>
          </div>
          <multiScatterChart
            :data="modelEArenaChartData"
            :xData="timeList"
            :yData="scoreList"
            :title="multiScatterChartTitle"
          />
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script lang="ts" setup>
import {useReadUpdates} from '@/useReadUpdates.js';
import {
  ref,
  computed,
  watch,
  onMounted,
  onBeforeUnmount,
  nextTick,
} from "vue";
import { useRouter, useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { STRINGS } from "@/utils/Constants.js";
import { useRankingStore } from "@/stores/rankingStore";
import { formatValue } from "./utils";
import { getMultiModelData, getEvaluationResult } from "@/api/dataService.js";
import { useStore } from "vuex";
import multiScatterChart from "@/charts/multiScatterChart.vue";
import speakerIcon from "@/assets/speaker.svg";
import { API_BASE_URL } from "@/utils/Constants.js";
import axios from "axios";
import ArrowUp from "@/assets/ArrowUp.png";
import ArrowDown from "@/assets/ArrowDown.png";
import { InfoFilled, QuestionFilled, CaretTop, CaretBottom, Download } from "@element-plus/icons-vue";
import { SCENE_GROUPS } from "./datasetComparisonConfig";
import * as XLSX from "xlsx";
import saveAs from "file-saver";

// ============= DATASET 配置 =============
// 每个测试集的 wikiUrl — 未来可单独配置不同的链接
const WIKI_BASE_URL =
  "https://wiki.huawei.com/domains/67832/wiki/278411/WIKI2026062311563537";

// Ruler1 大语言模型：MMLU-Redux AIME2026 LiveCodeBench GPQA_Diamond IF-Eval
const LLM_DATASETS = [
  { key: "mmlu_redux", label: "MMLU-Redux", wikiUrl: WIKI_BASE_URL },
  { key: "aime26", label: "AIME2026", wikiUrl: WIKI_BASE_URL },
  { key: "live_code_bench", label: "LiveCodeBench", wikiUrl: WIKI_BASE_URL },
  { key: "gpqa", label: "GPQA_Diamond", wikiUrl: WIKI_BASE_URL },
  { key: "ifeval", label: "IF-Eval", wikiUrl: WIKI_BASE_URL },
];

// Ruler1 视觉模型：MMMU MMStar Video-MME
const VISION_DATASETS = [
  { key: "MMMU", label: "MMMU", wikiUrl: WIKI_BASE_URL },
  { key: "MMStar", label: "MMStar", wikiUrl: WIKI_BASE_URL },
  { key: "Video-MME", label: "Video-MME", wikiUrl: WIKI_BASE_URL },
];
const VISION_DATASET_KEYS = ["MMMU", "MMStar", "Video-MME"];

// Ruler1 临时测试集（尚未完成测评，不计入均分，整列淡黄色展示）
const LLM_TEMP_DATASETS = [
  { key: "longbench_v2", label: "longbench_v2", wikiUrl: WIKI_BASE_URL, temp: true },
  { key: "mtbench101", label: "mtbench101", wikiUrl: WIKI_BASE_URL, temp: true },
  { key: "safetybench", label: "safetybench", wikiUrl: WIKI_BASE_URL, temp: true },
  { key: "bfcl_v3", label: "bfcl_v3", wikiUrl: WIKI_BASE_URL, temp: true },
];

const VISION_TEMP_DATASETS = [
  { key: "MLVU", label: "MLVU", wikiUrl: WIKI_BASE_URL, temp: true },
  { key: "MMBench", label: "MMBench", wikiUrl: WIKI_BASE_URL, temp: true },
  { key: "OCRBench", label: "OCRBench", wikiUrl: WIKI_BASE_URL, temp: true },
  { key: "MVBench", label: "MVBench", wikiUrl: WIKI_BASE_URL, temp: true },
];

// Ruler1 音频模型：MMAU MMAR WorldSense（LibrisSpeech、Fleurs 已舍弃不展示）
const AUDIO_DATASETS = [
  { key: "MMAU", label: "MMAU", wikiUrl: WIKI_BASE_URL },
  { key: "MMAR", label: "MMAR", wikiUrl: WIKI_BASE_URL },
  { key: "WorldSense", label: "WorldSense", wikiUrl: WIKI_BASE_URL },
];
const AUDIO_DATASET_KEYS = ["MMAU", "MMAR", "WorldSense"];

//Agent测试集
const AGENT_DATASETS = [
  { key: "tau3_bench", label: "tau3_bench", wikiUrl: WIKI_BASE_URL },
  { key: "mcp_atlas", label: "mcp_atlas", wikiUrl: WIKI_BASE_URL },
  { key: "terminal_bench2.1", label: "terminal_bench2.1", wikiUrl: WIKI_BASE_URL },
  { key: "claw_eval", label: "claw_eval", wikiUrl: WIKI_BASE_URL },
];

// ============= Ruler1 模态切换配置 =============
const RULER1_MODALITIES = [
  { key: "llm", label: "大语言模型" },
  { key: "vision", label: "视觉模型" },
  { key: "audio", label: "音频模型" },
  { key: "agent", label: "Agent" },
];

// ============= 官方分数数据（来自 模型分数官方.xlsx） =============
// 注意：官方分数以小数形式存储（Excel 中的 88.6 存为 0.886），与后端实测分数尺度一致
// None 表示查询不到该数据，渲染时显示为 "-"
const OFFICIAL_SCORES = {};

// 将官方分数注入到 model row 上，key 为 "${dsKey}_official"
function injectOfficialScores(row, datasetKeys) {
  const modelName = row.name;
  const modelScores = OFFICIAL_SCORES[modelName];
  if (!modelScores) return row;
  datasetKeys.forEach((dsKey) => {
    if (modelScores[dsKey] !== undefined) {
      row[dsKey + "_official"] = modelScores[dsKey];
    }
  });
  return row;
}

// ============= Model Whitelists for "评测中" =============
const LLM_WHITELIST = new Set([
  "Qwen3-235B-A22B-Thinking-2507",
  "Qwen3-30B-A3B-Thinking-2507",
  "Qwen3-32B",
  "Qwen3-14B",
  "Qwen3-8B",
  "Qwen3.5-397B-A17B",
  "Qwen3.5-122B-A10B",
  "Qwen3.5-35B-A3B",
  "Qwen3.5-27B",
  "Qwen3.5-9B",
  "Qwen3.5-4B",
  "Qwen3.6-35B-A3B",
  "Qwen3.6-27B",
  "DeepSeek-V3.2",
  "DeepSeek-V4-Flash",
  "DeepSeek-V4-Pro",
  "gemma-4-12B",
]);

const VISION_WHITELIST = new Set([
  "Qwen3.5-397B-A17B",
  "Qwen3.5-122B-A10B",
  "Qwen3.5-35B-A3B",
  "Qwen3.5-27B",
  "Qwen3.5-9B",
  "Qwen3.5-4B",
  "Qwen3.6-35B-A3B",
  "Qwen3.6-27B",
  "Qwen3-VL-235B-A22B-Thinking",
  "Qwen3-VL-30B-A3B-Thinking",
  "Qwen3-VL-8B-Thinking",
  "Qwen3-VL-4B-Thinking",
  "Qwen3-VL-32B-Thinking",
  "gemma-4-12B",
]);

const AUDIO_WHITELIST = new Set([
  "Qwen3-Omni-30B-A3B-Instruct",
  "Qwen2.5-Omni-7B",
]);

// ============= Ruler2 类别配置 =============
const ruler2Categories = [{ key: "aisf", label: "AISF" }];

const activeRuler1Modality = ref("llm");
const activeRuler2Category = ref("aisf");

// 每个类别的列配置（用于列头显示）
const RULER2_COLUMN_LABELS = {
  aisf_llm_gaixie: {
    // 明确代词指向: "明确代词指向",
    // 省略主体: "省略主体",
    // 省略主语: "省略主语",
    // 省略宾语: "省略宾语",
    // 省略服务名: "省略服务名",
    // 主题明确: "主题明确",
    // 询问历史细节信息: "询问历史细节信息",
    // 外挂fewshot库: "外挂fewshot库",
    // 不外挂fewshot库: "不外挂fewshot库",
    // "上下文信息无法支持内容补全":"上下文信息无法支持内容补全",
    // "上下文信息无法支持指代消解":"上下文信息无法支持指代消解",
    "需内容补全":"内容补全",
    "需指代消解":"指代消解",
    "意图模糊":"意图模糊",
    "意图完备":"意图完备"
  },
  aisf_banxue: { 注意力检测: "注意力检测", 坐姿检测: "坐姿检测" },
  aisf_llm_yitu: {
    单意图: "单意图",
    两意图: "两意图",
    三意图: "三意图",
  },
  aisf_memory_cuiqu: {
    "记忆萃取-信息点提取": "信息点提取",
    "记忆萃取-更新": "更新",
  },
  aisf_memory_zhaohui: {
    "记忆召回-查询扩写": "查询扩写",
    "记忆召回-总结过滤": "总结过滤",
  },
  aisf_gui_plan: {
    "影音娱乐-长视频(腾讯视频)": "长视频(腾讯视频)",
    "影音娱乐--音乐(QQ音乐)": "音乐(QQ音乐)",
    "影音娱乐-长视频(爱奇艺)": "长视频(爱奇艺)",
    "影音娱乐-长视频(优酷视频)": "长视频(优酷视频)",
    "影音娱乐-长视频(芒果TV)": "长视频(芒果TV)",
    "影音娱乐--音乐(网易云音乐)": "音乐(网易云音乐)",
    "影音娱乐--音乐(酷狗音乐)": "音乐(酷狗音乐)",
    "影音娱乐-短剧(红果)": "短剧(红果)",
    "系统工具-应用安装(应用市场)": "应用安装(应用市场)",
    "游戏(咸鱼之王)": "游戏(咸鱼之王)",
    "游戏(蛋仔派对)": "游戏(蛋仔派对)",
    "游戏(开心消消乐)": "游戏(开心消消乐)",
    "游戏(剑网3)": "游戏(剑网3)",
    "通讯-运营商APP(中国联通)": "运营商APP(中国联通)",
  },
  aisf_gui_vla: {
    "影音娱乐-长视频(腾讯视频)": "长视频(腾讯视频)",
    "影音娱乐--音乐(QQ音乐)": "音乐(QQ音乐)",
    "影音娱乐-长视频(爱奇艺)": "长视频(爱奇艺)",
    "影音娱乐-长视频(优酷视频)": "长视频(优酷视频)",
    "影音娱乐-长视频(芒果TV)": "长视频(芒果TV)",
    "影音娱乐--音乐(网易云音乐)": "音乐(网易云音乐)",
    "影音娱乐--音乐(酷狗音乐)": "音乐(酷狗音乐)",
    "影音娱乐-短剧(红果)": "短剧(红果)",
    "系统工具-应用安装(应用市场)": "应用安装(应用市场)",
    "游戏(咸鱼之王)": "游戏(咸鱼之王)",
    "游戏(蛋仔派对)": "游戏(蛋仔派对)",
    "游戏(开心消消乐)": "游戏(开心消消乐)",
    "游戏(剑网3)": "游戏(剑网3)",
    "通讯-运营商APP(中国联通)": "运营商APP(中国联通)",
  },
  aisf_llm_skilltican: {
    "宽松通过率": "宽松通过率",
  },
  aisf_llm_guican: {
    "GUI提参": "GUI提参",
  },
  aisf_llm_banxue: {
    提参: "提参",
    总结: "总结",
    提醒: "提醒",
  },
  aisf_llm_coordinator: {
    单意图: "单意图",
    两意图: "两意图",
    三意图: "三意图",
  },
};

// aisf_llm_skilltican 子集名 → 列 key 的映射
// 后端当前仍存 "skill提参"，后续将改为 "宽松通过率"（与前端一致），此处兼容两种命名
const SKILLTICAN_SUBSET_MAP = {
  "skill提参": "宽松通过率",
};

// 多级榜单的子类别配置（一级目录 → 二级目录）
const RULER2_SUB_CATEGORIES = {
  aisf: [
    { key: "aisf_banxue", label: "伴学" },
    { key: "aisf_llm_gaixie", label: "改写" },
    { key: "aisf_llm_yitu", label: "意图" },
    { key: "aisf_memory_cuiqu", label: "记忆萃取" },
    { key: "aisf_memory_zhaohui", label: "记忆召回" },
    { key: "aisf_gui_plan", label: "VLM(GUI操控规划)" },
    { key: "aisf_gui_vla", label: "VLA(GUI操控执行)" },
    { key: "aisf_llm_skilltican", label: "skill提参" },
    { key: "aisf_llm_guican", label: "GUI提参" },
    { key: "aisf_llm_banxue", label: "伴学提参" },
    { key: "aisf_llm_coordinator", label: "Coordinator" },
  ],
};

const activeRuler2SubCategory = ref(null);

// 当前选中类别的子类别列表
const currentRuler2Subs = computed(() => {
  const cat = activeRuler2Category.value;
  return RULER2_SUB_CATEGORIES[cat] || null;
});

// 当前选中的二级目录 key（如果没有二级目录就是 null）
const currentRuler2SubKey = computed(() => {
  const subs = currentRuler2Subs.value;
  if (!subs || subs.length === 0) return null;
  // 如果用户选择了一级但没选二级，选中第一个子项的 key
  if (!activeRuler2SubCategory.value) {
    const first = subs[0];
    if (first.children) {
      // 如果一级有 children，取第一个 children 的 key
      return first.children[0]?.key || first.key;
    }
    return first.key;
  }
  return activeRuler2SubCategory.value;
});

// ============= Reactives =============
const router = useRouter();
const route = useRoute();
const store = useStore();
const isLoading = ref(true);

const activeTab = computed(
  () => store.getters["rankingScore/getActiveTab"] || "ruler1"
);
const disableSlide = ref(true);

// ============= Sort State =============
const sortState = ref({ key: null, order: null }); // null | 'asc' | 'desc'

function setSort(key) {
  if (sortState.value.key === key) {
    // 切换排序方向
    if (sortState.value.order === "desc") {
      sortState.value.order = "asc";
    } else if (sortState.value.order === "asc") {
      sortState.value.key = null;
      sortState.value.order = null;
    }
  } else {
    sortState.value.key = key;
    sortState.value.order = "desc";
  }
}

function getSortIcon(key) {
  if (sortState.value.key !== key) return "";
  return sortState.value.order === "asc" ? " ▲" : " ▼";
}

// 排序箭头图标（测试集名称列头）：未排序/降序显示向下箭头，升序显示向上箭头
function sortArrowComp(key) {
  if (sortState.value.key !== key) return CaretBottom;
  return sortState.value.order === "asc" ? CaretTop : CaretBottom;
}

function sortArrowActive(key) {
  return sortState.value.key === key;
}

function applySort(data, sortKey) {
  if (!sortKey || sortState.value.order == null) return data;
  const order = sortState.value.order;
  return [...data].sort((a, b) => {
    const valA = a[sortKey] != null ? a[sortKey] : -Infinity;
    const valB = b[sortKey] != null ? b[sortKey] : -Infinity;
    if (order === "desc") return valB - valA;
    return valA - valB;
  });
}

const tableHeaderStyle = {
  backgroundColor: "#f5f6fd",
  color: "#000000",
  cursor: "pointer",
};

// === Ruler1 原始数据 ===
const llmRawData = ref({});
const multiRawRuler1 = ref({});

// === Ruler2 原始数据 ===
const ruler2Gaixie = ref([]);
const ruler2Yitu = ref([]);
const _multiRuler2Raw = ref({});
const _currentFullRuler2Raw = ref({});

const llmUpdateTime = ref("");
const visionUpdateTime = ref("");
const audioUpdateTime = ref("");
const agentUpdateTime = ref("");

// 预取的测评结果查询表：键为 `${modelName}__${datasetKey}`，值为 true 表示存在关联任务
const evaluationTaskMap = ref(new Map());

// "改写"场景：列 key → evaluation result 中的 dataset 字段值映射
const GAIXIE_DATASET_MAP = {
  // "外挂fewshot库": "外挂fewshot库",
  // "不外挂fewshot库": "不外挂fewshot库",
    "上下文信息无法支持内容补全":"上下文信息无法支持内容补全",
    "上下文信息无法支持指代消解":"上下文信息无法支持指代消解",
    "需内容补全":"需内容补全",
    "需指代消解":"需指代消解",
    "意图模糊":"意图模糊",
    "意图完备":"意图完备"
};

// 标准化字符串：去除非字母数字字符 + 转小写，用于忽略大小写/特殊字符的匹配
function normalizeMatch(str) {
  return str.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
}

function hasEvaluationTask(row, datasetKey) {
  const rowNameNorm = normalizeMatch(row.name);
  // 意图场景：检查是否存在 dataset === '意图' 的评估任务
  if (currentRuler2SubKey.value === "aisf_llm_yitu") {
    for (const [key] of evaluationTaskMap.value.entries()) {
      const [modelId, dataset] = key.split("__");
      if (dataset === "意图" && normalizeMatch(modelId).includes(rowNameNorm)) {
        return true;
      }
    }
    return false;
  } else if (
    currentRuler2SubKey.value === "aisf_memory_cuiqu" ||
    currentRuler2SubKey.value === "aisf_memory_zhaohui"
  ) {
    for (const [key] of evaluationTaskMap.value.entries()) {
      const [modelId, dataset] = key.split("__");
      if (
        dataset.includes(datasetKey) &&
        normalizeMatch(modelId).includes(rowNameNorm)
      ) {
        return true;
      }
    }
    return false;
  }
  // 改写场景：通过 dataset 映射匹配 evaluation result 中的 dataset 字段值
  if (currentRuler2SubKey.value === "aisf_llm_gaixie") {
    const evalDataset = GAIXIE_DATASET_MAP[datasetKey];
    if (!evalDataset) return false;
    // 中文数据集名使用精确匹配（避免 normalizeMatch 过滤掉中文后 "外挂fewshot库" 和 "不外挂fewshot库" 都变成空串）
    for (const [key] of evaluationTaskMap.value.entries()) {
      const [modelId, dataset] = key.split("__");
      if (
        dataset === evalDataset &&
        normalizeMatch(modelId).includes(rowNameNorm)
      ) {
        return true;
      }
    }
    return false;
  }
  const dsKeyNorm = normalizeMatch(datasetKey);
  for (const [key, task] of evaluationTaskMap.value.entries()) {
    const [modelId, dataset] = key.split("__");
    if (
      normalizeMatch(dataset) === dsKeyNorm &&
      normalizeMatch(modelId).includes(rowNameNorm)
    ) {
      return true;
    }
  }
  return false;
}

// ============= Row processing helpers =============
// test_time 形如 "2026-08-20 09:10:36"，榜单中只展示日期部分
function formatTestTime(testTime) {
  if (!testTime) return "";
  return String(testTime).trim().split(/\s+/)[0] || "";
}

function isWithinOneMonth(dateStr) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return false;
  const oneMonthAgo = new Date();
  oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
  return d >= oneMonthAgo;
}

function processRuler1Row(modelName, modelGroup, datasetKeys, tempDatasetKeys = []) {
  const result = modelGroup?.result || [];
  const updateDate = modelGroup?.update_date || "";
  const row = {
    name: modelName,
    publisher: modelGroup?.publisher || STRINGS.DASH,
    _isNew: isWithinOneMonth(updateDate) && (modelGroup?.is_new || false),
    updateTime: updateDate || STRINGS.DASH,
  };
  let scoreSum = 0;
  let scoreCount = 0;
  datasetKeys.forEach((dsKey) => {
    const matched = result.find((item) => item.dataset_name === dsKey);
    if (matched && matched.score != null) {
      row[dsKey] = matched.score;
      scoreSum += matched.score;
      scoreCount++;
    } else {
      row[dsKey] = null;
    }
  });
  // 临时测试集：展示分数但不计入均分
  tempDatasetKeys.forEach((dsKey) => {
    const matched = result.find((item) => item.dataset_name === dsKey);
    if (matched && matched.score != null) {
      row[dsKey] = matched.score;
    } else {
      row[dsKey] = null;
    }
  });
  row._avg = scoreCount > 0 ? scoreSum / scoreCount : null;
  row._updateTimeLabel = row.updateTime;
  // 注入官方分数
  injectOfficialScores(row, datasetKeys);
  return row;
}

function processRuler1RowWithWhitelist(
  modelName,
  modelGroup,
  datasetKeys,
  whitelist,
  tempDatasetKeys = []
) {
  const row = processRuler1Row(modelName, modelGroup, datasetKeys, tempDatasetKeys);
  if (whitelist.has(modelName)) {
    const allHaveScores = datasetKeys.every((dsKey) => row[dsKey] != null);
    if (!allHaveScores) {
      row._isPending = true;
      row._updateTimeLabel = "评测中";
      datasetKeys.forEach((dsKey) => {
        row[dsKey] = null;
      });
      row._avg = null;
    }
  } else {
    const allHaveScores = datasetKeys.every((dsKey) => row[dsKey] != null);
    if (!allHaveScores) return null;
  }
  return row;
}

// ============= Helper: 计算每列最高分（用于标红加粗） =============
function calcColumnMax(rows, columnKeys) {
  const maxMap = {};
  columnKeys.forEach((key) => {
    const scores = rows
      .map((r) => r[key])
      .filter((v) => v != null && typeof v === "number");
    maxMap[key] = scores.length > 0 ? Math.max(...scores) : null;
  });
  return maxMap;
}

function isHighestScore(row, colKey, maxMap) {
  if (maxMap[colKey] == null) return false;
  return row[colKey] != null && row[colKey] === maxMap[colKey];
}

// ============= Helper: 计算差值 =============
function computeDiff(testScore, officialScore) {
  if (testScore == null || officialScore == null) return "-";
  if (officialScore === 0) return "-";
  const diff = (testScore - officialScore) * 100;
  return diff.toFixed(1);
}

function diffColor(testScore, officialScore) {
  if (testScore == null || officialScore == null) return "";
  if (officialScore === 0) return "";
  const diff = (testScore - officialScore) * 100;
  if (diff < 0) return "color: #2e7d32"; // 绿色（负值）
  return "color: #d32f2f"; // 红色（正值或0）
}

// ============= Computed: Ruler1 Models =============
// ============= Helper: 计算"模型"列最小宽度 =============
function calcModelMinWidth(rows) {
  // 模型名 16px + publisher 10px + 间距 + New标签
  // 按字符估算：中文字符≈1em=16px，ASCII≈0.6em=9.6px
  let maxWidth = 0;
  rows.forEach((row) => {
    let w = 0;
    const name = row.name || "";
    for (const ch of name) {
      w += ch.charCodeAt(0) > 127 ? 16 : 9.6;
    }
    // publisher 通常在一行，按 10px 字体估算
    if (row.publisher && row.publisher !== "-") {
      let pw = 0;
      for (const ch of row.publisher) {
        pw += ch.charCodeAt(0) > 127 ? 10 : 6;
      }
      w = Math.max(w, pw);
    }
    // New 标签约 36px + 间距
    if (row._isNew) w += 42;
    // 左右 padding 和额外余量
    w += 32;
    if (w > maxWidth) maxWidth = w;
  });
  // 至少保留 120px，最大不超过 400px
  return Math.max(120, Math.min(400, Math.ceil(maxWidth)));
}

const modelMinWidth = ref(292);

function computeModelMinWidth() {
  const rows = [];
  [...llmModels.value, ...visionModels.value, ...audioModels.value, ...agentModels.value].forEach(
    (r) => {
      if (!rows.some((x) => x.name === r.name)) rows.push(r);
    }
  );
  modelMinWidth.value = calcModelMinWidth(rows);
  console.log(modelMinWidth.value);
}

const llmModels = computed(() => {
  const rows = [];
  Object.entries(llmRawData.value).forEach(([modelName, modelGroup]) => {
    const row = processRuler1RowWithWhitelist(
      modelName,
      modelGroup,
      LLM_DATASETS.map((d) => d.key),
      LLM_WHITELIST,
      LLM_TEMP_DATASETS.map((d) => d.key)
    );
    if (row) rows.push(row);
  });
  return rows;
});

const visionModels = computed(() => {
  const rows = [];
  const visionKeys = VISION_DATASETS.map((d) => d.key);
  const visionTempKeys = VISION_TEMP_DATASETS.map((d) => d.key);
  Object.entries(multiRawRuler1.value).forEach(([modelName, modelGroup]) => {
    const result = modelGroup?.result || [];
    if (!result.some((item) => visionKeys.includes(item.dataset_name))) return;
    const row = processRuler1RowWithWhitelist(
      modelName,
      modelGroup,
      visionKeys,
      VISION_WHITELIST,
      visionTempKeys
    );
    if (row) rows.push(row);
  });
  return rows;
});

const audioModels = computed(() => {
  const rows = [];
  const audioKeys = AUDIO_DATASETS.map((d) => d.key);
  Object.entries(multiRawRuler1.value).forEach(([modelName, modelGroup]) => {
    const result = modelGroup?.result || [];
    if (!result.some((item) => audioKeys.includes(item.dataset_name))) return;
    const row = processRuler1RowWithWhitelist(
      modelName,
      modelGroup,
      audioKeys,
      AUDIO_WHITELIST
    );
    if (row) rows.push(row);
  });
  return rows;
});

const agentModels = computed(() => {
  const rows = [];
  const agentKeys = AGENT_DATASETS.map((d) => d.key);
  Object.entries(llmRawData.value).forEach(([modelName, modelGroup]) => {
    const result = modelGroup?.result || [];
    if (!result.some((item) => agentKeys.includes(item.dataset_name))) return;
    // Agent 榜单：保留具备任一 Agent 测试集分数的模型，缺失项展示为 "-"
    const row = processRuler1Row(modelName, modelGroup, agentKeys);
    if (row) rows.push(row);
  });
  return rows;
});

// ============= Ruler1 模态切换 computed =============
// 是否为临时测试集（尚未完成测评，整列淡黄色展示且不计入均分）
function isTempDataset(ds) {
  return ds && ds.temp === true;
}

// 父列 class：临时列额外加 temp-dataset-column（作用于组头）
function ruler1DatasetColumnClass(ds) {
  return isTempDataset(ds)
    ? "dataset-column-group temp-dataset-column"
    : "dataset-column-group";
}

// 子列 class：临时列额外加 temp-dataset-column（作用于单元格）
function ruler1DatasetCellClass(ds, extra = "") {
  const classes = [];
  if (extra) classes.push(extra);
  if (isTempDataset(ds)) classes.push("temp-dataset-column");
  return classes.join(" ");
}

// 当前模态的数据集列表（正式测试集 + 临时测试集）
const currentRuler1Datasets = computed(() => {
  const mod = activeRuler1Modality.value;
  if (mod === "llm") return [...LLM_DATASETS, ...LLM_TEMP_DATASETS];
  if (mod === "vision") return [...VISION_DATASETS, ...VISION_TEMP_DATASETS];
  if (mod === "audio") return AUDIO_DATASETS;
  if (mod === 'agent') return AGENT_DATASETS;
  return LLM_DATASETS;
});

// 当前模态的 dataset key 列表
const currentRuler1DatasetKeys = computed(() =>
  currentRuler1Datasets.value.map((d) => d.key)
);

// 当前模态的模型列表
const currentRuler1Models = computed(() => {
  const mod = activeRuler1Modality.value;
  if (mod === "llm") return llmModels.value;
  if (mod === "vision") return visionModels.value;
  if (mod === "audio") return audioModels.value;
  if (mod === "agent") return agentModels.value;
  return [];
});

// 当前模态的更新时间
const currentRuler1UpdateTime = computed(() => {
  const mod = activeRuler1Modality.value;
  if (mod === "llm") return llmUpdateTime.value;
  if (mod === "vision") return visionUpdateTime.value;
  if (mod === "audio") return audioUpdateTime.value;
  if (mod === "agent") return agentUpdateTime.value;
  return "";
});

// 排序+排名
function sortRuler1(models) {
  return [...models].sort((a, b) => {
    if (a._isPending && !b._isPending) return -1;
    if (!a._isPending && b._isPending) return 1;
    const avgA = a._avg != null ? a._avg : -1;
    const avgB = b._avg != null ? b._avg : -1;
    return avgB - avgA;
  });
}

function assignRanks(sorted) {
  let rank = 0;
  return sorted.map((row) => {
    if (!row._isPending) rank++;
    return { ...row, _computedRank: row._isPending ? "-" : rank };
  });
}

const currentRuler1Sorted = computed(() => {
  const base = sortRuler1(currentRuler1Models.value);
  if (sortState.value.key && sortState.value.order) {
    return assignRanks(applySort(base, sortState.value.key));
  }
  return assignRanks(base);
});

const currentRuler1MaxScores = computed(() =>
  calcColumnMax(currentRuler1Sorted.value, currentRuler1DatasetKeys.value)
);

// Row class name for current modality
function currentRuler1RowClassName({ row }) {
  return row._isPending ? "pending-row" : "";
}

// ============= Ruler2 Data Processing =============
function processRuler2StoreData(sourceArray, categoryKey) {
  return sourceArray
    .map((item, idx) => {
      const updateDate = item.updateTime || "";
      // 测评时间优先取该测试集的 test_time，缺失时回退到模型更新时间
      const testTime = formatTestTime(item.testTime);
      const row = {
        _uid: `${categoryKey}-${idx}`,
        name: item.name,
        publisher: item.publisher,
        _isNew: isWithinOneMonth(updateDate) && (item.new || false),
        updateTime: testTime || updateDate || "-",
      };
      // 使用后端返回的 averageScore（与 test_time 同级下的 score）作为均分
      row._avg = item.averageScore != null ? Number(item.averageScore) : null;
      const subsets = item.subsets || [];
      const triMap = {};
      subsets.forEach((s) => {
        if (s.tri_subsets && s.tri_subsets.length > 0) {
          triMap[s.key] = s.tri_subsets;
        }
        if (s.score != null && s.score >= 0) {
          row[s.key] = s.score;
        } else {
          row[s.key] = null;
        }
      });
      row._triMap = triMap;
      row._triSubsets = null;
      return row;
    })
    .sort((a, b) => {
      const avgA = a._avg != null ? a._avg : -1;
      const avgB = b._avg != null ? b._avg : -1;
      return avgB - avgA;
    });
}

function processMultiRuler2Data(sourceData, label) {
  console.log("sourceData");
  console.log(sourceData);
  console.log("label");
  console.log(label);
  const rows = [];
  let idx = 0;
  Object.entries(sourceData).forEach(([modelName, modelGroup]) => {
    const matchedResult = (modelGroup?.result || []).find(
      (item) => item.dataset_name === label
    );
    if (!matchedResult) return;
    const subsets = matchedResult.metrics?.[0]?.categories?.[0]?.subsets || [];
    const updateDate = modelGroup?.update_date || "";
    // 测评时间优先取当前榜单对应测试集的 test_time，缺失时回退到模型更新时间
    const testTime = formatTestTime(matchedResult.test_time);
    const row = {
      _uid: `${label}-${idx++}`,
      name: modelName,
      publisher: modelGroup?.publisher || STRINGS.DASH,
      _isNew: isWithinOneMonth(updateDate) && (modelGroup?.is_new || false),
      updateTime: testTime || updateDate || STRINGS.DASH,
    };
    // 使用后端返回的外层 score 作为均分
    row._avg = matchedResult.score != null ? matchedResult.score : null;
    const triMap = {};
    // aisf_llm_skilltican：把后端子集名（skill提参/宽松通过率）统一映射为列 key（宽松通过率）
    const nameMap =
      label === "aisf_llm_skilltican" ? SKILLTICAN_SUBSET_MAP : null;
    subsets.forEach((sub) => {
      const subName = (nameMap && nameMap[sub.name]) || sub.name;
      if (sub.tri_subsets && sub.tri_subsets.length > 0) {
        triMap[subName] = sub.tri_subsets;
      }
      if (sub.subsets && sub.subsets.length > 0) {
        // 有三级子场景（如伴学）
        // 组均分用 _avg_组名 存储
        row[`_avg_${subName}`] = sub.score;
        row[subName] = sub.score;
        // 存储三级子场景数据
        triMap[subName] = [sub];
        // 三级子场景分数直接存储到 row
        sub.subsets.forEach((s3) => {
          row[s3.name] = s3.score;
        });
      } else {
        row[subName] = sub.score;
      }
    });
    row._triMap = triMap;
    row._triSubsets = null;
    rows.push(row);
  });
  // 默认按均分降序排列
  rows.sort((a, b) => {
    const avgA = a._avg != null ? a._avg : -1;
    const avgB = b._avg != null ? b._avg : -1;
    return avgB - avgA;
  });
  // 伴学按"注意力检测"组均分排定名次
  if (label === "aisf_banxue") {
    rows.sort((a, b) => {
      const avgA = a["_avg_注意力检测"] != null ? a["_avg_注意力检测"] : -1;
      const avgB = b["_avg_注意力检测"] != null ? b["_avg_注意力检测"] : -1;
      return avgB - avgA;
    });
    rows.forEach((row, i) => {
      row._banxueRank = i + 1;
    });
  }
  // 记忆按总体均分排定名次（已在默认排序中）
  return rows;
}

const currentRuler2Data = computed(() => {
  const cat = activeRuler2Category.value;
  let data;
  if (cat === "aisf") {
    const subKey = currentRuler2SubKey.value;
    if (!subKey) return [];
    if (subKey === "aisf_llm_gaixie")
      data = processRuler2StoreData(ruler2Gaixie.value, subKey);
    else if (subKey === "aisf_llm_yitu")
      data = processRuler2StoreData(ruler2Yitu.value, subKey);
    else if (subKey === "aisf_banxue")
      data = processMultiRuler2Data(_multiRuler2Raw.value, "aisf_banxue");
    else if (subKey === "aisf_memory_cuiqu")
      data = processMultiRuler2Data(
        _currentFullRuler2Raw.value,
        "aisf_memory_cuiqu"
      );
    else if (subKey === "aisf_memory_zhaohui")
      data = processMultiRuler2Data(
        _currentFullRuler2Raw.value,
        "aisf_memory_zhaohui"
      );
    else if (subKey === "aisf_gui_plan")
      data = processMultiRuler2Data(_multiRuler2Raw.value, "aisf_gui_plan");
    else if (subKey === "aisf_gui_vla")
      data = processMultiRuler2Data(_multiRuler2Raw.value, "aisf_gui_vla");
    else if (subKey === "aisf_llm_skilltican")
      data = processMultiRuler2Data(
        _currentFullRuler2Raw.value,
        "aisf_llm_skilltican"
      );
    else if (subKey === "aisf_llm_guican")
      data = processMultiRuler2Data(
        _currentFullRuler2Raw.value,
        "aisf_llm_guican"
      );
    else if (subKey === "aisf_llm_banxue")
      data = processMultiRuler2Data(
        _currentFullRuler2Raw.value,
        "aisf_llm_banxue"
      );
    else if (subKey === "aisf_llm_coordinator")
      data = processMultiRuler2Data(
        _currentFullRuler2Raw.value,
        "aisf_llm_coordinator"
      );
    else return [];
  } else return [];
  // 应用列排序（如果用户点击了排序列头）
  if (sortState.value.key && sortState.value.order) {
    return applySort(data, sortState.value.key);
  }
  return data;
});

// 当前尺子二榜单的最新测评时间
const currentRuler2UpdateTime = computed(() => {
  const times = currentRuler2Data.value
    .map((row) => row.updateTime)
    .filter((t) => t && t !== STRINGS.DASH)
    .map((t) => new Date(t).getTime())
    .filter((t) => !Number.isNaN(t));
  if (times.length === 0) return "";
  const latest = new Date(Math.max(...times));
  const month = String(latest.getMonth() + 1).padStart(2, "0");
  const day = String(latest.getDate()).padStart(2, "0");
  return `测评时间 ${latest.getFullYear()}-${month}-${day}`;
});

const ruler2ColumnKeys = computed(() => {
  const keys = currentRuler2Columns.value.map((c) => c.key);
  // 伴学：添加组均分 key 和子列 key
  const bg = banxueGroupColumns.value;
  if (bg.length > 0) {
    bg.forEach((g) => {
      keys.push(`_avg_${g.key}`);
      g.children.forEach((c) => {
        if (!keys.includes(c.key)) keys.push(c.key);
      });
    });
  }
  return keys;
});

const ruler2MaxScores = computed(() =>
  calcColumnMax(currentRuler2Data.value, ruler2ColumnKeys.value)
);

const currentRuler2Columns = computed(() => {
  const cat = activeRuler2Category.value;
  if (cat === "aisf") {
    const subKey = currentRuler2SubKey.value;
    if (!subKey) return [];
    const labels = RULER2_COLUMN_LABELS[subKey] || {};
    return Object.entries(labels).map(([k, v]) => ({ key: k, label: v }));
  }
  return [];
});

// 伴学/记忆特有：从对应数据源中提取组列和子列配置
const banxueGroupColumns = computed(() => {
  const groups = [];
  const dsName = currentRuler2SubKey.value;

  if (!dsName) return [];

  // 根据子类选择数据源
  const source =
    dsName === "aisf_memory_cuiqu" || dsName === "aisf_memory_zhaohui"
      ? _currentFullRuler2Raw.value
      : _multiRuler2Raw.value;

  const entries = Object.entries(source).filter((item) => {
    return item[1].result.some((res) => res.dataset_name === dsName);
  });

  if (entries.length === 0) return [];

  // 提取所有匹配的 result
  const allMatchedResults = entries.flatMap(([key, value]) =>
    value.result.filter((res) => res.dataset_name === dsName)
  );

  if (allMatchedResults.length === 0) return [];

  // 提取所有 metrics 中的 subsets
  const allSubsets = allMatchedResults
    .flatMap((res) => res.metrics || [])
    .flatMap((metric) => metric.categories || [])
    .flatMap((category) => category.subsets || []);

  // 去重处理（根据 name）
  const uniqueSubsets = Array.from(new Set(allSubsets.map((s) => s.name))).map(
    (name) => allSubsets.find((s) => s.name === name)
  );

  // 构建 groups
  uniqueSubsets.forEach((sub) => {
    if (sub.subsets && sub.subsets.length > 0) {
      const children = [
        // 均分放在首位
        { key: `_avg_${sub.name}`, label: "均分" },
        ...sub.subsets.map((s3) => ({ key: s3.name, label: s3.name })),
      ];
      groups.push({
        key: sub.name,
        label: sub.name,
        children,
      });
    }
  });

  console.log("groups", groups);
  return groups;
});

const ruler2ModelMinWidth = computed(() => {
  const data = currentRuler2Data.value;
  return calcModelMinWidth(data);
});

// 当前尺子二榜单名称（用于导出文件名）
const currentRuler2SubLabel = computed(() => {
  const subKey = currentRuler2SubKey.value;
  if (!subKey) return "榜单";
  const subs = currentRuler2Subs.value || [];
  return subs.find((s) => s.key === subKey)?.label || subKey;
});

// ============= Excel 导出 =============
// 将内部 0~1 的分数转换为展示用的百分制数值（保留 1 位小数）
function toExportScore(value) {
  if (value == null || value === -1) return "-";
  const num = parseFloat(value);
  if (Number.isNaN(num)) return "-";
  return Number((num * 100).toFixed(1));
}

function exportTimestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
}

function sanitizeFileName(name) {
  return String(name).replace(/[\\/:*?"<>|]/g, "_");
}

function downloadExcel(rows, sheetName, fileName) {
  if (!rows || rows.length === 0) {
    ElMessage.warning("当前榜单暂无可导出的数据");
    return;
  }
  const worksheet = XLSX.utils.json_to_sheet(rows);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, sheetName);
  const excelBuffer = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
  const blob = new Blob([excelBuffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  saveAs(blob, `${sanitizeFileName(fileName)}_${exportTimestamp()}.xlsx`);
  ElMessage.success("Excel 导出成功");
}

// 尺子一：导出当前模态榜单
function exportRuler1Excel() {
  const modalityLabel =
    RULER1_MODALITIES.find((m) => m.key === activeRuler1Modality.value)?.label ||
    "榜单";
  const datasets = currentRuler1Datasets.value;
  const rows = currentRuler1Sorted.value.map((row) => {
    const item = {
      名次: row._isPending ? "-" : row._computedRank,
      模型: row.name,
      厂商: row.publisher,
      均分: toExportScore(row._avg),
    };
    datasets.forEach((ds) => {
      item[`${ds.label}-实测`] = toExportScore(row[ds.key]);
      item[`${ds.label}-官方`] = toExportScore(row[ds.key + "_official"]);
      item[`${ds.label}-差值`] = computeDiff(
        row[ds.key],
        row[ds.key + "_official"]
      );
    });
    item["评测时间"] = row._updateTimeLabel || row.updateTime || "-";
    return item;
  });
  downloadExcel(rows, "尺子一", `尺子一_${modalityLabel}_榜单`);
}

// 从 _triMap 中提取某列的展开子项（兼容三级子场景结构）
function getTriEntries(row, colKey) {
  const arr = row?._triMap?.[colKey] || [];
  const entries = [];
  arr.forEach((s) => {
    if (Array.isArray(s.subsets) && s.subsets.length > 0) {
      s.subsets.forEach((s3) => entries.push({ name: s3.name, score: s3.score }));
    } else {
      entries.push({ name: s.name, score: s.score });
    }
  });
  return entries;
}

// 尺子二：导出当前子榜单
function exportRuler2Excel() {
  const subKey = currentRuler2SubKey.value;
  if (!subKey) {
    ElMessage.warning("当前榜单暂无可导出的数据");
    return;
  }
  const isBanxue = subKey === "aisf_banxue";
  const data = currentRuler2Data.value;
  const columns = currentRuler2Columns.value;

  // 非伴学榜单：收集所有展开子项，作为附加列导出
  const triColumns = [];
  if (!isBanxue) {
    const seen = new Set();
    data.forEach((row) => {
      columns.forEach((col) => {
        getTriEntries(row, col.key).forEach((entry) => {
          const key = `${col.key}__${entry.name}`;
          if (!seen.has(key)) {
            seen.add(key);
            triColumns.push({ colKey: col.key, colLabel: col.label, name: entry.name });
          }
        });
      });
    });
  }

  const rows = data.map((row, index) => {
    const item = {
      名次: row._banxueRank != null ? row._banxueRank : index + 1,
      模型: row.name,
      厂商: row.publisher,
    };
    if (isBanxue) {
      banxueGroupColumns.value.forEach((group) => {
        group.children.forEach((child) => {
          item[`${group.label}-${child.label}`] = toExportScore(row[child.key]);
        });
      });
    } else {
      item["均分"] = toExportScore(row._avg);
      columns.forEach((col) => {
        item[col.label] = toExportScore(row[col.key]);
      });
      triColumns.forEach((tri) => {
        const entry = getTriEntries(row, tri.colKey).find(
          (e) => e.name === tri.name
        );
        item[`${tri.colLabel}-${tri.name}`] = toExportScore(entry?.score);
      });
    }
    item["测评时间"] = row.updateTime || "-";
    return item;
  });

  downloadExcel(
    rows,
    "尺子二",
    `尺子二_${currentRuler2SubLabel.value}_榜单`
  );
}

// 模型竞技场（LMArena）：导出榜单数据
function exportArenaExcel() {
  const rows = modelEArenaTableData.value.map((row, index) => ({
    序号: index + 1,
    模型: row.model_name,
    厂商: row.organization,
    "开源/闭源": row.is_open,
    Elo分数: row.eloScore,
    投票数: row.votes,
    时间: row.time,
  }));
  downloadExcel(rows, "LMArena", "模型竞技场_LMArena_榜单");
}

// ============= Expand for tri_subsets =============
const expandedRowKeys = ref([]);

function isExpandedFor(row, colKey) {
  return expandedRowKeys.value.includes(`${row._uid}_${colKey}`);
}

function toggleExpand(row, colKey) {
  const key = `${row._uid}_${colKey}`;
  if (expandedRowKeys.value.includes(key)) {
    expandedRowKeys.value = expandedRowKeys.value.filter((k) => k !== key);
    row._triSubsets = null;
  } else {
    expandedRowKeys.value = [key];
    row._triSubsets = row._triMap[colKey] || [];
  }
}

function onExpandChange(row, expandedRows) {
  // Element Plus: if expandedRows is empty, row was collapsed
  if (!expandedRows || expandedRows.length === 0) {
    row._triSubsets = null;
  }
}

// 切换标签或子类别时重置排序
function resetSort() {
  sortState.value = { key: null, order: null };
}

// 监听子类切换，重置排序状态
watch(currentRuler2SubKey, () => {
  resetSort();
});
watch(activeRuler2Category, () => {
  resetSort();
});

// ============= Data Loading =============
const rankingStore = useRankingStore();

function computeUpdateTime(rawObj) {
  const arr = Object.values(rawObj);
  if (arr.length === 0) return "";
  arr.sort((a, b) => new Date(b.update_date) - new Date(a.update_date));
  return arr[0]?.update_date || "";
}

function filterModelsByDatasets(rawObj, datasetKeys) {
  const result = {};
  Object.entries(rawObj).forEach(([modelName, modelGroup]) => {
    if (
      (modelGroup?.result || []).some((item) =>
        datasetKeys.includes(item.dataset_name)
      )
    ) {
      result[modelName] = modelGroup;
    }
  });
  return result;
}

const loadData = async () => {
  try {
    const { getCurrentFullRes } = await import("@/api/dataService.js");
    const [llmRes,multiRes,evalRes] = await Promise.all([getCurrentFullRes(),getMultiModelData(),getEvaluationResult()]);
    rankingStore.processRawData(llmRes.data);
    const llmData = llmRes.data?.ruler1 || {};
    llmRawData.value = llmData;
    _currentFullRuler2Raw.value = llmRes.data?.ruler2 || {};
    llmUpdateTime.value = computeUpdateTime(llmData);

    const multiData = multiRes.data;

    const multiR1 = multiData.ruler1 || {};
    multiRawRuler1.value = multiR1;

    // ruler1 数据已就绪，计算 modelMinWidth
    computeModelMinWidth();
    // 等 DOM 更新后再解除 loading，避免表格列宽闪烁
    await nextTick();
    isLoading.value = false;

    const visionRaw = filterModelsByDatasets(multiR1, VISION_DATASET_KEYS);
    visionUpdateTime.value = computeUpdateTime(visionRaw);

    const audioRaw = filterModelsByDatasets(multiR1, AUDIO_DATASET_KEYS);
    audioUpdateTime.value = computeUpdateTime(audioRaw);

    // Agent 数据来自 ruler1_cheat.json（get_current_full_res），格式与 LLM 相同
    const agentRaw = filterModelsByDatasets(
      llmData,
      AGENT_DATASETS.map((d) => d.key)
    );
    agentUpdateTime.value = computeUpdateTime(agentRaw);

    _multiRuler2Raw.value = multiData.ruler2 || {};

    ruler2Gaixie.value = rankingStore.ruler2Values.aisf_llm_gaixie || [];
    ruler2Yitu.value = rankingStore.ruler2Values.aisf_llm_yitu || [];

    // 预取测评任务列表，构建查询表
    const taskList = Array.isArray(evalRes.data)
      ? evalRes.data
      : Object.values(evalRes.data);
    const map = new Map();
    taskList.forEach((task) => {
      map.set(`${task.model_id}__${task.dataset}`, task);
    });
    evaluationTaskMap.value = map;
  } catch (error) {
    console.error("Error fetching ranking data:", error);
    // 加载失败也要解除加载状态
    isLoading.value = false;
  }
};

// ============= Tab Handlers =============
const tabClick = (tab) => {
  updateTab(tab);
  disableSlide.value = true;
  setTimeout(() => {
    disableSlide.value = false;
  }, 1);
};
const updateTab = (newTab) => {
  store.dispatch("rankingScore/updateActiveTab", newTab.props.name);
};

const handleClickName = (row) => {
  // 传入当前所处 tab 和子类信息，供 modelCompareTab 决定默认展示哪个 tab
  const query = { modelName: row.name };
  if (activeTab.value === "ruler1") {
    // 尺子一：记录当前模态（llm/vision/audio）
    query.fromTab = "ruler1";
    query.fromModality = activeRuler1Modality.value;
  } else if (activeTab.value === "ruler2") {
    // 尺子二：记录当前子类别（如 aisf_llm_gaixie）
    query.fromTab = "ruler2";
    query.fromSubKey = currentRuler2SubKey.value || "";
  }
  router.push({
    path: "/rankingScore/ModelComparison",
    query,
  });
};

// 点击测试集名称 -> 跳转到该测试集下各模型分数对比页
function goDatasetComparison(item) {
  if (activeTab.value === "ruler1") {
    router.push({
      path: "/rankingScore/DatasetComparison",
      query: {
        fromTab: "ruler1",
        datasetKey: item.key,
        displayName: item.label,
      },
    });
  } else {
    // 尺子二：同一测试集在榜单上可能是多个独立子榜单（记忆/GUI），合并为一页展示
    const subKey = currentRuler2SubKey.value;
    const scenes = SCENE_GROUPS[subKey] || [subKey];
    router.push({
      path: "/rankingScore/DatasetComparison",
      query: {
        fromTab: "ruler2",
        scenes: scenes.join(","),
      },
    });
  }
}

function navigateToTask(task, row, datasetKey) {
  const displayedScore = row[datasetKey];
  const taskScore = task.score;
  // if (
  //   displayedScore != null &&
  //   taskScore != null &&
  //   Math.abs(displayedScore - taskScore) > 1e-9
  // ) {
  //   ElMessage({
  //     type: "warning",
  //     message: "分数与当前存在结果数据不一致",
  //   });
  // }
  router.push({
    name: "resultDetail",
    query: {
      taskId: task.task_id,
      model_name: task.model_name,
      dataset: task.task_dataset,
      score: task.score,
      assessmentType: task.assessmentType,
    },
  });
}

function getDatasetWikiUrl(datasetKey, subCategoryKey) {
  // Ruler1 数据集 → 跳转到对应测试集锚点
  const allDatasets = [
    ...LLM_DATASETS,
    ...LLM_TEMP_DATASETS,
    ...VISION_DATASETS,
    ...VISION_TEMP_DATASETS,
    ...AUDIO_DATASETS,
  ];
  const ds = allDatasets.find((d) => d.key === datasetKey);
  if (ds) return `${WIKI_BASE_URL}?title=${encodeURIComponent(ds.label)}`;
  // Ruler2 场景列 → 根据子类别映射到对应锚点
  if (subCategoryKey === "aisf_llm_gaixie")
    return `${WIKI_BASE_URL}?title=${encodeURIComponent("AISF-Query改写")}`;
  if (subCategoryKey === "aisf_llm_yitu")
    return `${WIKI_BASE_URL}?title=${encodeURIComponent("AISF-意图")}`;
  if (
    subCategoryKey === "aisf_memory_cuiqu" ||
    subCategoryKey === "aisf_memory_zhaohui"
  )
    return `${WIKI_BASE_URL}?title=${encodeURIComponent("AISF-记忆")}`;
  if (subCategoryKey === "aisf_gui_plan" || subCategoryKey === "aisf_gui_vla")
    return `${WIKI_BASE_URL}?title=${encodeURIComponent(
      "AISF-GUI操控规划-执行"
    )}`;
  if (
    subCategoryKey === "aisf_banxue" ||
    subCategoryKey === "aisf_llm_banxue"
  )
    return `${WIKI_BASE_URL}?title=${encodeURIComponent("AISF-伴学智能体")}`;
  if (subCategoryKey === "aisf_llm_coordinator")
    return `${WIKI_BASE_URL}?title=${encodeURIComponent("AISF-Coordinator")}`;
  return WIKI_BASE_URL;
}

function getAverageScoreWikiUrl() {
  if (activeTab.value === "ruler1") {
    return `${WIKI_BASE_URL}?title=${encodeURIComponent("均分计算方式")}`;
  }
  const subKey = currentRuler2SubKey.value;
  if (subKey === "aisf_llm_gaixie")
    return `${WIKI_BASE_URL}?title=${encodeURIComponent("AISF-Query改写-")}`;
  if (subKey === "aisf_llm_yitu")
    return `${WIKI_BASE_URL}?title=${encodeURIComponent("AISF-意图-")}`;
  if (subKey === "aisf_memory_cuiqu" || subKey === "aisf_memory_zhaohui")
    return `${WIKI_BASE_URL}?title=${encodeURIComponent("AISF-记忆-")}`;
  if (subKey === "aisf_banxue" || subKey === "aisf_llm_banxue")
    return `${WIKI_BASE_URL}?title=${encodeURIComponent("AISF-伴学智能体")}`;
  if (subKey === "aisf_gui_plan" || subKey === "aisf_gui_vla")
    return `${WIKI_BASE_URL}?title=${encodeURIComponent(
      "AISF-GUI操控规划---操控执行"
    )}`;
  return WIKI_BASE_URL;
}

const handleScoreClick = (row, datasetKey) => {
  // 意图场景：无论点击哪个子场景分数，都跳转到 dataset === '意图' 的结果
  if (currentRuler2SubKey.value === "aisf_llm_yitu") {
    const rowNameNorm = normalizeMatch(row.name);
    for (const [key, task] of evaluationTaskMap.value.entries()) {
      const [modelId, dataset] = key.split("__");
      if (dataset === "意图" && normalizeMatch(modelId).includes(rowNameNorm)) {
        navigateToTask(task, row, datasetKey);
        return;
      }
    }
    console.warn(`No matching task found for model: ${row.name}, dataset:意图`);
    return;
  } else if (
    currentRuler2SubKey.value === "aisf_memory_cuiqu" ||
    currentRuler2SubKey.value === "aisf_memory_zhaohui"
  ) {
    const rowNameNorm = normalizeMatch(row.name);
    for (const [key, task] of evaluationTaskMap.value.entries()) {
      const [modelId, dataset] = key.split("__");
      if (
        dataset.includes(datasetKey) &&
        normalizeMatch(modelId).includes(rowNameNorm)
      ) {
        navigateToTask(task, row, datasetKey);
        return;
      }
    }
    console.warn(`No matching task found for model: ${row.name}, dataset:${datasetKey}`);
    return;
  }
  // 改写场景：通过 dataset 映射匹配 evaluation result 中的 dataset 字段值
  if (currentRuler2SubKey.value === "aisf_llm_gaixie") {
    const rowNameNorm = normalizeMatch(row.name);
    const evalDataset = GAIXIE_DATASET_MAP[datasetKey];
    if (!evalDataset) {
      console.warn(`No dataset mapping for key: ${datasetKey}`);
      return;
    }
    // 中文数据集名使用精确匹配
    for (const [key, task] of evaluationTaskMap.value.entries()) {
      const [modelId, dataset] = key.split("__");
      if (
        dataset === evalDataset &&
        normalizeMatch(modelId).includes(rowNameNorm)
      ) {
        navigateToTask(task, row, datasetKey);
        return;
      }
    }
    console.warn(
      `No matching task found for model: ${row.name}, dataset:${evalDataset}`
    );
    return;
  }
  const rowNameNorm = normalizeMatch(row.name);
  const dsKeyNorm = normalizeMatch(datasetKey);
  for (const [key, task] of evaluationTaskMap.value.entries()) {
    const [modelId, dataset] = key.split("__");
    if (
      normalizeMatch(dataset) === dsKeyNorm &&
      normalizeMatch(modelId).includes(rowNameNorm)
    ) {
      navigateToTask(task, row, datasetKey);
      return; // 找到第一个匹配项后退出
    }
  }
  // 如果没有找到匹配项，可以添加提示逻辑
  console.warn(
    `No matching task found for model: ${row.name}, dataset:${datasetKey}`
  );
};

const calcAverageContent = (scene) => {
  if (
    scene === "aisf_llm_gaixie" ||
    scene === "aisf_memory_cuiqu" ||
    scene === "aisf_memory_zhaohui"
  ) {
    return "均分计算公式，各测试集实测分数取平均";
  } else if (
    scene === "aisf_gui_plan" ||
    scene === "aisf_gui_vla" ||
    scene === "aisf_llm_yitu"
  ) {
    return "sum(所有子集正确数量)/sum(所有子集的数量)";
  }
};

// ============= Arena Chart Data (unchanged) =============
const modelEArenaChartData = ref([]);
const modelEArenaTableData = ref([]);
const timeList = ref([]);
const scoreList = ref([]);
const arenaModels = ref([]);
const multiScatterChartTitle = ref("基于 ChatBot Arena 对战 Elo 分数趋势图");
const arenaModelsNum = "模型数量";
const arenaModelsUpdatePeriod = "原始历史快照，非实时排名";

function getLmArenaUpdateDate() {
  const now = new Date();
  if (now.getHours() < 23) {
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const yYear = yesterday.getFullYear();
    const yMonth = String(yesterday.getMonth() + 1).padStart(2, "0");
    const yDay = String(yesterday.getDate()).padStart(2, "0");
    return `更新时间 ${yYear}-${yMonth}-${yDay}`;
  } else {
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `更新时间 ${year}-${month}-${day}`;
  }
}
const arenaModelsDate = ref("历史榜单");
const arenaModelsSpeakerTitle = ref(
  "本次重点更新gpt-5.5、mimo-v2.5pro、deepseek-v4系列"
);

function dateStrToExcelSerial(dateStr) {
  if (!dateStr) return 0;
  const parts = dateStr.split(/[/-]/);
  if (parts.length !== 3) return 0;
  const date = new Date(+parts[0], +parts[1] - 1, +parts[2]);
  const epoch = new Date(1900, 0, 1);
  const diff = date.getTime() - epoch.getTime();
  return Math.floor(diff / (1000 * 60 * 60 * 24)) + 2;
}

const loadArenaExcel = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}lmarena/leaderboard`);
    const data = response.data;
    modelEArenaTableData.value = [];
    arenaModels.value = [];
    const processedData = [];
    for (const row of data) {
      const excelTime = dateStrToExcelSerial(row.time);
      const name = row.model_name || row.model || "";
      const score = row.elo || 0;
      const votes = row.votes || "-";
      const organization = row.organization || "-";
      const type = row["closed/open"] === "open" ? "开源" : "闭源";
      if (excelTime && name && score !== null) {
        processedData.push([excelTime, score, name, type]);
      }
      modelEArenaTableData.value.push({
        time: row.time,
        model_name: name,
        eloScore: score,
        votes: votes,
        organization: organization,
        is_open: type,
      });
      if (!arenaModels.value.includes(name)) {
        arenaModels.value.push(name);
      }
    }
    modelEArenaChartData.value = processedData;
  } catch (error) {
    console.error("获取LM Arena排行榜数据失败:", error);
  }
};

const checkScreenWidth = () => {};

useReadUpdates(["/v1/get_current_full_res","/v1/get_current_multi_full_res","/v1/get_evaluation_result"],loadData);
useReadUpdates(['/v1/lmarena/leaderboard'],loadArenaExcel);
onMounted(async () => {
  // 先读取路由参数，在数据加载前设置 tab 和模态，避免首次渲染闪动
  const fromTab = route.query.fromTab as string;
  const fromModality = route.query.fromModality as string;
  const fromSubKey = route.query.fromSubKey as string;
  if (fromTab) {
    store.dispatch("rankingScore/updateActiveTab", fromTab);
  }
  if (fromTab === "ruler1" && fromModality) {
    activeRuler1Modality.value = fromModality;
  } else if (fromTab === "ruler2") {
    if (fromSubKey) {
      activeRuler2SubCategory.value = fromSubKey;
    } else {
      const subs = currentRuler2Subs.value;
      if (subs && subs.length > 0) {
        const first = subs[0];
        activeRuler2SubCategory.value = first.children
          ? first.children[0]?.key || first.key
          : first.key;
      }
    }
  }
  await Promise.all([loadData(),loadArenaExcel()]);
  checkScreenWidth();
  window.addEventListener("resize", checkScreenWidth);
  setTimeout(() => {
    disableSlide.value = false;
  }, 1);
});
onBeforeUnmount(() => {
  window.removeEventListener("resize", checkScreenWidth);
});
</script>

<style scoped>
.tabsContainer :deep(.el-tabs__header) {
  margin-left: 20px;
}
.tabsContainer :deep(.el-tabs__item) {
  font-size: 18px;
  z-index: 1;
  padding: 0 28px;
  line-height: 56px;
  height: 56px;
}
.insideContainer {
  display: flex;
  max-width: 100%;
  /* margin: 0px 20px 0px 10px; */
  gap: 10px;
  position: relative;
  flex-direction: column;
}
.rankingTable {
  background-color: #fff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  border: 1px solid #d7d8dd;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 表格不再自动占满容器宽度，允许留白 */
.modelTableFull {
  font-size: 14px;
  table-layout: auto;
  width: auto;
  min-width: 0;
  max-width: 100%;
}
.modelTableFull :deep(.el-table__row) {
  height: 48px;
}
.modelTableFull :deep(td.el-table__cell),
.modelTableFull :deep(th.el-table__cell.is-leaf) {
  border-bottom: 1px solid var(--line-1, #faf5f9) !important;
}
.modelTableFull :deep(th) {
  font-size: 14px;
  height: 32px !important;
}
.modelTableFull :deep(.cell) {
  padding: 0 5px;
  overflow: unset;
  max-height: 45px;
}
.modelTableFull :deep(.el-table__inner-wrapper:before) {
  background-color: #fff;
}
/* 评测中行样式 - 浅黄色背景 */
.modelTableFull :deep(.pending-row) {
  background-color: #fffde7 !important;
}
/* 临时测试集列（尚未完成测评）- 整列淡黄色背景，与评测中行背景一致 */
.modelTableFull :deep(th.temp-dataset-column),
.modelTableFull :deep(td.temp-dataset-column) {
  background-color: #fffde7 !important;
}

/* 数据集列组之间的分隔竖线 */
/* 组头（dataset-column-group）右侧加竖线 */
.modelTableFull :deep(th.dataset-column-group) {
  border-right: 1px solid #e0e0e0 !important;
}
/* 数据行中每个子列组的最后一列（diff-column）右侧加竖线 */
.modelTableFull :deep(td.diff-column) {
  border-right: 1px solid #e0e0e0 !important;
}
/* 均分列与数据集列之间的竖线 */
.modelTableFull :deep(.el-table__header-wrapper th:nth-child(4)) {
  border-left: 1px solid #e0e0e0 !important;
}

/* 测试集名称列头：名称可点击跳转，右侧排序箭头三态切换 */
.sortable-header {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  cursor: pointer;
}
.ds-name {
  cursor: pointer;
  white-space: nowrap;
}
.ds-name:hover {
  color: #1b3882;
  text-decoration: underline;
}
.sort-arrow {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  color: #c0c4cc;
  transition: color 0.15s;
}
.sort-arrow:hover {
  color: #1b3882;
}
.sort-arrow.active {
  color: #1b3882;
}

.headerContainer {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 10px;
  background: linear-gradient(90deg, #5878b4 0%, #6bbafa 100%);
}
.headerRow1 {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.headerRow2 {
  display: flex;
  align-items: center;
  margin-left: 30px;
}
.guide-link {
  font-size: 12px;
  color: #fff;
  /* text-decoration: underline; */
}
.titleText {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  margin-left: 30px;
}
.updateTimeText {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}
.export-btn {
  margin-left: 4px;
  background-color: #ffffff;
  border-color: #ffffff;
  color: #1b3882;
  font-weight: 600;
}
.export-btn:hover,
.export-btn:focus {
  background-color: #eaf1ff;
  border-color: #eaf1ff;
  color: #1b3882;
}
.statistic_1mafc {
  display: flex;
  align-items: center;
  position: relative;
  flex-wrap: wrap;
  column-gap: 16px;
  row-gap: 4px;
  justify-content: right;
  z-index: 2;
  color: var(---fill-0, #fff);
  font-weight: 400;
  line-height: 24px;
  margin-left: auto;
  margin-right: 30px;
}
.divider_1mafc {
  width: 1px;
  height: 16px;
  background: var(--40-text-dark-3, rgba(255, 255, 255, 0.4));
}
/* 提示栏 */
.hint-bar {
  /* display: flex; */
  /* align-items: center; */
  gap: 8px;
  padding: 4px 16px;
  font-size: 12px;
  color: #888;
  /* background: #fafafa; */
  border-bottom: 1px solid #eee;
}
.hint-text {
  font-size: 12px;
  color: #000;
}
.hint-divider {
  color: #ddd;
}
.nameAndScore {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(18, 19, 22, 0.6);
  font-size: 10px;
  font-weight: 400;
  line-height: 16px;
  white-space: nowrap;
  width: auto;
}
.model-name {
  font-size: 16px;
  font-family: Helvetica Neue For Number, -apple-system, BlinkMacSystemFont,
    Segoe UI, Roboto, PingFang SC, Hiragino Sans GB, Microsoft YaHei,
    Helvetica Neue, Helvetica, Arial, sans-serif;
  cursor: pointer;
  margin-right: 20px;
}
.newrank {
  width: 30px;
  font-size: 10px;
  line-height: 10px;
  margin-top: 2px;
  text-align: center;
  font-weight: 600;
  border-radius: 2px;
  background: #e3f9ec;
  padding: 2px 3px;
  color: #18b25c;
  font-family: "Arial Black", "Impact", sans-serif;
  font-style: oblique;
}
.publisherTag {
  display: inline-block;
  font-size: 10px;
  color: rgba(18, 19, 22, 0.6);
}
.low-style {
  color: var(--100-text-5, #121316);
  font-size: 16px;
  font-weight: 700;
}
/* 每列最高分标红加粗，淡灰色底色 */
.highest-score {
  color: #d32f2f !important;
  font-weight: 700 !important;
}
/* 最高分单元格的背景色 */
.modelTableFull :deep(td) .highest-score {
  background-color: #f0f0f0;
  padding: 2px 6px;
  border-radius: 2px;
  display: inline-block;
}

/* 隐藏尺子二表格的展开列（>箭头） */
.modelTableFull :deep(.el-table__expand-column .el-table__expand-icon) {
  display: none !important;
}

/* Ruler2 一级标签切换 */
.ruler2-tabs {
  display: flex;
  gap: 0;
  margin-left: 30px;
  flex-wrap: wrap;
}
.ruler2-tab {
  padding: 4px 16px;
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.75);
  cursor: pointer;
  border-radius: 4px 4px 0 0;
  transition: all 0.2s;
  user-select: none;
}
.ruler2-tab:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.15);
}
.ruler2-tab.active {
  color: #fff;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.25);
}

/* Ruler2 二级目录标签 */
.ruler2-sub-tabs-container {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  padding: 4px 10px;
  background: #e8ecf4;
  border-bottom: 1px solid #d7d8dd;
}
.ruler2-sub-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
}
.ruler2-sub-group + .ruler2-sub-group::before {
  content: "|";
  color: #b0b8c8;
  margin-right: 8px;
}
.ruler2-sub-tab {
  padding: 2px 10px;
  font-size: 13px;
  cursor: pointer;
  border-radius: 3px;
  user-select: none;
  transition: all 0.15s;
  white-space: nowrap;
}
.ruler2-primary-sub {
  color: #1b3882;
  font-weight: 600;
}
.ruler2-primary-sub:hover {
  background: rgba(27, 56, 130, 0.08);
}
.ruler2-primary-sub.active {
  background: rgba(27, 56, 130, 0.15);
  text-decoration: underline;
}
.ruler2-secondary-sub {
  color: #555;
  font-weight: 400;
}
.ruler2-secondary-sub:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #333;
}
.ruler2-secondary-sub.active {
  background: #1b3882;
  color: #fff;
  font-weight: 500;
}
.ruler2-sub-children {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 2px;
  align-items: center;
}

/* 展开按钮 */
.table-cell-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.expand-btn {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
}
.expand-icon {
  width: 14px;
  height: 14px;
}

/* 展开行 */
.expanded-row-container {
  margin: 10px 20px;
  display: table !important;
  width: 100%;
}
.custom-score-table {
  border-collapse: collapse;
  table-layout: auto;
  width: fit-content;
  background: transparent;
}
.custom-score-table th,
.custom-score-table td {
  text-align: left;
  border: none;
}
.custom-score-table th {
  color: #000;
  background-color: #fff;
  font-weight: normal;
  white-space: nowrap;
}
.custom-score-table td {
  background-color: #f4f3f9;
}
:deep(.el-table__expanded-cell) {
  background-color: #f4f3f9 !important;
}

/* 展开的子组样式（伴学3级子场景） */
.expanded-sub-group {
  margin-bottom: 12px;
}
.expanded-sub-group:last-child {
  margin-bottom: 0;
}
.expanded-group-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 6px;
}
.expanded-group-score {
  font-weight: 400;
  font-size: 12px;
  color: #666;
  margin-left: 8px;
}

/* 伴学子列之间的分隔竖线 */
.modelTableFull :deep(th.banxue-sub-column) {
  border-right: 1px solid #e0e0e0 !important;
}
.modelTableFull :deep(th.banxue-sub-column:last-child) {
  border-right: none !important;
}

/* 分数可点击样式 */
.score-clickable {
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
  text-underline-offset: 2px;
}
.score-clickable:hover {
  color: #1b3882 !important;
  opacity: 0.8;
}

/* 可排序列头样式 */
.sortable-header {
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}
.sortable-header:hover {
  color: #1b3882;
}

/* Arena chart styles (unchanged) */
.chartContainer {
  position: relative;
  background-color: #fff;
  height: calc(100vh - 150px);
  min-height: 400px;
  box-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
}
.arena-export-btn {
  position: absolute;
  top: 12px;
  right: 20px;
  z-index: 2;
}
.toDetail {
  position: absolute;
  display: block;
  margin-top: 10px;
  width: 100%;
  height: 40px;
  bottom: 0;
  left: 50%;
  text-align: center;
  text-decoration: underline;
  font-size: 14px;
  font-weight: 400;
  line-height: 24px;
  cursor: pointer;
  padding: 8px 0;
  transform: translateX(-50%);
  border: none;
  background: var(--Brand1-1, #f5f6fd);
  color: var(--Brand1-6, #1b3882);
  z-index: 1;
}
.charDesc {
  top: 5px;
  position: absolute;
  z-index: 1;
  color: #606060;
}
.updateTime {
  left: 180px;
  width: 100px;
  height: 20px;
  text-align: center;
}
.updatePeriod {
  left: 100px;
  width: 80px;
  height: 20px;
  text-align: center;
}
.modelNumber {
  left: 0;
  width: 100px;
  height: 20px;
  text-align: center;
}
.speakerTitle {
  max-width: 500px;
  height: 20px;
  right: 50px;
  font-size: 14px;
  display: flex;
  flex-direction: row;
  justify-content: stretch;
  gap: 4px;
}
.speakerTitle > p {
  flex: 1 1 0;
  min-width: 0;
  margin: 0;
  font-size: 14px;
  color: grey;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.speakerTitle > img {
  min-width: 0;
  flex: 0 0 1;
  height: 20px;
  width: auto;
}
.no-slide :deep(.el-tabs__active-bar) {
  transition: none !important;
}

.rank-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  /* height: 48px; */
}

.rank-container {
  position: relative;
  width: 25px;
  height: 25px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.rank-number {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #fff;
  font-size: 10px;
  font-weight: bold;
  line-height: 1;
}

.model-icon {
  width: 30px;
  height: 30px;
  display: block;
}

.rank-icon {
  width: 25px;
  height: 25px;
  display: block;
  object-fit: cover;
}
</style>
