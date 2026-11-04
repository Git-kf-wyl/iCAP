<template>
  <div class="cardContainer">
    <el-container style="gap:1%">
      <el-aside class="stasticsAnchorList">
        <el-select
          ref="taskSelectRef"
          v-model="selectedTaskIds"
          multiple
          multiple-limit="5"
          filterable
          placeholder="请选择任务"
          popper-class="task-selector"
          @visible-change="dropdownVisible = $event"
          v-if="canCompare"
        >
          <template #header>
            <div class="table-header">
              <el-table
                :data="filteredTasks"
                style="width: 100%"
                height="500"
                @row-click="toggleSelection"
              >
                <el-table-column width="50">
                  <template #default="{ row }">
                    <el-checkbox
                      :model-value="isSelected(row.ID)"
                      @click.stop="toggleTask(row)"
                      :disabled="row.ID===props.task_id || isRowDisabled(row)"
                    />
                  </template>
                </el-table-column>
                <el-table-column prop="ID" label="任务ID" width="100" />
                <el-table-column prop="name" label="任务名称" width="150" />
                <el-table-column prop="createTime" label="创建时间" width="180" />
                <el-table-column prop="model_name" label="模型名称" width="150" />
                <el-table-column prop="datasets" label="测试集名称" width="150" />
                <el-table-column label="任务类型" width="200">
                  <template #default="{ row }">
                    <!-- 假设 taskConfig 是 row 中的一个属性 -->
                    <div
                      v-if="row.taskConfig && row.taskConfig.dataset_args && row.taskConfig.dataset_args[0]"
                    >{{ row.taskConfig.dataset_args[0].subset_list.join(', ') }}</div>
                    <div v-else>无数据</div>
                  </template>
                </el-table-column>
                <el-table-column prop="description" label="任务描述" />
              </el-table>
            </div>
          </template>
          <template #tag>
            <span v-if="selectedTaskIds.length > 0">已选择 {{ selectedTaskIds.length }} 个任务</span>
          </template>
          <template #empty>
            <div>
              <el-button type="primary" @click="handleConfirm">确认</el-button>
              <el-button @click="handelCancel">取消</el-button>
            </div>
          </template>
        </el-select>
        <h4 style="margin:5px 5px 5px 20px;line-height: 20px;">目录</h4>

        <el-scrollbar
          style="height:calc(99% - 116px)"
          :always="true"
          v-if="sheet_scene ==='normal'"
        >
          <el-anchor
            :offset="30"
            :container="mainContainerRef"
            direction="vertical"
            class="anchor-nav"
            type="underline"
          >
            <el-anchor-link href="#businesses-accuracy" title="各个业务整体准确率交付指标" />
            <el-anchor-link href="#Indicators" title="交付指标">
              <template #sub-link>
                <el-anchor-link href="#attention-indicator" title="注意力交付指标" />
                <el-anchor-link href="#sitting-indicator" title="坐姿交付指标" />
                <el-anchor-link href="#distance-indicator" title="视距交付指标" />
                <el-anchor-link href="#seat-indicator" title="离座检测交付指标" />
              </template>
            </el-anchor-link>

            <el-anchor-link href="#total-accuracy" title="总的正确率" />
            <el-anchor-link href="#class-accuracy" title="各个大小类的正确率" />
            <el-anchor-link href="#cost-time-statistics" title="时延分布统计" />
            <el-anchor-link href="#source-statistics" title="不同图片来源统计" />
            <el-anchor-link href="#resolution-statistics" title="不同分辨率统计" />

            <el-anchor-link href="#attention-section" title="注意力">
              <template #sub-link>
                <!-- <el-anchor-link href="#attention_difficulty" title="注意力小类难易度正确率" /> -->
                <el-anchor-link href="#attention_precision" title="注意力统计_模型" />
                <el-anchor-link href="#attention-confusion-matrix2" title="注意力混淆矩阵_模型" />
              </template>
            </el-anchor-link>

            <el-anchor-link href="#posture-section" title="坐姿">
              <template #sub-link>
                <!-- <el-anchor-link href="#sitting_difficulty" title="坐姿小类难易度正确率" /> -->
                <el-anchor-link href="#sitting_precision" title="坐姿统计_模型" />
                <el-anchor-link href="#posture-confusion-matrix2" title="坐姿混淆矩阵_模型" />
              </template>
            </el-anchor-link>
          </el-anchor>
        </el-scrollbar>
        <el-scrollbar style="height:calc(99% - 116px)" :always="true" v-if="sheet_scene ==='part'">
          <el-anchor
            :offset="30"
            :container="partContainerRef"
            direction="vertical"
            class="anchor-nav"
            type="underline"
          >
            <el-anchor-link href="#businesses-accuracy-part" title="各个业务的正确率" />
            <el-anchor-link href="#attention-indicator-part" title="注意力交付指标" />
            <el-anchor-link href="#sitting-indicator-part" title="坐姿交付指标" />
            <el-anchor-link href="#attention-confusion-matrix-part" title="注意力混淆矩阵" />
            <el-anchor-link href="#posture-confusion-matrix-part" title="坐姿混淆矩阵" />
          </el-anchor>
        </el-scrollbar>
        <el-scrollbar
          style="height:calc(99% - 116px)"
          :always="true"
          v-if="sheet_scene ==='Doubao'"
        >
          <el-anchor
            :offset="30"
            :container="doubaoContainerRef"
            direction="vertical"
            class="anchor-nav"
            type="underline"
          >
            <el-anchor-link href="#businesses-accuracy-doubao" title="各个业务的正确率" />
            <el-anchor-link href="#attention-indicator-doubao" title="注意力交付指标" />
            <el-anchor-link href="#sitting-indicator-doubao" title="坐姿交付指标" />
            <!-- <el-anchor-link href="#distance-indicator-doubao" title="视距交付指标" />
            <el-anchor-link href="#seat-indicator-doubao" title="离座检测交付指标" />-->
          </el-anchor>
        </el-scrollbar>
        <el-scrollbar
          style="height:calc(99% - 116px)"
          :always="true"
          v-if="sheet_scene ==='timeDelay'"
        >
          <el-anchor
            :offset="30"
            :container="partContainerRef"
            direction="vertical"
            class="anchor-nav"
            type="underline"
          >
            <el-anchor-link href="#time-delay-statistics" title="时延分布统计" />
            <el-anchor-link href="#total-time" title="平均时延" />
          </el-anchor>
        </el-scrollbar>
        <el-scrollbar
          style="height:calc(99% - 116px)"
          :always="true"
          v-if="sheet_scene ==='stability'"
        >
          <el-anchor
            :offset="30"
            :container="partContainerRef"
            direction="vertical"
            class="anchor-nav"
            type="underline"
          >
            <el-anchor-link href="#attention-stability" title="注意力稳定性分布" />
            <el-anchor-link href="#position-stability" title="坐姿稳定性分布" />
            <el-anchor-link href="#total-stability" title="汇总" />
          </el-anchor>
        </el-scrollbar>
        <el-scrollbar
          style="height:calc(99% - 116px)"
          :always="true"
          v-if="sheet_scene && sheet_scene.startsWith('dynamic_')"
        >
          <el-anchor
            :offset="100"
            :container="dynamicContainerRef"
            direction="vertical"
            class="anchor-nav"
            type="underline"
          >
            <el-anchor-link
              v-for="(table, tableIdx) in getDynamicAnchorLinks()"
              :key="tableIdx"
              :href="'#dynamic-' + tableIdx"
              :title="getDynamicAnchorTitle(table)"
            />
          </el-anchor>
        </el-scrollbar>
      </el-aside>
      <el-main class="tablesContainer">
        <div>
          <el-radio-group
            v-model="sheet_scene"
            size="large"
            fill="#409eff"
            v-if="statisticsData.length>0 && selectedTaskIds.length>0 && selected.length > 0"
          >
            <el-radio-button label="稳定性" value="stability" v-if="taskSubSet==='稳定性'" />
            <el-radio-button label="时延分布" value="timeDelay" v-if="taskSubSet==='时延分布'" />
            <el-radio-button label="评测结果统计" value="normal" />
            <el-radio-button label="与产品验收维度保持一致" value="part" />
            <el-radio-button
              v-for="name in dynamicSheetNames"
              :key="name"
              :label="name"
              :value="'dynamic_' + name"
            />
            <!-- <el-radio-button label="根据豆包正确项统计结果" value="Doubao" /> -->
          </el-radio-group>
        </div>

        <div
          v-if="statisticsData.length>0 && selectedTaskIds.length>0 && selected.length > 0 && sheet_scene ==='normal'"
          ref="mainContainerRef"
          style="height:calc(100% - 40px);overflow: auto;"
        >
          <div id="businesses-accuracy" class="stasticsTableTitle">
            各个业务整体准确率交付指标
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(36)"
              type="primary"
            >{{ tableVisible[36] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[36]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="filteredTableData(totalAccuracyTableData[idx])"
                stripe
                border
                class="statisticTable"
              >
                <el-table-column prop="维度" label="维度" show-overflow-tooltip />
                <el-table-column prop="总数量" label="总数量" />
                <el-table-column prop="正确数量" label="正确数量" />
                <el-table-column prop="正确率" label="正确率" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateStatusChartData(totalAccuracyTableData, preSelectedTasks)"
            :title="'各个业务整体准确率交付指标'"
            :rateName="'正确率'"
            :width="'99%'"
            v-if="selected.length>=2"
          />

          <div id="businesses-accuracy" class="stasticsTableTitle">
            各个业务整体准确率交付指标
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(36)"
              type="primary"
            >{{ tableVisible[36] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[36]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="filteredTableData(totalAccuracyTableData_1[idx])"
                stripe
                border
                class="statisticTable"
              >
                <el-table-column prop="维度" label="维度" show-overflow-tooltip />
                <el-table-column prop="总数量" label="总数量" />
                <el-table-column prop="正确数量" label="正确数量" />
                <el-table-column prop="正确率" label="正确率" show-overflow-tooltip />
                <el-table-column prop="等比例缩放后总数量" label="等比例缩放后总数量" show-overflow-tooltip />
                <el-table-column prop="等比例缩放后正确数量" label="等比例缩放后正确数量" show-overflow-tooltip />
                <el-table-column prop="等比例缩放后正确率" label="等比例缩放后正确率" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateStatusChartData(totalAccuracyTableData_1, preSelectedTasks)"
            :title="'各个业务整体准确率交付指标'"
            :rateName="'正确率'"
            :width="'99%'"
            v-if="selected.length>=2"
          />

          <div id="Indicators" class="stasticsTableTitle">交付指标</div>
          <div id="attention-indicator" class="statisticsChildTitle">
            注意力交付指标
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(35)"
              type="primary"
            >{{ tableVisible[35] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[35]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="attentionIndicatorTablData[idx]"
                stripe
                border
                class="statisticTable"
                :cell-style="attentionIndicatorCellStyle"
              >
                <el-table-column prop="小类名" label="注意力小类" />
                <el-table-column prop="真实样本数" label="真实样本数" />
                <el-table-column prop="TP" label="TP" />
                <el-table-column prop="TN" label="TN" />
                <el-table-column prop="FP" label="FP" />
                <el-table-column prop="FN" label="FN" />
                <el-table-column prop="精确率计算TP/TP+FP" label="精确率计算(TP/(TP+FP))" />
                <el-table-column prop="精确率" label="精确率" />
                <el-table-column prop="召回率计算TP/TP+FN" label="召回率计算(TP/(TP+FN))" />
                <el-table-column prop="召回率" label="召回率" />
                <el-table-column prop="召回率等比例缩放后" label="召回率等比例缩放后" />
                <el-table-column prop="F1-score" label="F1-score" />
              </el-table>
            </div>
          </div>

          <div id="sitting-indicator" class="statisticsChildTitle">
            坐姿交付指标
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(35)"
              type="primary"
            >{{ tableVisible[35] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[35]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="sittingIndicatorTablData[idx]"
                stripe
                border
                class="statisticTable"
                :cell-style="sittingIndicatorCellStyle"
              >
                <el-table-column prop="小类名" label="坐姿小类" />
                <el-table-column prop="真实样本数" label="真实样本数" />
                <el-table-column prop="TP" label="TP" />
                <el-table-column prop="TN" label="TN" />
                <el-table-column prop="FP" label="FP" />
                <el-table-column prop="FN" label="FN" />
                <el-table-column prop="精确率计算TP/TP+FP" label="精确率计算(TP/(TP+FP))" />
                <el-table-column prop="精确率" label="精确率" />
                <el-table-column prop="召回率计算TP/TP+FN" label="召回率计算(TP/(TP+FN))" />
                <el-table-column prop="召回率" label="召回率" />
                <el-table-column prop="召回率等比例缩放后" label="召回率等比例缩放后" />
                <el-table-column prop="F1-score" label="F1-score" />
              </el-table>
            </div>
          </div>

          <div id="total-accuracy" class="stasticsTableTitle">
            总的正确率
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(0)"
              type="primary"
            >{{ tableVisible[0] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[0]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table :data="accuracyTableData[idx]" stripe border class="statisticTable">
                <el-table-column prop="指标" label="指标" width="180" show-overflow-tooltip />
                <el-table-column prop="数值" label="数值" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
          <div class="tables-container">
            <ChildrenStudyLineChart
              :data="accuracyChartData"
              :title="'总正确率'"
              :dataType="{
              总正确率:true,
            }"
              :width="'49%'"
              v-if="selected.length>=2"
            />
            <ChildrenStudyBarLineChart
              :data="tokensChartData"
              :title="'tokens与耗时统计'"
              :dataType="{
              平均completion_tokens: false,
              平均prompt_tokens: false,
              平均total_tokens: false,
              平均cost_time: true,
            }"
              :width="'49%'"
              v-if="selected.length>=2"
            />
          </div>

          <div id="class-accuracy" class="stasticsTableTitle">
            各个大小类的正确率
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(1)"
              type="primary"
            >{{ tableVisible[1] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[1]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table :data="statusTableData[idx]" stripe border class="statisticTable">
                <el-table-column prop="维度" label="维度" show-overflow-tooltip />
                <el-table-column prop="总数量" label="总数量" />
                <el-table-column prop="正确数量" label="正确数量" />
                <el-table-column prop="正确率" label="正确率" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateStatusChartData(statusTableData,preSelectedTasks)"
            :title="'各个大小类的正确率'"
            :rateName="'正确率'"
            :width="'99%'"
            v-if="selected.length>=2"
          />

          <div id="cost-time-statistics" class="stasticsTableTitle">
            时延分布统计
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(2)"
              type="primary"
            >{{ tableVisible[2] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[2]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table :data="costTimeTableData[idx]" stripe border class="statisticTable">
                <el-table-column prop="耗时" label="耗时" />
                <el-table-column prop="数量" label="数量" />
                <el-table-column prop="占比" label="占比" />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateCostTimeChartData(costTimeTableData,preSelectedTasks)"
            :title="'时延分布统计'"
            :rateName="'占比'"
            :width="'99%'"
            v-if="selected.length>=2"
          />

          <div id="source-statistics" class="stasticsTableTitle">
            不同图片来源统计
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(3)"
              type="primary"
            >{{ tableVisible[3] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[3]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table :data="sourceTableData[idx]" stripe border class="statisticTable">
                <el-table-column
                  v-for="column in dynamicSourceColumns"
                  :key="column"
                  :prop="column"
                  :label="column"
                  show-overflow-tooltip
                />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateSourceChartData(sourceTableData,preSelectedTasks)"
            :title="'不同图片来源统计'"
            :rateName="'正确率'"
            :width="'99%'"
            v-if="selected.length>=2"
          />

          <div id="resolution-statistics" class="stasticsTableTitle">
            不同分辨率统计
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(4)"
              type="primary"
            >{{ tableVisible[4] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[4]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table :data="resolutionTableData[idx]" stripe border class="statisticTable">
                <el-table-column prop="分辨率" label="分辨率" show-overflow-tooltip />
                <el-table-column prop="总数量" label="总数量" />
                <el-table-column prop="正确数量" label="正确数量" />
                <el-table-column prop="正确率" label="正确率" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateResolutionChartData(resolutionTableData,preSelectedTasks)"
            :title="'各个大小类的正确率'"
            :rateName="'正确率'"
            :width="'99%'"
            v-if="selected.length>=2"
          />

          <!-- <div id="attention_difficulty" class="statisticsChildTitle">
            注意力小类难易度正确率
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(7)"
              type="primary"
            >{{ tableVisible[7] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[7]">
            <div v-for="index in Result.length" :key="index" class="table-wrapper">
              <div
                class="text_center"
              >{{ selected[index-1]?.name }}——{{ selected[index-1]?.model_id }}——{{ selected[index-1]?.datasets?.[0] }}</div>
              <el-table
                :data="attentionDifficultyTablData[index - 1]"
                stripe
                border
                class="statisticTable"
              >
                <el-table-column prop="level" label="难易程度" />
                <el-table-column prop="total" label="总数量" show-overflow-tooltip />
                <el-table-column prop="correct" label="正确数量" show-overflow-tooltip />
                <el-table-column prop="accuracy" label="占比" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateDifficultyChartData(attentionDifficultyTablData,preSelectedTasks)"
            :title="'注意力小类难易度正确率'"
            :rateName="'正确率'"
            :width="'99%'"
            v-if="selected.length>=2"
          />-->

          <div id="attention_precision" class="statisticsChildTitle">
            注意力统计_模型
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(11)"
              type="primary"
            >{{ tableVisible[11] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[11]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="attentionPrecisionTablData[idx]"
                stripe
                border
                class="statisticTable"
              >
                <el-table-column prop="小类名" label="注意力小类" />
                <el-table-column prop="TP" label="TP" />
                <el-table-column prop="TN" label="TN" />
                <el-table-column prop="FP" label="FP" />
                <el-table-column prop="FN" label="FN" />
                <el-table-column prop="精确率" label="精确率" />
                <el-table-column prop="召回率" label="召回率" />
                <el-table-column prop="漏报率" label="漏报率" />
                <el-table-column prop="误发现率" label="误发现率" />
              </el-table>
            </div>
          </div>

          <div id="attention-confusion-matrix2" class="statisticsChildTitle">
            注意力混淆矩阵_模型
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(12)"
              type="primary"
            >{{ tableVisible[12] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[12]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="attentionConfusionMatrixData2[idx]?.tableData"
                stripe
                border
                class="statisticTable"
                :cell-style="handleCellStyleGreen"
              >
                <el-table-column
                  prop="goldValue"
                  :label="attentionConfusionMatrixData2[idx]?.dimensionName"
                />
                <el-table-column
                  v-for="pred in attentionConfusionMatrixData2[idx]?.predValues"
                  :key="pred"
                  :prop="pred.replace(/\s+/g, '_')"
                  :label="pred"
                />
              </el-table>
            </div>
          </div>

          <!-- <div id="sitting_difficulty" class="statisticsChildTitle">
            坐姿小类难易度正确率
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(15)"
              type="primary"
            >{{ tableVisible[15] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[15]">
            <div v-for="index in Result.length" :key="index" class="table-wrapper">
              <div
                class="text_center"
              >{{ selected[index-1]?.name }}——{{ selected[index-1]?.model_id }}——{{ selected[index-1]?.datasets?.[0] }}</div>
              <el-table
                :data="sittingDifficultyTablData[index - 1]"
                stripe
                border
                class="statisticTable"
              >
                <el-table-column prop="level" label="难易程度" />
                <el-table-column prop="total" label="总数量" show-overflow-tooltip />
                <el-table-column prop="correct" label="正确数量" show-overflow-tooltip />
                <el-table-column prop="accuracy" label="占比" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateDifficultyChartData(sittingDifficultyTablData,preSelectedTasks)"
            :title="'坐姿小类难易度正确率'"
            :rateName="'正确率'"
            :width="'99%'"
            v-if="selected.length>=2"
          />-->

          <div id="sitting_precision" class="statisticsChildTitle">
            坐姿统计_模型
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(19)"
              type="primary"
            >{{ tableVisible[19] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[19]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table :data="sittingPrecisionTablData[idx]" stripe border class="statisticTable">
                <el-table-column prop="小类名" label="坐姿小类" />
                <el-table-column prop="TP" label="TP" />
                <el-table-column prop="TN" label="TN" />
                <el-table-column prop="FP" label="FP" />
                <el-table-column prop="FN" label="FN" />
                <el-table-column prop="精确率" label="精确率" />
                <el-table-column prop="召回率" label="召回率" />
                <el-table-column prop="漏报率" label="漏报率" />
                <el-table-column prop="误发现率" label="误发现率" />
              </el-table>
            </div>
          </div>

          <div id="posture-confusion-matrix2" class="statisticsChildTitle">
            坐姿混淆矩阵_模型
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(20)"
              type="primary"
            >{{ tableVisible[20] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[20]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="sittingConfusionMatrixData2[idx]?.tableData"
                stripe
                border
                class="statisticTable"
                :cell-style="handleCellStyleGreen"
              >
                <el-table-column
                  prop="goldValue"
                  :label="sittingConfusionMatrixData2[idx]?.dimensionName"
                />
                <el-table-column
                  v-for="pred in sittingConfusionMatrixData2[idx]?.predValues"
                  :key="pred"
                  :prop="pred.replace(/\s+/g, '_')"
                  :label="pred"
                />
              </el-table>
            </div>
          </div>
        </div>

        <div
          v-else-if="selected.length > 0 && sheet_scene ==='part'"
          ref="partContainerRef"
          style="height:calc(100% - 40px);overflow: auto;"
        >
          <div id="businesses-accuracy-part" class="stasticsTableTitle">
            各个业务的正确率
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(36)"
              type="primary"
            >{{ tableVisible[36] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[36]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="filteredTableData(statusPartTableData[idx])"
                stripe
                border
                class="statisticTable"
              >
                <el-table-column prop="维度" label="维度" show-overflow-tooltip />
                <el-table-column prop="总数量" label="总数量" />
                <el-table-column prop="正确数量" label="正确数量" />
                <el-table-column prop="正确率" label="正确率" show-overflow-tooltip />
                <el-table-column prop="等比例缩放后总数量" label="等比例缩放后总数量" show-overflow-tooltip />
                <el-table-column prop="等比例缩放后正确数量" label="等比例缩放后正确数量" show-overflow-tooltip />
                <el-table-column prop="等比例缩放后正确率" label="等比例缩放后正确率" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateStatusChartData(statusPartTableData, preSelectedTasks)"
            :title="'各个业务的正确率'"
            :rateName="'正确率'"
            :width="'99%'"
            v-if="selected.length>=2"
          />

          <div id="attention-indicator-part" class="statisticsChildTitle">
            注意力交付指标
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(35)"
              type="primary"
            >{{ tableVisible[35] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[35]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="attentionIndicatorPartTablData[idx]"
                stripe
                border
                class="statisticTable"
                :cell-style="attentionIndicatorCellStyle"
              >
                <el-table-column prop="小类名" label="注意力小类" />
                <el-table-column prop="真实样本数" label="真实样本数" />
                <el-table-column prop="TP" label="TP" />
                <el-table-column prop="TN" label="TN" />
                <el-table-column prop="FP" label="FP" />
                <el-table-column prop="FN" label="FN" />
                <el-table-column prop="精确率计算TP/TP+FP" label="精确率计算(TP/(TP+FP))" />
                <el-table-column prop="精确率" label="精确率" />
                <el-table-column prop="召回率计算TP/TP+FN" label="召回率计算(TP/(TP+FN))" />
                <el-table-column prop="召回率" label="召回率" />
                <el-table-column prop="召回率等比例缩放后" label="召回率等比例缩放后" />
                <el-table-column prop="F1-score" label="F1-score" />
                <el-table-column prop="Weighted F1-score" label="Weighted F1-score" />
              </el-table>
            </div>
          </div>

          <div id="sitting-indicator-part" class="statisticsChildTitle">
            坐姿交付指标
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(35)"
              type="primary"
            >{{ tableVisible[35] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[35]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="sittingIndicatorPartTablData[idx]"
                stripe
                border
                class="statisticTable"
                :cell-style="sittingIndicatorCellStyle"
              >
                <el-table-column prop="小类名" label="坐姿小类" />
                <el-table-column prop="真实样本数" label="真实样本数" />
                <el-table-column prop="TP" label="TP" />
                <el-table-column prop="TN" label="TN" />
                <el-table-column prop="FP" label="FP" />
                <el-table-column prop="FN" label="FN" />
                <el-table-column prop="精确率计算TP/TP+FP" label="精确率计算(TP/(TP+FP))" />
                <el-table-column prop="精确率" label="精确率" />
                <el-table-column prop="召回率计算TP/TP+FN" label="召回率计算(TP/(TP+FN))" />
                <el-table-column prop="召回率" label="召回率" />W
                <el-table-column prop="召回率等比例缩放后" label="召回率等比例缩放后" />
                <el-table-column prop="F1-score" label="F1-score" />
                <el-table-column prop="Weighted F1-score" label="Weighted F1-score" />
              </el-table>
            </div>
          </div>

          <div id="attention-confusion-matrix2" class="statisticsChildTitle">
            注意力混淆矩阵_模型
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(12)"
              type="primary"
            >{{ tableVisible[12] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[12]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="attentionConfusionMatrixData2[idx]?.tableData"
                stripe
                border
                class="statisticTable"
                :cell-style="handleCellStyleGreen"
              >
                <el-table-column
                  prop="goldValue"
                  :label="attentionConfusionMatrixData2[idx]?.dimensionName"
                />
                <el-table-column
                  v-for="pred in attentionConfusionMatrixData2[idx]?.predValues"
                  :key="pred"
                  :prop="pred.replace(/\s+/g, '_')"
                  :label="pred"
                />
              </el-table>
            </div>
          </div>

          <div id="posture-confusion-matrix2" class="statisticsChildTitle">
            坐姿混淆矩阵_模型
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(20)"
              type="primary"
            >{{ tableVisible[20] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[20]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="sittingConfusionMatrixData2[idx]?.tableData"
                stripe
                border
                class="statisticTable"
                :cell-style="handleCellStyleGreen"
              >
                <el-table-column
                  prop="goldValue"
                  :label="sittingConfusionMatrixData2[idx]?.dimensionName"
                />
                <el-table-column
                  v-for="pred in sittingConfusionMatrixData2[idx]?.predValues"
                  :key="pred"
                  :prop="pred.replace(/\s+/g, '_')"
                  :label="pred"
                />
              </el-table>
            </div>
          </div>
        </div>

        <div
          v-else-if="selected.length > 0 && sheet_scene ==='Doubao'"
          ref="doubaoContainerRef"
          style="height:calc(100% - 40px);overflow: auto;"
        >
          <div id="businesses-accuracy-doubao" class="stasticsTableTitle">
            各个业务的正确率
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(36)"
              type="primary"
            >{{ tableVisible[36] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[36]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="filteredTableData(statusTableData[idx])"
                stripe
                border
                class="statisticTable"
              >
                <el-table-column prop="dimension" label="维度" show-overflow-tooltip />
                <el-table-column prop="totalSamples" label="总数量" />
                <el-table-column prop="count" label="正确数量" />
                <el-table-column prop="accuracy" label="正确率" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateStatusChartData(statusTableData, preSelectedTasks)"
            :title="'各个业务的正确率'"
            :rateName="'正确率'"
            :width="'99%'"
            v-if="selected.length>=2"
          />

          <div id="attention-indicator-doubao" class="statisticsChildTitle">
            注意力交付指标
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(35)"
              type="primary"
            >{{ tableVisible[35] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[35]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="attentionIndicatorTablData[idx]"
                stripe
                border
                class="statisticTable"
                :cell-style="attentionIndicatorCellStyle"
              >
                <el-table-column prop="小类名" label="注意力小类" />
                <el-table-column prop="TP" label="TP" />
                <el-table-column prop="TN" label="TN" />
                <el-table-column prop="FP" label="FP" />
                <el-table-column prop="FN" label="FN" />
                <el-table-column prop="精确率计算(TP/(TP+FP))" label="精确率计算(TP/(TP+FP))" />
                <el-table-column prop="精确率" label="精确率" />
                <el-table-column prop="召回率计算(TP/(TP+FN))" label="召回率计算(TP/(TP+FN))" />
                <el-table-column prop="召回率" label="召回率" />
              </el-table>
            </div>
          </div>

          <div id="sitting-indicator-doubao" class="statisticsChildTitle">
            坐姿交付指标
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(35)"
              type="primary"
            >{{ tableVisible[35] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[35]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table
                :data="sittingIndicatorTablData[idx]"
                stripe
                border
                class="statisticTable"
                :cell-style="sittingIndicatorCellStyle"
              >
                <el-table-column prop="小类名" label="坐姿小类" />
                <el-table-column prop="TP" label="TP" />
                <el-table-column prop="TN" label="TN" />
                <el-table-column prop="FP" label="FP" />
                <el-table-column prop="FN" label="FN" />
                <el-table-column prop="精确率计算(TP/(TP+FP))" label="精确率计算(TP/(TP+FP))" />
                <el-table-column prop="精确率" label="精确率" />
                <el-table-column prop="召回率计算(TP/(TP+FN))" label="召回率计算(TP/(TP+FN))" />
                <el-table-column prop="召回率" label="召回率" />
              </el-table>
            </div>
          </div>
        </div>

        <div v-else-if="selected.length > 0 && sheet_scene === 'timeDelay' && taskSubSet === '时延分布'">
          <div id="time-delay-statistics" class="stasticsTableTitle">
            时延分布统计
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(2)"
              type="primary"
            >{{ tableVisible[2] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[2]">
            <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
              <div
                class="text_center"
              >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
              <el-table :data="costTimeTableData[idx]" stripe border class="statisticTable">
                <el-table-column prop="interval" label="耗时区间" />
                <el-table-column prop="count" label="数量" />
                <el-table-column prop="percentage" label="占比" />
              </el-table>
              <ChildrenStudyBarChart :data="costTimeTableData[index - 1]" :width="'100%'" />
            </div>
          </div>

          <div id="total-time" class="stasticsTableTitle">
            平均时延
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(0)"
              type="primary"
            >{{ tableVisible[0] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[0]">
            <div v-for="index in Result.length" :key="index" class="table-wrapper">
              <div
                class="text_center"
              >{{ selected[index-1]?.name }}——{{ selected[index-1]?.model_id }}——{{ selected[index-1]?.datasets?.[0] }}</div>
              <el-table
                :data="accuracyTableData[index - 1].filter(x=>x.metric === '平均cost_time' || x.metric === '总数量')"
                stripe
                border
                class="statisticTable"
              >
                <el-table-column prop="metric" label="指标" width="180" show-overflow-tooltip />
                <el-table-column prop="value" label="数值" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
          <div class="tables-container">
            <ChildrenStudyBarLineChart
              :data="tokensChartData"
              :title="'平均时延统计'"
              :dataType="{
              平均cost_time: true,
            }"
              :width="'99%'"
              v-if="selected.length>=2"
            />
          </div>
        </div>

        <div v-else-if="selected.length > 0 && sheet_scene === 'stability' && taskSubSet === '稳定性'">
          <div id="attention-stability" class="stasticsTableTitle">
            注意力稳定性分布
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(0)"
              type="primary"
            >{{ tableVisible[0] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[0]">
            <div v-for="index in Result.length" :key="index" class="table-wrapper">
              <div
                class="text_center"
              >{{ selected[index-1]?.name }}——{{ selected[index-1]?.model_id }}——{{ selected[index-1]?.datasets?.[0] }}</div>
              <el-table
                :data="attentionStabilityData[index - 1]"
                stripe
                border
                class="statisticTable"
              >
                <el-table-column prop="category" label="小类名" show-overflow-tooltip />
                <el-table-column prop="count1" label="第一次数量" />
                <el-table-column prop="count2" label="第二次数量" />
                <el-table-column prop="count3" label="第三次数量" />
                <el-table-column prop="total" label="总数量" />
                <el-table-column prop="stableCount" label="稳定数量" />
                <el-table-column prop="stabilityRate" label="稳定性率" />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateStabilityChartData(attentionStabilityData,preSelectedTasks)"
            :title="'注意力稳定性分布'"
            :rateName="'稳定性率'"
            :width="'99%'"
            v-if="selected.length>=2"
          />

          <div id="position-stability" class="stasticsTableTitle">
            坐姿稳定性分布
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(1)"
              type="primary"
            >{{ tableVisible[1] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[1]">
            <div v-for="index in Result.length" :key="index" class="table-wrapper">
              <div
                class="text_center"
              >{{ selected[index-1]?.name }}——{{ selected[index-1]?.model_id }}——{{ selected[index-1]?.datasets?.[0] }}</div>
              <el-table
                :data="sittingStabilityData[index - 1]"
                stripe
                border
                class="statisticTable"
              >
                <el-table-column prop="category" label="小类名" show-overflow-tooltip />
                <el-table-column prop="count1" label="第一次数量" />
                <el-table-column prop="count2" label="第二次数量" />
                <el-table-column prop="count3" label="第三次数量" />
                <el-table-column prop="total" label="总数量" />
                <el-table-column prop="stableCount" label="稳定数量" />
                <el-table-column prop="stabilityRate" label="稳定性率" />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateStabilityChartData(sittingStabilityData,preSelectedTasks)"
            :title="'坐姿稳定性分布'"
            :rateName="'稳定性率'"
            :width="'99%'"
            v-if="selected.length>=2"
          />

          <div id="total-stability" class="stasticsTableTitle">
            汇总
            <el-button
              v-if="selected.length > 2"
              @click="toggleTable(2)"
              type="primary"
            >{{ tableVisible[2] ? '收起表格' : '展开表格' }}</el-button>
          </div>
          <div class="tables-container" v-if="selected.length<=2 || tableVisible[2]">
            <div v-for="index in Result.length" :key="index" class="table-wrapper">
              <div
                class="text_center"
              >{{ selected[index-1]?.name }}——{{ selected[index-1]?.model_id }}——{{ selected[index-1]?.datasets?.[0] }}</div>
              <el-table :data="totalStabilityData[index - 1]" stripe border class="statisticTable">
                <el-table-column prop="category" label show-overflow-tooltip />
                <el-table-column prop="count1" label="第一次数量" />
                <el-table-column prop="count2" label="第二次数量" />
                <el-table-column prop="count3" label="第三次数量" />
                <el-table-column prop="total" label="总数量" />
                <el-table-column prop="stableCount" label="稳定数量" />
                <el-table-column prop="stabilityRate" label="稳定性率" />
              </el-table>
            </div>
          </div>
          <childrenStudyMattrixChart
            :data="generateStabilityChartData(totalStabilityData,preSelectedTasks)"
            :title="'汇总'"
            :rateName="'稳定性率'"
            :width="'99%'"
            v-if="selected.length>=2"
          />
        </div>
        
        <div
          v-else-if="selected.length > 0 && sheet_scene && sheet_scene.startsWith('dynamic_')"
          ref="dynamicContainerRef"
          style="height:calc(100% - 40px);overflow: auto;"
        >
          <div v-for="(table, tableIdx) in getActiveDynamicSheetTables()" :key="tableIdx">
            <div :id="'dynamic-' + tableIdx" class="stasticsTableTitle">
              {{ getDynamicAnchorTitle(table) }}
              <el-button
                v-if="selected.length > 2"
                @click="toggleTable(99 + tableIdx)"
                type="primary"
              >{{ tableVisible[99 + tableIdx] ? '收起表格' : '展开表格' }}</el-button>
            </div>
            <div class="tables-container" v-if="selected.length<=2 || tableVisible[99 + tableIdx]">
              <div v-for="(task, idx) in selected" :key="idx" class="table-wrapper">
                <div
                  class="text_center"
                >{{ task?.name }}——{{ task?.model_id }}——{{ task?.datasets?.[0] }}</div>
                <el-table
                  :data="getDynamicTableData(idx, getCurrentSheetName(), tableIdx)"
                  stripe
                  border
                  class="statisticTable"
                >
                  <el-table-column
                    v-for="col in getDynamicColumns(idx, getCurrentSheetName(), tableIdx)"
                    :key="col"
                    :prop="col"
                    :label="col"
                    show-overflow-tooltip
                  />
                </el-table>
              </div>
            </div>
          </div>
        </div>
        <div v-if="selected.length === 0">暂无数据</div>
      </el-main>
    </el-container>
  </div>
</template>

<script lang="ts" setup>
import { inject, ref } from "vue";
import ChildrenStudyMattrixChart from "./charts/childrenStudyMattrixChart.vue";
import ChildrenStudyLineChart from "./charts/childrenStudyLineChart.vue";
import ChildrenStudyBarLineChart from "./charts/childrenStudyBarLineChart.vue";
import ChildrenStudyBarChart from "./charts/childrenStudyBarChart.vue";

const injected = inject("childrenStudyData");

// ── useTaskSelection ──
const taskSelectRef = injected.taskSelectRef;
const selectedTaskIds = injected.selectedTaskIds;
const selectedTasks = injected.selectedTasks;
const selected = injected.selected;
const filteredTasks = injected.filteredTasks;
const dropdownVisible = injected.dropdownVisible;
const taskSubSet = injected.taskSubSet;
const sheet_scene = injected.sheet_scene;
const Result = injected.Result;
const preSelectedTasks = injected.preSelectedTasks;
const isSelected = injected.isSelected;
const isRowDisabled = injected.isRowDisabled;
const toggleTask = injected.toggleTask;
const toggleSelection = injected.toggleSelection;
const handelCancel = injected.handelCancel;
const canCompare = injected.canCompare;

// ── useCellStyles ──
const tableVisible = injected.tableVisible;
const toggleTable = injected.toggleTable;
const attentionIndicatorCellStyle = injected.attentionIndicatorCellStyle;
const sittingIndicatorCellStyle = injected.sittingIndicatorCellStyle;
const handleCellStyleGreen = injected.handleCellStyleGreen;
const filteredTableData = injected.filteredTableData;

// ── useChildrenStudyData ──
const statisticsData = injected.statisticsData;
const totalAccuracyTableData = injected.totalAccuracyTableData;
const totalAccuracyTableData_1 = injected.totalAccuracyTableData_1;
const statusTableData = injected.statusTableData;
const accuracyTableData = injected.accuracyTableData;
const costTimeTableData = injected.costTimeTableData;
const sourceTableData = injected.sourceTableData;
const resolutionTableData = injected.resolutionTableData;
// const attentionDifficultyTablData = injected.attentionDifficultyTablData;
const attentionPrecisionTablData = injected.attentionPrecisionTablData;
const attentionConfusionMatrixData2 = injected.attentionConfusionMatrixData2;
// const sittingDifficultyTablData = injected.sittingDifficultyTablData;
const sittingPrecisionTablData = injected.sittingPrecisionTablData;
const sittingConfusionMatrixData2 = injected.sittingConfusionMatrixData2;
const attentionIndicatorTablData = injected.attentionIndicatorTablData;
const sittingIndicatorTablData = injected.sittingIndicatorTablData;
const attentionIndicatorPartTablData = injected.attentionIndicatorPartTablData;
const sittingIndicatorPartTablData = injected.sittingIndicatorPartTablData;
const statusPartTableData = injected.statusPartTableData;
const dynamicSourceColumns = injected.dynamicSourceColumns;

const attentionStabilityData = injected.attentionStabilityData;
const sittingStabilityData = injected.sittingStabilityData;
const totalStabilityData = injected.totalStabilityData;

// ── useChildrenStudyCharts ──
const accuracyChartData = injected.accuracyChartData;
const tokensChartData = injected.tokensChartData;
const generateStatusChartData = injected.generateStatusChartData;
const generateCostTimeChartData = injected.generateCostTimeChartData;
const generateSourceChartData = injected.generateSourceChartData;
const generateResolutionChartData = injected.generateResolutionChartData;
const generateDifficultyChartData = injected.generateDifficultyChartData;
const generateStabilityChartData = injected.generateStabilityChartData;

// ── 包装后的 handleConfirm ──
const handleConfirm = injected.handleConfirm;

// ── 动态 sheet ──
const dynamicSheetData = injected.dynamicSheetData;
const dynamicSheetNames = injected.dynamicSheetNames;

// 获取当前激活的动态 sheet 的所有 table 结构（从第0个任务提取模板结构）
const getActiveDynamicSheet = () => {
  const data = dynamicSheetData.value?.[0];
  if (!data) return {};
  const activeSheet = sheet_scene.value?.replace("dynamic_", "");
  return activeSheet && data[activeSheet]
    ? { [activeSheet]: data[activeSheet] }
    : {};
};

// 获取某个任务某个 sheet 某个 table 的 columns（过滤空列）
const getDynamicColumns = (
  taskIndex: number,
  sheetName: string,
  tableIndex: number
) => {
  const tables = dynamicSheetData.value?.[taskIndex]?.[sheetName];
  if (!tables || !tables[tableIndex]) return [];
  return tables[tableIndex].columns.filter((c) => c.trim() !== "");
};

// 获取某个任务某个 sheet 某个 table 的 rows
const getDynamicTableData = (
  taskIndex: number,
  sheetName: string,
  tableIndex: number
) => {
  const tables = dynamicSheetData.value?.[taskIndex]?.[sheetName];
  if (!tables || !tables[tableIndex]) return [];
  return tables[tableIndex].rows;
};

// 获取动态锚点链接列表（返回当前 sheet 的 tables 数组）
const getDynamicAnchorLinks = () => {
  const data = dynamicSheetData.value?.[0];
  if (!data) return [];
  const activeSheet = sheet_scene.value?.replace("dynamic_", "");
  return activeSheet && data[activeSheet] ? data[activeSheet] : [];
};

// 获取动态锚点标题
const getDynamicAnchorTitle = (table: any) => {
  if (!table) return "";
  // table 可能是 {title, columns, rows} 结构
  const title = table.title?.replace(/^##/, "");
  return title || "";
};

// 获取当前激活的动态 sheet 的 tables 数组
const getActiveDynamicSheetTables = () => {
  const data = dynamicSheetData.value?.[0];
  if (!data) return [];
  const activeSheet = sheet_scene.value?.replace("dynamic_", "");
  if (!activeSheet || !data[activeSheet]) return [];
  return data[activeSheet];
};

// 获取当前激活的动态 sheet 名称
const getCurrentSheetName = () => {
  return sheet_scene.value?.replace("dynamic_", "");
};

// ── props ──
const props = injected.props;

// ── Container refs (模板内部使用) ──
const mainContainerRef = ref(null);
const partContainerRef = ref(null);
const doubaoContainerRef = ref(null);
const dynamicContainerRef = ref(null);
</script>

<style scoped>
.cardContainer {
  display: flex;
  flex-direction: column;
  gap: 2%;
  height: calc(100vh - 160px);
  margin: 0;
  padding: 0;
}

.stasticsTableTitle {
  margin: 10px;
  font-size: 20px;
  font-weight: 600;
}

.statisticsChildTitle {
  margin: 10px;
  font-size: 18px;
  font-weight: 600;
}

.statisticTable {
  max-height: 100%;
  width: 100%;
  overflow: auto;
}

.stasticsAnchorList {
  width: 12%;
  height: calc(100vh - 160px);
  margin-top: 10px;
  background-color: #fff;
  padding-left: 10px;
}

.anchor-nav {
  padding-left: 20px;
}

.tabsContainer :deep(.el-tabs__header) {
  margin-left: 20px;
}

.tablesContainer {
  width: 98%;
  height: calc(100vh - 160px);
  border-radius: 8px;
  background: rgb(255, 255, 255);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  overflow: auto;
}

.table-header {
  padding: 10px;
  width: 1000px;
}

.task-selector :deep(.el-select-dropdown__empty) {
  padding: 0 !important;
}

.tables-container {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  width: 100%;
}

.table-wrapper {
  width: 49%;
  margin-right: 1%;
  margin-bottom: 10px;
}

.table-wrapper:last-child {
  margin-right: 0 !important;
}

.text_center {
  text-align: center;
}
</style>