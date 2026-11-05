<template>
<el-container class="dataCardContainer">
  <el-scrollbar class="asideContainer">
    <el-aside class="screening" width="410px" style="margin-right: 10px;height:100%">
      <div style="margin: 20px">
        <div class="questionCard">
          <div style="display: flex; align-items: center; gap: 10px">
            <el-icon>
              <QuestionFilled />
            </el-icon>
            <b>问题列表</b>
            <div v-if="isinterpretation" style="margin-left: auto;">
              <el-radio-group v-model="scoreType" size="default">
                <el-radio-button label="BLEU" value="accuracy" v-if="scene==='MT'" />
                <el-radio-button label="COMET" value="comet" v-if="scene==='MT'" />
                <el-radio-button label="准确率" value="correct" v-if="scene==='ASR'" />
                <el-radio-button label="精确率" value="accuracy" v-if="scene==='ASR'" />
              </el-radio-group>
            </div>
          </div>
          <div style="height: 5px"></div>
          <div class="questionButtomTag" v-if="!isinterpretation && !isChildStudy">
            <el-button
              @click="filterByStatus('10')"
              :class="{
          highlight: TagKey === '10',
          questionCardButtom: true,
          buttom_undefine_color: true,
        }"
            >未标注</el-button>
            <el-button
              @click="filterByStatus('20')"
              :class="{
          highlight: TagKey === '20',
          questionCardButtom: true,
          button_success_color: true,
        }"
            >正确</el-button>
            <el-button
              @click="filterByStatus('30')"
              :class="{
          highlight: TagKey === '30',
          questionCardButtom: true,
          buttom_error_color: true,
        }"
            >错误</el-button>
          </div>
          <div class="questionButtomTag" v-else-if="isinterpretation">
            <el-button
              @click="filterByAccuracy('10')"
              :class="{
          highlight: TagKey === '10',
          questionCardButtom: true,
          lowAccuracyColor: true,
        }"
            >0~49</el-button>
            <el-button
              @click="filterByAccuracy('20')"
              :class="{
          highlight: TagKey === '20',
          questionCardButtom: true,
          middleAccuracyColor: true,
        }"
            >50~79</el-button>
            <el-button
              @click="filterByAccuracy('30')"
              :class="{
          highlight: TagKey === '30',
          questionCardButtom: true,
          highAccuracyColor: true,
        }"
            >80~100</el-button>
          </div>
          <div v-else>
            <div class="questionButtomTag">
              <el-button
                @click="filterByCategory('未标注')"
                :class="{
          highlight: TagKey === '未标注',
          questionCardButtom: true,
          buttom_undefine_color: true,
        }"
              >未标注</el-button>
              <el-button
                @click="filterByCategory('完全正确')"
                :class="{
          highlight: TagKey === '完全正确',
          questionCardButtom: true,
          button_success_color: true,
        }"
              >完全正确</el-button>
              <el-button
                @click="filterByCategory('错误')"
                :class="{
          highlight: TagKey === '错误',
          questionCardButtom: true,
          buttom_error_color: true,
        }"
              >错误</el-button>
            </div>
            <div style="margin-top: 10px;"></div>
            <div class="questionButtomTag">
              <!-- <el-button
                @click="filterByCategory('视距检测')"
                :class="{
          highlight: TagKey === '视距检测',
          questionCardButtom: true,
          buttom_error_color: true,
        }"
              >视距检测</el-button>-->
              <el-button
                @click="filterByCategory('注意力小类')"
                :class="{
          highlight: TagKey === '注意力小类',
          questionCardButtom: true,
          buttom_error_color: true,
        }"
              >注意力小类</el-button>
              <el-button
                @click="filterByCategory('坐姿小类')"
                :class="{
          highlight: TagKey === '坐姿小类',
          questionCardButtom: true,
          buttom_error_color: true,
        }"
              >坐姿小类</el-button>
              <!-- <el-button
                @click="filterByCategory('离座检测')"
                :class="{
          highlight: TagKey === '离座检测',
          questionCardButtom: true,
          buttom_error_color: true,
        }"
              >离座检测</el-button>-->
            </div>
          </div>

          <div class="ButtomCard">
            <div v-for="item in pagedQuestions" :key="item.index">
              <el-button
                :style="ButtonType(item)"
                v-if="item.choices.length > 1"
                @click="searchQuestion(item)"
                :class="{
                  highlight: selectedButtonIndex === item.index,
                  questionCardButtom: true
                }"
              >{{ typeof item.index === 'number' ? item.index + 1 : item.index }}</el-button>
              <!-- isGaixie场景：显示用例编号按钮，不遍历choices -->
              <div v-else-if="isGaixie">
                <el-button
                  :style="GaixieButtonType(item)"
                  @click="searchQuestion(item)"
                  :class="{
                    highlight: selectedButtonIndex === item.index,
                    questionCardButtom: true,
                  }"
                >{{ item.caseIndex + 1 }}</el-button>
              </div>
              <div v-else v-for="choice in item.choices">
                <el-button
                  v-if="
              !isinterpretation&&
              choice.review.result === true ||
              choice.review.result === 1 ||
              choice.review.result === '1'
              "
                  @click="searchQuestion(item)"
                  :class="{
              highlight: selectedButtonIndex === item.index,
              questionCardButtom: true,
              button_success_color: true,
              }"
                >{{ typeof item.index === 'number' ? item.index + 1 : item.index }}</el-button>
                <el-button
                  v-else-if="
              !isinterpretation&&
              choice.review.result === false ||
              choice.review.result === 0 ||
              choice.review.result === '0'
              "
                  @click="searchQuestion(item)"
                  :class="{
              highlight: selectedButtonIndex === item.index,
              questionCardButtom: true,
              buttom_error_color: true,
              }"
                >{{ typeof item.index === 'number' ? item.index + 1 : item.index }}</el-button>
                <el-button
                  v-else-if="!isinterpretation"
                  type="info"
                  @click="searchQuestion(item)"
                  :class="{
              highlight: selectedButtonIndex === item.index,
              questionCardButtom: true,
              }"
                >{{ typeof item.index === 'number' ? item.index + 1 : item.index }}</el-button>

                <el-button
                  v-if="
              isinterpretation&&
              choice.review[scoreType]<0.5
              "
                  @click="searchQuestion(item)"
                  :class="{
              highlight: selectedButtonIndex === item.index,
              questionCardButtom: true,
              lowAccuracyColor: true,
              }"
                >{{ typeof item.index === 'number' ? item.index + 1 : item.index }}</el-button>
                <el-button
                  v-else-if="
              isinterpretation&&
              choice.review[scoreType]>=0.5&&
              choice.review[scoreType]<0.8
              "
                  @click="searchQuestion(item)"
                  :class="{
              highlight: selectedButtonIndex === item.index,
              questionCardButtom: true,
              middleAccuracyColor: true,
              }"
                >{{ typeof item.index === 'number' ? item.index + 1 : item.index }}</el-button>
                <el-button
                  v-else-if="isinterpretation"
                  type="info"
                  @click="searchQuestion(item)"
                  :class="{
              highlight: selectedButtonIndex === item.index,
              questionCardButtom: true,
              highAccuracyColor: true,
              }"
                >{{ typeof item.index === 'number' ? item.index + 1 : item.index }}</el-button>
              </div>
            </div>
          </div>
          <el-pagination
            style="margin-top: 10px"
            size="small"
            layout="prev, pager, next"
            @current-change="pageChange"
            :current-page="currentPage"
            :page-count="page_count"
            hide-on-single-page
          ></el-pagination>
        </div>
      </div>
    </el-aside>
  </el-scrollbar>
  <el-main class="main">
    <!-- 锚点导航 -->
    <el-scrollbar class="gaixie-anchor" v-if="itemInfo.gaixieRounds?.length > 1">
      <el-affix :offset="10" style="margin-top:20px">
        <el-anchor :offset="20">
          <el-anchor-link
            v-for="(round, index) in itemInfo.gaixieRounds"
            :key="index"
            :href="'#gaixie-round-' + index"
          >
            <span>第{{ index + 1 }}轮问答：</span>
            <span
              :style="{ color: round.resultType === 'success' ? '#67c23a' : round.resultType === 'danger' ? '#f56c6c' : '#909399' }"
              v-if="round.resultType === 'success'"
            >✅</span>
            <span
              :style="{ color: round.resultType === 'success' ? '#67c23a' : round.resultType === 'danger' ? '#f56c6c' : '#909399' }"
              v-else
            >❌</span>
          </el-anchor-link>
        </el-anchor>
      </el-affix>
    </el-scrollbar>
    <el-scrollbar
      always
      :style="{ width: itemInfo.gaixieRounds?.length > 1 ? '87%' : '100%' }"
    >
      <div
        style="display: flex; gap: inherit; margin-top: 28px;"
        v-if="!isinterpretation && !isChildStudy || !isRuler2"
      >
        <div v-for="(choice, index) in itemInfo.choices">
          <!-- {{ choice }} -->
          <el-button
            v-if="
          choice.review.result === true ||
          choice.review.result === 1 ||
          choice.review.result === '1'
        "
            @click="detailQestion(choice, index)"
            :class="{
        highlight: subSelectedIndex === index,
        questionCardButtom: true,
        button_success_color: true,
        }"
            style="margin-left:10px"
          >回答：{{ index + 1 }}</el-button>
          <el-button
            v-else-if="
            choice.review.result === false ||
            choice.review.result === 0 ||
            choice.review.result === '0'
          "
            @click="detailQestion(choice, index)"
            :class="{
          highlight: subSelectedIndex === index,
          questionCardButtom: true,
          buttom_error_color: true,
        }"
            style="margin-left:10px"
          >回答：{{ index + 1 }}</el-button>
          <el-button
            v-else
            @click="detailQestion(choice, index)"
            :class="{
          highlight: subSelectedIndex === index,
          questionCardButtom: true,
          buttom_undefine_color: true,
        }"
            style="margin-left:10px"
          >回答：{{ index + 1 }}</el-button>
        </div>
      </div>
      <!-- isGaixie场景：左侧锚点导航 + 右侧多轮对话 -->
      <div
        v-if="isGaixie && itemInfo.gaixieRounds && itemInfo.gaixieRounds.length > 0"
        class="gaixie-flex"
      >
        <!-- 多轮对话内容 -->
        <div class="gaixie-rounds">
          <div
            v-for="(round, index) in itemInfo.gaixieRounds"
            :key="index"
            :id="'gaixie-round-' + index"
          >
            <div class="turnTitle">
              <!-- 第 {{ index + 1 }} 轮问答： -->
              系统Prompt：
              <el-button text size="small" @click="toggleContext(index)">
                <el-icon>
                  <ArrowDown v-if="!round.showContext" />
                  <ArrowUp v-else />
                </el-icon>
              </el-button>
            </div>
            <template v-if="round.showContext">
              <h1 class="title">系统提示词</h1>
              <el-input
                :model-value="round.prompt"
                type="textarea"
                :autosize="{ minRows: 1, maxRows: 10 }"
                placeholder="无"
              />
            </template>
            <h1 class="title">上下文</h1>
            <el-input
              :model-value="round.context"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              placeholder="无"
            />
            <h1 class="title">问题</h1>
            <el-input
              :model-value="round.question"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              placeholder="无"
            />
            <h1 class="title">改写结果</h1>
            <el-input
              :model-value="round.pred"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              placeholder="无"
            />
            <h1 class="title">助手回复</h1>
            <el-input
              :model-value="round.answer"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              placeholder="无"
            />
            <div style="display: flex; gap: 16px; align-items: center; margin: 8px 0;">
              <span>
                <strong>宽松判定结果：</strong>
                <el-tag :type="round.looseResult === '正确' ? 'success' : 'danger'" size="small">{{ round.looseResult || '未判定' }}</el-tag>
              </span>
            </div>
            <h1 class="title" v-if="round.looseReason">宽松判定原因</h1>
            <el-input
              v-if="round.looseReason"
              :model-value="round.looseReason"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              placeholder="无"
            />
            <div style="display: flex; gap: 16px; align-items: center; margin: 8px 0;">
              <span>
                <strong>严格判定结果：</strong>
                <el-tag :type="round.strictResult === '正确' ? 'success' : 'danger'" size="small">{{ round.strictResult || '未判定' }}</el-tag>
              </span>
            </div>
            <h1 class="title" v-if="round.strictReason">严格判定原因</h1>
            <el-input
              v-if="round.strictReason"
              :model-value="round.strictReason"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              placeholder="无"
            />
            <h1 class="title" v-if="round.tokenUsage">token统计</h1>
            <el-input
              v-if="round.tokenUsage"
              :model-value="round.tokenUsage"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              placeholder="无"
            />
            <div style="display: flex; gap: 16px; align-items: center; margin: 8px 0;">
              <!-- <span>
                <strong>判题结果：</strong>
                <el-tag :type="round.resultType" size="small">{{ round.resultLabel }}</el-tag>
              </span> -->
              <span v-if="round.responseTime">
                <strong>耗时(s):</strong>
                {{ round.responseTime }}
              </span>
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="turnQuestionsAnswer && turnQuestionsAnswer.length > 1">
        <div v-for="(item, index) in turnQuestionsAnswer" :key="index">
          <div class="turnTitle">第 {{ index + 1 }} 轮问答：</div>
          <h1 class="title">问题</h1>
          <el-input
            v-model="item.question"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 10 }"
            placeholder="无"
          />
          <h1 class="title">模型回答</h1>
          <el-input
            v-model="item.pred"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 10 }"
            placeholder="无"
          />
          <h1 class="title">参考答案</h1>
          <el-input
            v-model="item.answer"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 10 }"
            placeholder="无"
          />
        </div>
      </div>
      <div v-else>
        <!-- 意图对比表格 -->
        <template v-if="isYitu">
          <h1 class="title">意图对比</h1>
          <el-table :data="yituComparisonData" border style="width: 100%" stripe>
            <el-table-column prop="fieldName" label="字段" width="120" show-overflow-tooltip />
            <el-table-column
              prop="channel_A_expected"
              label="通道A预期回答"
              show-overflow-tooltip
            />
            <el-table-column prop="channel_A_pred" label="通道A模型回答" show-overflow-tooltip />
            <el-table-column label="通道A正确性" width="120">
              <template #default="{ row }">
                <el-tag
                  v-if="row.fieldName!='content'"
                  :type="row.channel_A_correct ? 'success' : 'danger'"
                >{{ row.channel_A_correct ? '正确' : '错误' }}</el-tag>
                <div v-else>-</div>
              </template>
            </el-table-column>
            <el-table-column
              prop="channel_B_expected"
              label="通道B预期回答"
              show-overflow-tooltip
            />
            <el-table-column prop="channel_B_pred" label="通道B模型回答" show-overflow-tooltip />
            <el-table-column label="通道B正确性" width="120">
              <template #default="{ row }">
                <el-tag
                  v-if="row.fieldName!='content'"
                  :type="row.channel_B_correct ? 'success' : 'danger'"
                >{{ row.channel_B_correct ? '正确' : '错误' }}</el-tag>
                <div v-else>-</div>
              </template>
            </el-table-column>
          </el-table>
        </template>
        <h1
          class="title"
          v-else-if="question_img_path"
        >图片--{{ question_img_path?.replaceAll("$", "/") ?? '无路径'}}</h1>
        <div v-if="question_img_path" style="display: flex; justify-content: flex-start;">
          <el-image
            :src="`${API_BASE_URL}image/view/${selectValue}/${question_img_path}`"
            :preview-src-list="[`${API_BASE_URL}image/view/${selectValue}/${question_img_path}`]"
            hide-on-click-modal
            fit="contain"
            class="preview-image"
          />
        </div>
        <h1 class="title" v-if="question_audio_path">音频</h1>
        <div v-if="question_audio_path">
          <audio
            :src="question_audio_path"
            controls
            controlslist="nodownload noplaybackrate"
            style="margin-bottom: 10px"
          ></audio>
        </div>
        <!-- skill提参：上下文展示在“问题”前 -->
        <h1 class="title" v-if="isSkill">上下文</h1>
        <el-input
          v-if="isSkill"
          :model-value="skillContext"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <h1 class="title" v-if="isCoordinator">上下文</h1>
        <el-input
          v-if="isCoordinator"
          :model-value="coordContext"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <h1 class="title" v-if="!isinterpretation">问题</h1>
        <h1 class="title" v-if="scene==='ASR'">音频语料</h1>
        <h1 class="title" v-if="scene==='MT'">源语言</h1>
        <h1 class="title" v-if="scene==='TTS'">问题</h1>
        <el-input
          v-model="question"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <template v-if="isValidJSON && isChildStudy ">
          <h1 class="title">测评结果</h1>
          <el-table :data="comparisonData" border style="width: 100%" stripe>
            <el-table-column prop="key" label="属性名" width="180" />
            <el-table-column prop="refValue" label="参考答案值" show-overflow-tooltip />
            <el-table-column prop="modelValue" label="模型答案值" show-overflow-tooltip />
            <el-table-column label="是否正确">
              <template #default="{ row }">
                <el-tag
                  :type="row.isCorrect ? 'success' : 'danger'"
                >{{ row.isCorrect ? '正确' : '错误' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </template>

        <!-- 当JSON解析失败时显示原始文本域 -->
        <template v-else>
          <template v-if="!isYitu">
            <h1 class="title">模型回答</h1>
            <el-input
              v-model="pred"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              placeholder="无"
            />
            <h1 class="title">参考答案</h1>
            <el-input
              v-model="answer"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              placeholder="无"
            />
            <h1 class="title" v-if="isMemory">评测回答</h1>
            <el-input
              v-model="judge_result"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 10 }"
              placeholder="无"
              v-if="isMemory"
            />
          </template>
        </template>
      </div>
      <h1 class="title" v-if="scene==='ASR'">准确率/精确率</h1>
      <h1 class="title" v-if="scene==='MT'">BLEU/COMET</h1>
      <h1 class="title" v-if="scene==='TTS'">准确率/MOS</h1>
      <el-input
        v-model="accuracy"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 10 }"
        placeholder="请输入准确率"
        v-if="isinterpretation"
      />

      <h1
        class="title"
        v-if="(!isinterpretation && is_llmjudge) || isBanxue || isGUI"
      >裁判模型结果</h1>
      <div v-if="is_llmjudge || isBanxue || isGUI">
        <el-input
          v-model="judge_result"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
          v-if="!isinterpretation"
        />
      </div>
      <h1 class="title" v-if="!isinterpretation && !isGaixie">判题结果</h1>
      <el-input
        :model-value="resultDisplay"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 10 }"
        placeholder="无"
        v-if="!isinterpretation && !isGaixie"
      />
      <!-- 意图场景：两个通道的模型原始输出 -->
      <template v-if="isYitu">
        <h1 class="title">通道A模型原始输出</h1>
        <el-input
          v-model="channelA_output"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 15 }"
          placeholder="无"
        />
        <h1 class="title">通道B模型原始输出</h1>
        <el-input
          v-model="channelB_output"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 15 }"
          placeholder="无"
        />
      </template>
      <template v-else-if="!isGaixie">
        <h1 v-if="correctAnwser || isinterpretation || isChildStudy" class="title">模型原始输出</h1>
        <el-input
          v-if="correctAnwser || isinterpretation || isChildStudy"
          v-model="content"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
      </template>
      <h1 class="title" v-if="!isinterpretation && !isGaixie">token统计</h1>
      <el-input
        v-model="tokenUsage"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 10 }"
        placeholder="无"
        v-if="!isinterpretation && !isGaixie"
      />
      <h1 class="title" v-if="!isinterpretation && !isGaixie">耗时(s):</h1>
      <el-input
        v-model="executionTime"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 10 }"
        placeholder="无"
        v-if="!isinterpretation && !isGaixie"
      />
      <!-- skill提参：Excel 用例信息展示在“耗时”后 -->
      <h1 class="title" v-if="isSkill">Excel信息</h1>
      <el-input
        v-if="isSkill"
        :model-value="skillExcelInfo"
        type="textarea"
        :autosize="{ minRows: 3, maxRows: 15 }"
        placeholder="无"
      />
      <!-- Coordinator场景：上下文 + 四个属性独立展示框（JSON 美化） -->
      <template v-if="isCoordinator">
        <h1 class="title">memory_location_time</h1>
        <el-input
          :model-value="coordMemory"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <h1 class="title">user_input</h1>
        <el-input
          :model-value="coordUserInput"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <h1 class="title">assistant_skill_select</h1>
        <el-input
          :model-value="coordSkillSelect"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <h1 class="title">tools</h1>
        <el-input
          :model-value="coordTools"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
      </template>
      <!-- 改写场景：结果 Excel 列信息独立展示框（宽松/严格双规则四项） -->
      <template v-if="isGaixie">
        <!-- <h1 class="title">宽松判定结果</h1>
        <el-input
          :model-value="rewriteLooseResult"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <h1 class="title">宽松判定原因</h1>
        <el-input
          :model-value="rewriteLooseReason"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <h1 class="title">严格判定结果</h1>
        <el-input
          :model-value="rewriteStrictResult"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <h1 class="title">严格判定原因</h1>
        <el-input
          :model-value="rewriteStrictReason"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        /> -->
        <h1 class="title">要求关键字</h1>
        <el-input
          :model-value="rewriteRequiredKeywords"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <h1 class="title">命中关键字</h1>
        <el-input
          :model-value="rewriteMatchedKeywords"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <h1 class="title">缺失关键字</h1>
        <el-input
          :model-value="rewriteMissingKeywords"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <h1 class="title">黑名单词</h1>
        <el-input
          :model-value="rewriteBlacklistTerms"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
        <h1 class="title">命中黑名单</h1>
        <el-input
          :model-value="rewriteHitBlacklist"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 10 }"
          placeholder="无"
        />
      </template>
      <div v-if="is_llmjudge">
        <h1 class="title">打分</h1>
        <el-slider
          v-model="input3"
          :step="0.1"
          max="10"
          :mark="marks"
          show-stops
          show-input
        ></el-slider>
        <el-button v-if="canEvaluate" type="primary" @click="submitScoreUpdate">提交分数</el-button>
      </div>
      <div v-else-if="!isinterpretation && !isChildStudy && !isRuler2">
        <h1 class="title" style="margin-right: 20px">手动修改结果</h1>
        <el-radio v-model="input3" :label="1">对</el-radio>
        <el-radio v-model="input3" :label="0">错</el-radio>
        <el-button v-if="canEvaluate" type="primary" @click="submitScoreUpdate">提交修改</el-button>
      </div>
      <h1 class="title" v-if="!isinterpretation && !isChildStudy && !isRuler2">备注</h1>
      <el-input
        v-model="note"
        type="textarea"
        :disabled="true"
        :autosize="{ minRows: 1, maxRows: 10 }"
        placeholder="无"
        v-if="!isinterpretation && !isChildStudy && !isRuler2"
      />
      <h1 class="title" v-if="isinterpretation">问题分类</h1>
      <el-select v-model="questionType" placeholder="请选择问题分类" v-if="isinterpretation"></el-select>
      <h1 class="title" v-if="isinterpretation">问题描述</h1>
      <el-input
        v-model="description"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 10 }"
        placeholder="请输入问题描述"
        v-if="isinterpretation"
      />
    </el-scrollbar>
  </el-main>
</el-container>
</template>

<script lang="ts" setup>
import {useEvaluationAccess} from '@/evaluationAccess';
const {canEvaluate}=useEvaluationAccess();
import { ref, computed, watch, onMounted } from "vue";
import {
  ArrowDown,
  ArrowUp,
  QuestionFilled,
} from "@element-plus/icons-vue";
import { ElMessage, ElLoading } from "element-plus";
import { getResult, updateResult } from "@/api/runService.js";
import { API_BASE_URL } from "@/utils/Constants.js";
import {
  checkAllDatasetsTag,
  computeIsChildStudy,
  computeIsInterpretation,
} from "./assessmentSharedUtils";

const props = defineProps({
  task: { type: Object, default: () => ({}) },
  datasets: { type: Object, default: () => ({}) },
  assessmentType: { type: String, default: "" },
  selectValue: { type: String, default: "" },
  selectSubValue: { type: String, default: "" },
  scene: { type: String, default: "" },
  pageSize: { type: Number, default: 50 },
  isLLMJudge: { type: Boolean, default: false },
  taskId: { type: String, default: "" },
  modelId: { type: String, default: "" },
});

const Result = defineModel("result", { type: Array, default: () => [] });

const note = ref("");
const question = ref("");
const question_img_path = ref("");
const question_audio_path = ref("");
const answer = ref("");
const result = ref("");
const pred = ref("");
const judge_result = ref("");
const turnQuestionsAnswer = ref([]);
const content = ref("");
const channelA_output = ref("");
const channelB_output = ref("");
const tokenUsage = ref("");
const executionTime = ref("");
// skill提参 场景：上下文与 Excel 用例信息展示
const skillContext = ref("");
const skillExcelInfo = ref("");
// Coordinator 场景：上下文 + 四个独立展示框（字符串 JSON 美化）
const coordContext = ref("");
const coordMemory = ref("");
const coordUserInput = ref("");
const coordSkillSelect = ref("");
const coordTools = ref("");
// 改写场景：结果 Excel 列信息独立展示框（宽松/严格双规则四项）
const rewriteLooseResult = ref("");
const rewriteLooseReason = ref("");
const rewriteStrictResult = ref("");
const rewriteStrictReason = ref("");
const rewriteRequiredKeywords = ref("");
const rewriteMatchedKeywords = ref("");
const rewriteMissingKeywords = ref("");
const rewriteBlacklistTerms = ref("");
const rewriteHitBlacklist = ref("");
const input3 = ref("");
const currentPage = ref(1);
const page_count = ref(1);
const is_llmjudge = computed(() => props.isLLMJudge);
const selectedButtonIndex = ref(-1);
const subSelectedIndex = ref(0);
const selectedId = ref("");
const TagKey = ref("00");
const correctAnwser = ref(false);
const marks = ref({
  0: 0,
  2: 2,
  5: 5,
  8: {
    style: {
      color: "#1989FA",
    },
  },
});
const filterStatus = ref("all");
const scoreType = ref();
const pagedQuestions = ref([]);
const itemInfo = ref([]);
const questionType = ref("");
const description = ref("");
const accuracy = ref();
const studyStatusMap = {
  attention_status: "注意力大类",
  attention_category: "注意力小类",
  // distance_status: "视距检测",
  sitting_posture_status: "坐姿大类",
  sitting_posture_category: "坐姿小类",
  // seat_status: "离座检测",
};

// 归一化判定结果：兼容布尔/数字/字符串等多种存储类型（如 "1"/1/true、"0"/0/false）
function isCorrectResult(v) {
  return v === true || v === 1 || v === "1" || v === "true";
}

function isWrongResult(v) {
  return v === false || v === 0 || v === "0" || v === "false";
}

function isUnlabeledResult(v) {
  return !isCorrectResult(v) && !isWrongResult(v);
}

const question_item = ref({
  default: ["Question"],
  aime24: ["problem"],
  aime25: ["question"],
  ifeval: ["prompt"],
  live_code_bench: ["question_content"],
  humaneval: ["prompt"],
  bfcl_v3: ["turns"],
  gpqa: ["Question"],
  aisf_intent: ["Input"],
  math_500: ["problem"],
  mmlu: ["input", "A", "B", "C", "D"],
  box_tool_use: ["Question"],
  om_task: ["Question"],
  service_emotion: ["Question"],
  service_intent: ["input"],
  service_parameter_extract: ["messages"],
  service_style: ["Question"],
  service_tool_select: ["messages"],
  aisf_intent_dev: ["query"],
  aisf_extract: ["column1"],
  box_call: ["Question"],
  aisf_box: ["user_prompt"],
  aisf_box_dev: ["user_prompt"],
  aisf_box_tool_dev: ["user_prompt"],
  aisf_tool_box_dev: ["user_prompt"],
  aisf_classify_box_dev: ["query"],
  aisf_box_classify_dev: ["query"],
  aisf_perception_planning: ["Input"],
  aisf_intent_category: ["Input"],
  aisf_vla: ["tasks", "instructions"],
});

const anwser_item = ref({
  default: "Answer",
  aime24: "answer",
  aime25: "answer",
  ifeval: "answer",
  humaneval: "canonical_solution",
  gpqa: "answer",
  math_500: "answer",
  mmlu: "target",
  live_code_bench: "public_test_cases",
  bfcl_v3: "ground_truth",
  aisf_intent: "Test answer",
  box_tool_use: "Answer",
  om_task: "answer",
  service_emotion: "Answer",
  service_intent: "output",
  service_parameter_extract: "messages",
  service_style: "Answer",
  service_tool_select: "messages",
  aisf_intent_dev: "任务类型",
  aisf_extract: "column3",
  box_call: "Answer",
  aisf_perception_planning: "Test answer",
  aisf_intent_category: "Test answer",
});

const extra_item = ref({
  gpqa: ["Correct Answer", "", "", ""],
});

const isinterpretation = computed(() =>
  computeIsInterpretation(props.assessmentType)
);

const isChildStudy = computed(() =>
  computeIsChildStudy(props.task, props.datasets)
);

const isYitu = computed(() => checkAllDatasetsTag(props.task, props.datasets, "意图"));
const isMemory = computed(() => checkAllDatasetsTag(props.task, props.datasets, "记忆"));
const isGaixie = computed(() => checkAllDatasetsTag(props.task, props.datasets, "改写"));
const isSkill = computed(() => checkAllDatasetsTag(props.task, props.datasets, "skill提参"));
const isGUI = computed(() => checkAllDatasetsTag(props.task, props.datasets, "GUI提参"));
const isBanxue = computed(() => checkAllDatasetsTag(props.task, props.datasets, "伴学提参"));
const isCoordinator = computed(() => checkAllDatasetsTag(props.task, props.datasets, "Coordinator"));

const isRuler2 = computed(() => {
  return (
    isYitu ||
    isMemory ||
    isGaixie ||
    isSkill ||
    isGUI ||
    isBanxue ||
    isCoordinator
  );
});

const setScoreType = () => {
  switch (props.scene) {
    case "ASR":
      scoreType.value = "accuracy";
      break;
    case "MT":
      scoreType.value = "comet";
      break;
    case "TTS":
      scoreType.value = "accuracy";
      break;
    default:
      scoreType.value = "";
  }
};

watch(() => props.scene, setScoreType, { immediate: true });

const pageChange = async (val) => {
  currentPage.value = val;
  const start = (val - 1) * props.pageSize;
  const end = val * props.pageSize;
  const page_num = `${start},${end}`;
  if (props.selectValue === "live_code_bench") {
    const loading = ElLoading.service({
      lock: true,
      text: "卖力加载中...",
    });
    await getResult({
      task_id: props.taskId,
      model_id: props.modelId,
      page: page_num,
      dataset: props.selectValue,
      subset: "",
      assessmentType: props.scene,
    }).then((res) => {
      loading.close();
      try {
        if (res.data.result.length < 1) {
          ElMessage({
            type: "error",
            message: "暂无数据",
          });
          return;
        }
      } catch {
        ElMessage({
          type: "error",
          message: "暂无数据",
        });
        return;
      }
      Result.value = res.data.result;
      page_count.value = res.data.page_count;
      if (isGaixie.value) {
        const grouped = groupGaixieData(Result.value);
        if (grouped.length > 0) {
          searchQuestion(grouped[0]);
        }
      } else {
        searchQuestion(
          Result.value.sort((a, b) => {
            return a.index - b.index;
          })[0]
        );
      }
    });
    loading.close();
  } else {
    const allData = filteredQuestions.value;
    page_count.value = Math.ceil(allData.length / props.pageSize) || 1;
    pagedQuestions.value = allData.slice(start, end);
  }
};

const ButtonType = computed(() => (item) => {
  // 意图场景：双通道都正确才绿色，任一错误则红色
  if (isYitu.value) {
    const allCorrect = item.choices.every((c) => isCorrectResult(c.review.result));
    const anyEmpty = item.choices.some(
      (c) =>
        c.review.result === "" ||
        c.review.result === undefined ||
        c.review.result === null
    );
    if (anyEmpty) return { "background-color": "#909399" };
    return allCorrect
      ? { "background-color": "rgb(160, 207, 255)" }
      : { "background-color": "rgb(250, 182, 182)" };
  }
  if (item.choices.some((choice) => isUnlabeledResult(choice.review.result)))
    return { "background-color": "#909399" };
  return item.choices.some((choice) => isWrongResult(choice.review.result))
    ? { "background-color": "rgb(250, 182, 182)" }
    : { "background-color": "rgb(160, 207, 255)" };
});

// Gaixie按钮颜色：全部正确为绿色，有错误为红色，未标注为灰色
const GaixieButtonType = computed(() => (item) => {
  if (!item.gaixieAllCorrect && !item.gaixieAnyWrong) {
    return { "background-color": "#909399", color: "#ffffff" };
  }
  return item.gaixieAllCorrect
    ? { "background-color": "rgb(160, 207, 255)" }
    : { "background-color": "rgb(250, 182, 182)" };
});

const detailQestion = (choice, index) => {
  subSelectedIndex.value = index;
  pred.value = formatDisplayJSON(choice.review.pred);
  judge_result.value = formatDisplayJSON(choice.review.judge_result);
  content.value = formatDisplayJSON(choice.message.content);
  result.value = choice.review.result;
  // console.log("answer.value", answer.value);
  if (!answer.value || answer.value === undefined) {
    answer.value = formatDisplayJSON(choice.review.gold);
  }
  if (
    result.value === true ||
    result.value === 1 ||
    result.value === "true" ||
    result.value === "1"
  ) {
    correctAnwser.value = false;
  } else {
    correctAnwser.value = true;
  }
};

function get_mllm_res_path(item) {
  const cur_img_path = item.raw_input["img"];
  if (cur_img_path) {
    if (cur_img_path.includes("\\")) {
      question_img_path.value = cur_img_path.replaceAll("\\", "$");
    } else if (cur_img_path.includes("/")) {
      question_img_path.value = cur_img_path.replaceAll("/", "$");
    } else {
      console.error("not find / or \\, cur_img_path", cur_img_path);
    }
  }
  console.log("question_img_path", question_img_path.value);
  if (question_img_path.value) return;
  const cur_audio_path = item.raw_input["audio"];
  if (cur_audio_path) {
    if (cur_audio_path.includes("\\")) {
      question_audio_path.value = cur_audio_path.replaceAll("\\", "$");
    } else if (cur_audio_path.includes("/")) {
      question_audio_path.value = cur_audio_path.replaceAll("/", "$");
    } else {
      console.error("not find / or \\, cur_audio_path", cur_audio_path);
    }
  }
  console.log("question_audio_path", question_audio_path.value);
}

const searchQuestion = (item) => {
  console.log("item");
  console.log(item);
  question.value = "";
  answer.value = "";
  pred.value = "";
  judge_result.value = "";
  content.value = "";
  result.value = "";
  selectedId.value = "";
  subSelectedIndex.value = 0;
  selectedButtonIndex.value = item.index;
  itemInfo.value = item;
  selectedId.value = item.answer_id;
  // skill提参 场景：上下文与 Excel 用例信息（前端 JSON 展示前统一格式化）
  skillContext.value = item.raw_input?.context
    ? String(item.raw_input.context)
    : "";
  skillExcelInfo.value = item.excel_info
    ? JSON.stringify(item.excel_info, null, 2)
    : "";
  // Coordinator 场景：上下文 + 四个独立展示框（字符串 JSON 美化）
  coordContext.value = item.raw_input?.context
    ? String(item.raw_input.context)
    : "";
  const coordInfo = item.excel_info || {};
  coordMemory.value = formatDisplayJSON(coordInfo.memory_location_time);
  coordUserInput.value = formatDisplayJSON(coordInfo.user_input);
  coordSkillSelect.value = formatDisplayJSON(coordInfo.assistant_skill_select);
  coordTools.value = formatDisplayJSON(coordInfo.tools);
  // 改写场景：结果 Excel 列信息（宽松判定结果/原因 + 严格判定结果/原因 + 关键字/黑名单）
  const rewriteInfo = item.excel_info || {};
  rewriteLooseResult.value = formatDisplayJSON(rewriteInfo["宽松判定结果"]);
  rewriteLooseReason.value = formatDisplayJSON(rewriteInfo["宽松判定原因"]);
  rewriteStrictResult.value = formatDisplayJSON(rewriteInfo["严格判定结果"]);
  rewriteStrictReason.value = formatDisplayJSON(rewriteInfo["严格判定原因"]);
  rewriteRequiredKeywords.value = formatDisplayJSON(rewriteInfo["要求关键字"]);
  rewriteMatchedKeywords.value = formatDisplayJSON(rewriteInfo["命中关键字"]);
  rewriteMissingKeywords.value = formatDisplayJSON(rewriteInfo["缺失关键字"]);
  rewriteBlacklistTerms.value = formatDisplayJSON(rewriteInfo["黑名单词"]);
  rewriteHitBlacklist.value = formatDisplayJSON(rewriteInfo["命中黑名单"]);
  // isGaixie场景：使用gaixieRounds展示多轮对话（每轮含完整信息），跳过原有逻辑
  if (isGaixie.value && item.gaixieRounds) {
    turnQuestionsAnswer.value = [];
    question.value = "";
    pred.value = "";
    answer.value = "";
    content.value = "";
    tokenUsage.value = "";
    executionTime.value = "";
    result.value = item.gaixieAllCorrect
      ? "true"
      : item.gaixieAnyWrong
      ? "false"
      : "未标注";
    if (item.gaixieAllCorrect) {
      correctAnwser.value = false;
    } else {
      correctAnwser.value = true;
    }
    return;
  }
  if (item.raw_input.turns && item.raw_input.turns.length > 0) {
    console.log("有turns！！！");
    const turns = item.raw_input.turns;
    const turnQuestions = turns.map((item, index) => {
      if (index === 0) {
        return item[1].content;
      } else {
        return item[0].content;
      }
    });
    question.value = turnQuestions;
    const ans =
      anwser_item.value[props.selectValue] || anwser_item.value.default;
    answer.value = item.raw_input[ans];
    pred.value = item.choices[0].review.pred;
    judge_result.value = item.choices[0].review.judge_result.value;

    turnQuestionsAnswer.value = question.value.map((q, index) => ({
      question: q,
      pred: pred.value[index],
      judge_result: judge_result.value,
      answer:
        answer.value && answer.value.length > 0 ? answer.value[index] : "",
    }));
  } else {
    const qs =
      question_item.value[props.selectValue] || question_item.value.default;
    const lines = qs.map((element) => {
      return formatDisplayJSON(item.raw_input[element]);
    });
    question.value = lines.join("\n");
    get_mllm_res_path(item);
    const ans =
      anwser_item.value[props.selectValue] || anwser_item.value.default;
    answer.value = formatDisplayJSON(item.raw_input[ans]);
    if (!question.value || question.value === undefined + "\n") {
      question.value = item.parsed_request?.messages.filter(
        (e) => e.role === "user"
      )[0].content;
    }
    pred.value = formatDisplayJSON(item.choices[0].review.pred);
    judge_result.value = formatDisplayJSON(item.choices[0].review.judge_result);
  }
  const ct = item.choices[0].message.content;
  if (ct) {
    content.value = formatDisplayJSON(ct);
  }
  // 意图场景下记录两个通道的原始输出
  if (item.choices.length >= 2) {
    channelA_output.value = formatDisplayJSON(item.choices[0].message.content) || "";
    channelB_output.value = formatDisplayJSON(item.choices[1].message.content) || "";
  }
  answer.value = formatDisplayJSON(item.choices[0].review.gold);
  // 意图场景：判题结果基于两个通道，都正确才算正确
  if (isYitu.value && item.choices.length >= 2) {
    const allCorrect = item.choices.every(
      (c) =>
        c.review.result === true ||
        c.review.result === 1 ||
        c.review.result === "1"
    );
    result.value = allCorrect ? "true" : "false";
  } else {
    // 保存原始判题结果（可能是数字/字符串/对象），展示时统一格式化
    const rawResult = item.choices[0].review.result;
    result.value =
      rawResult === undefined || rawResult === null ? "" : rawResult;
  }
  let usage = item.usage;
  if (usage?.total_tokens) {
    tokenUsage.value =
      "总token数:\t" +
      JSON.stringify(usage.total_tokens) +
      "\n" +
      "输入token数:\t" +
      JSON.stringify(usage.prompt_tokens) +
      "\n" +
      "输出token数:\t" +
      JSON.stringify(usage.completion_tokens);
  }
  executionTime.value = JSON.stringify(item.response_time);
  if (
    result.value === true ||
    result.value === 1 ||
    result.value === "true" ||
    result.value === "1"
  ) {
    correctAnwser.value = false;
  } else {
    correctAnwser.value = true;
  }
  if (!props.scene) {
    return;
  }
  switch (props.scene) {
    case "ASR":
      accuracy.value =
        (item.choices[0].review.correct * 100).toFixed(2) +
        "/" +
        (item.choices[0].review.accuracy * 100).toFixed(2);
      break;
    case "MT":
      accuracy.value =
        (item.choices[0].review.accuracy * 100).toFixed(2) +
        "/" +
        (item.choices[0].review.comet * 100).toFixed(2);
      break;
    case "TTS":
      accuracy.value =
        (item.choices[0].review.accuracy * 100).toFixed(2) +
        "/" +
        (item.choices[0].review.mos * 100).toFixed(2);
      break;
  }
};

const filterByStatus = (status) => {
  if (filterStatus.value === status) {
    TagKey.value = "00";
    filterStatus.value = "all";
  } else {
    TagKey.value = status;
    filterStatus.value = status;
  }
  pageChange(1);
  // console.log('pagedQuestions')
  // console.log(pagedQuestions.value)
};

const filterByAccuracy = (accuracy) => {
  if (filterStatus.value === accuracy) {
    TagKey.value = "00";
    filterStatus.value = "all";
  } else {
    TagKey.value = accuracy;
    filterStatus.value = accuracy;
  }
  pageChange(1);
};

const filterByCategory = (status) => {
  console.log("Result");
  console.log(Result.value);
  if (filterStatus.value === status) {
    TagKey.value = "00";
    filterStatus.value = "all";
  } else {
    TagKey.value = status;
    filterStatus.value = status;
  }
  pageChange(1);
};

const submitScoreUpdate = async () => {
  if (input3.value === "") {
    ElMessage({
      type: "error",
      message: "请填写手动修改的分数或对错",
    });
  }
  const loading = ElLoading.service({
    lock: true,
    text: "卖力加载中...",
  });
  await updateResult({
    task_id: props.taskId,
    dataset: props.selectValue,
    sub_dataset: props.selectSubValue,
    answer_id: selectedId.value,
    index: selectedButtonIndex.value,
    result: input3.value,
  })
    .then((res) => {
      ElMessage({
        type: "success",
        message: "修改成功！",
      });
      loading.close();
      Result.value.forEach((element) => {
        if (element.answer_id === selectedId.value) {
          element.choices.forEach((choice) => {
            if (choice.index === subSelectedIndex.value) {
              result.value = input3.value;
              choice.review.result = input3.value;
            }
          });
        }
      });
    })
    .catch((err) => {
      ElMessage({
        type: "error",
        message: "修改失败！",
      });
    });
  loading.close();
};

const filteredQuestions = computed(() => {
  // isGaixie场景：先按用例分组再过滤
  if (isGaixie.value) {
    const grouped = groupGaixieData(Result.value);
    if (filterStatus.value === "10") {
      return grouped.filter((q) => !q.gaixieAllCorrect && !q.gaixieAnyWrong);
    } else if (filterStatus.value === "20") {
      return grouped.filter((q) => q.gaixieAllCorrect);
    } else if (filterStatus.value === "30") {
      return grouped.filter((q) => q.gaixieAnyWrong);
    }
    return grouped;
  }
  if (!isinterpretation.value && !isChildStudy.value) {
    // console.log("！！！isinterpretation");
    if (filterStatus.value === "10") {
      return Result.value.filter((q) =>
        q.choices.some((choice) => isUnlabeledResult(choice.review.result))
      );
    } else if (filterStatus.value === "20") {
      return Result.value.filter((q) =>
        q.choices.every((choice) => isCorrectResult(choice.review.result))
      );
    } else if (filterStatus.value === "30") {
      return Result.value.filter((q) =>
        q.choices.some((choice) => isWrongResult(choice.review.result))
      );
    }
    return Result.value.sort((a, b) => {
      return a.index - b.index;
    });
  } else if (isinterpretation.value) {
    if (filterStatus.value === "10") {
      return Result.value.filter((item) => {
        return (
          // item.choices[0].review[scoreType.value] >= 0 &&
          item.choices[0].review[scoreType.value] < 0.5
        );
      });
    } else if (filterStatus.value === "20") {
      return Result.value.filter((item) => {
        return (
          item.choices[0].review[scoreType.value] >= 0.5 &&
          item.choices[0].review[scoreType.value] < 0.8
        );
      });
    } else if (filterStatus.value === "30") {
      return Result.value.filter((item) => {
        return (
          item.choices[0].review[scoreType.value] >= 0.8 &&
          item.choices[0].review[scoreType.value] <= 1
        );
      });
    }
    return Result.value.sort((a, b) => {
      return a.index - b.index;
    });
  } else {
    if (filterStatus.value === "未标注") {
      return Result.value.filter((q) =>
        q.choices.some(
          (choice) =>
            isWrongResult(choice.review.result) &&
            choice.review.pred.attention_category === "未知"
        )
      );
    } else if (filterStatus.value === "完全正确") {
      return Result.value.filter((q) =>
        q.choices.every((choice) => isCorrectResult(choice.review.result))
      );
    } else if (filterStatus.value === "错误") {
      return Result.value.filter((q) =>
        q.choices.some((choice) => isWrongResult(choice.review.result))
      );
    } else if (filterStatus.value === "注意力小类") {
      return Result.value.filter((q) =>
        q.choices.some(
          (choice) =>
            isWrongResult(choice.review.result) &&
            !choice.review.gold.attention_category
              .split(/[，,]/)
              .includes(choice.review.pred.attention_category)
        )
      );
    } else if (filterStatus.value === "视距检测") {
      return Result.value.filter((q) =>
        q.choices.some(
          (choice) =>
            isWrongResult(choice.review.result) &&
            !choice.review.gold.distance_status
              .split(/[，,]/)
              .includes(choice.review.pred.distance_status)
        )
      );
    } else if (filterStatus.value === "坐姿小类") {
      return Result.value.filter((q) =>
        q.choices.some(
          (choice) =>
            isWrongResult(choice.review.result) &&
            !choice.review.gold.sitting_posture_category
              .split(/[，,]/)
              .includes(choice.review.pred.sitting_posture_category)
        )
      );
    } else if (filterStatus.value === "离座检测") {
      return Result.value.filter((q) =>
        q.choices.some(
          (choice) =>
            isWrongResult(choice.review.result) &&
            !choice.review.gold.seat_status
              .split(/[，,]/)
              .includes(choice.review.pred.seat_status)
        )
      );
    }
    return Result.value.sort((a, b) => {
      return a.index - b.index;
    });
  }
});

// 判题结果可能为数字/字符串/对象，统一格式化后完整展示
const resultDisplay = computed(() => {
  const val = result.value;
  if (val === undefined || val === null || val === "") return "";
  if (typeof val === "object") return JSON.stringify(val, null, 2);
  if (typeof val === "string") {
    try {
      const parsed = JSON.parse(val);
      if (typeof parsed === "object" && parsed !== null) {
        return JSON.stringify(parsed, null, 2);
      }
      return String(parsed);
    } catch {
      return val;
    }
  }
  return String(val);
});

const isValidJSON = computed(() => {
  try {
    // 两个JSON都需要能成功解析且是对象类型
    const predObj = JSON.parse(pred.value);
    const answerObj = JSON.parse(answer.value);
    return (
      typeof predObj === "object" &&
      typeof answerObj === "object" &&
      predObj !== null &&
      answerObj !== null
    );
  } catch (e) {
    return false;
  }
});

// 生成表格数据
const comparisonData = computed(() => {
  if (!isValidJSON.value) return [];

  try {
    const modelAnswer = JSON.parse(pred.value);
    const refAnswer = JSON.parse(answer.value);

    // 获取需要显示的键（按studyStatusMap的顺序）
    const orderedKeys = Object.keys(studyStatusMap);

    return orderedKeys.map((key) => {
      // 获取中文属性名
      const chineseKey = studyStatusMap[key];
      // 获取参考答案值（如果不存在则显示空字符串）
      const refValue =
        refAnswer[key] !== undefined ? formatValue(refAnswer[key]) : "";
      // 获取模型答案值（如果不存在则显示空字符串）
      const modelValue =
        modelAnswer[key] !== undefined ? formatValue(modelAnswer[key]) : "";

      return {
        key: chineseKey, // 使用中文属性名
        refValue,
        modelValue,
        isCorrect: refValue.split(/[，,]/).includes(modelValue),
      };
    });
  } catch (e) {
    return [];
  }
});

// 解析可能的JSON/Python风格字符串（兼容单引号、True/False/None）
function parseJsonArray(val) {
  if (!val) return [];
  if (Array.isArray(val)) return val;
  if (typeof val === "object") return [val];
  try {
    // 先尝试标准 JSON 解析
    const parsed = JSON.parse(val);
    return Array.isArray(parsed) ? parsed : [parsed];
  } catch (e) {
    // JSON解析失败，尝试兼容 Python 风格字符串（单引号, True/False/None）
    try {
      let normalized = val
        .replace(/True/g, "true")
        .replace(/False/g, "false")
        .replace(/None/g, "null");
      // 将单引号替换为双引号
      normalized = normalized.replace(/'/g, '"');
      const parsed = JSON.parse(normalized);
      return Array.isArray(parsed) ? parsed : [parsed];
    } catch (e2) {
      return [];
    }
  }
}

// 意图对比表格数据
const yituComparisonData = computed(() => {
  const item = itemInfo.value;
  if (!item || !item.choices || item.choices.length < 2) return [];

  try {
    // choices[0] = tunnel_A, choices[1] = tunnel_B
    const choiceA = item.choices[0];
    const choiceB = item.choices[1];

    // 预期回答从 raw_input 中取（更语义化）
    const expectedA = parseJsonArray(item.raw_input.expected_A);
    const expectedB = parseJsonArray(item.raw_input.expected_B);
    // 模型预测从 review.pred 中取
    const predA = parseJsonArray(choiceA.review.pred);
    const predB = parseJsonArray(choiceB.review.pred);

    function joinFields(arr, field) {
      if (!arr || arr.length === 0) return "无";
      const values = arr.map((item) =>
        item[field] !== undefined ? String(item[field]) : "无"
      );
      return values.join("; ");
    }

    function arraysMatchByField(expected, pred, field) {
      if ((!expected || expected.length === 0) && (!pred || pred.length === 0))
        return true;
      if (!expected || !pred || expected.length !== pred.length) return false;
      return expected.every((exp, idx) => {
        const p = pred[idx] || {};
        return (
          String(exp[field]).toLowerCase() === String(p[field]).toLowerCase()
        );
      });
    }

    const result = [];

    const fields = [
      { key: "skill_name", label: "skill_name" },
      { key: "content", label: "content" },
      { key: "depends_on", label: "depends_on" },
    ];

    for (const field of fields) {
      result.push({
        fieldName: field.label,
        channel_A_expected: joinFields(expectedA, field.key),
        channel_A_pred: joinFields(predA, field.key),
        channel_A_correct: arraysMatchByField(expectedA, predA, field.key),
        channel_B_expected: joinFields(expectedB, field.key),
        channel_B_pred: joinFields(predB, field.key),
        channel_B_correct: arraysMatchByField(expectedB, predB, field.key),
      });
    }

    return result;
  } catch (e) {
    return [];
  }
});


// 统一值格式化方法
function formatValue(value) {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

// 对展示用的JSON进行格式化（带缩进和换行），使字符串中的 \n 等转义符实际生效
function formatDisplayJSON(val) {
  if (val === null || val === undefined) return "";
  // 如果已经是对象/数组，直接漂亮打印
  if (typeof val === "object") {
    return JSON.stringify(val, null, 2);
  }
  // 如果是字符串，尝试解析为JSON后漂亮打印
  if (typeof val === "string") {
    try {
      const parsed = JSON.parse(val);
      if (typeof parsed === "object" && parsed !== null) {
        return JSON.stringify(parsed, null, 2);
      }
      // 解析后是原始值(字符串/数字/布尔)，返回其字符串形式
      return String(parsed);
    } catch {
      // 不是JSON字符串，直接返回原字符串
      return val;
    }
  }
  return String(val);
}

// 将Gaixie数据按dialogue_round的caseId分组
function groupGaixieData(data) {
  const groups = {};
  data.forEach((item) => {
    const caseId = item.dialogue_round
      ? item.dialogue_round.split("-")[0]
      : String(item.index);
    if (!groups[caseId]) {
      groups[caseId] = [];
    }
    groups[caseId].push(item);
  });
  return Object.keys(groups)
    .sort((a, b) => Number(a) - Number(b))
    .map((caseId, idx) => {
      const rounds = groups[caseId].sort((a, b) => a.index - b.index);
      const first = rounds[0];
      // 构建gaixieRounds数据
      const gaixieRounds = rounds.map((r) => {
        const roundResult = r.choices[0]?.review?.result;
        const isCorrect =
          roundResult === true || roundResult === 1 || roundResult === "1";
        const isWrong =
          roundResult === false || roundResult === 0 || roundResult === "0";
        let usageStr = "";
        if (r.usage?.total_tokens) {
          usageStr =
            "总token数:\t" +
            JSON.stringify(r.usage.total_tokens) +
            "\n输入token数:\t" +
            JSON.stringify(r.usage.prompt_tokens) +
            "\n输出token数:\t" +
            JSON.stringify(r.usage.completion_tokens);
        }
        const roundExcel = r.excel_info || {};
        return {
          question: formatDisplayJSON(r.raw_input.Question || ""),
          pred: formatDisplayJSON(r.choices[0]?.review?.pred || ""),
          answer: formatDisplayJSON(r.choices[0]?.review?.gold || ""),
          prompt: r.raw_input.prompt || "",
          context: r.raw_input.context || "",
          result: isCorrect ? "true" : isWrong ? "false" : "",
          resultLabel: isCorrect ? "正确" : isWrong ? "错误" : "未标注",
          resultType: isCorrect ? "success" : isWrong ? "danger" : "info",
          tokenUsage: usageStr,
          responseTime: r.response_time ? JSON.stringify(r.response_time) : "",
          looseResult: roundExcel["宽松判定结果"] || "",
          looseReason: roundExcel["宽松判定原因"] || "",
          strictResult: roundExcel["严格判定结果"] || "",
          strictReason: roundExcel["严格判定原因"] || "",
        };
      });
      // 所有轮次都正确才算正确
      const allCorrect = rounds.every((r) => {
        const revResult = r.choices[0]?.review?.result;
        return revResult === true || revResult === 1 || revResult === "1";
      });
      // 任意轮次错误的判定结果
      const anyWrong = rounds.some((r) => {
        const revResult = r.choices[0]?.review?.result;
        return revResult === false || revResult === 0 || revResult === "0";
      });
      return {
        ...first,
        index: idx,
        caseIndex: Number(caseId),
        gaixieRounds,
        gaixieAllCorrect: allCorrect,
        gaixieAnyWrong: anyWrong,
        // choices保持一个占位，用于兼容existing模板中的v-if="item.choices.length > 1"
        choices: [
          { review: { result: allCorrect ? "1" : anyWrong ? "0" : "" } },
        ],
      };
    });
}

function toggleContext(index) {
  const round = itemInfo.value.gaixieRounds?.[index];
  if (round) {
    round.showContext = !round.showContext;
  }
}


function handleResultChange(val) {
  if (!val || val.length === 0) return;
  if (props.selectValue === "live_code_bench") {
    pagedQuestions.value = [...val].sort((a, b) => a.index - b.index);
  } else {
    pageChange(1);
  }
  if (isGaixie.value) {
    const grouped = groupGaixieData(val);
    if (grouped.length > 0) {
      searchQuestion(grouped[0]);
    }
  } else {
    searchQuestion(
      [...val].sort((a, b) => {
        return a.index - b.index;
      })[0]
    );
  }
}

watch(Result, handleResultChange);

onMounted(() => {
  if (Result.value && Result.value.length > 0) {
    handleResultChange(Result.value);
  }
});
</script>


<style scoped>
.main {
  display: flex;
  /* justify-content: center; */
  height: 100%;
  background-color: #ffffff;
  margin-left: 20px;
  padding-right: 0;
  padding-bottom: 0;
  border-radius: 8px;
  overflow: auto;
  gap: 0;
}

.title {
  /* height: 50px; */
  /* margin-top: 50px; */
  /* margin-right: 50px; */
}

.screening {
  /* margin-left: 10px; */
  /* height: 100vh; */
  /* padding-top: 20px; */
  background-color: #fff;
  border-radius: 5px;
  box-shadow: 0px 0px 8px rgba(158, 158, 158, 0.3);
}

.el-main {
  margin-left: auto;
  align-self: flex-start;
  /* margin-right: 20px; */
  padding-top: 0px;
  gap: 1rem;
  flex-wrap: wrap;
}

.dataCardContainer {
  /* background-color: #ffffff; */
  /* padding: 5px 0px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06); */
  /* border-radius: 4px; */
  /* margin-top: 10px; */
  height: calc(100vh - 310px);
  margin: 10px 20px 0;
  display: flex;
}

.questionCardButtom {
  width: 80px;
  height: 30px;
}

.button_success_color {
  background-color: rgb(160, 207, 255);
}

.buttom_error_color {
  background-color: rgb(250, 182, 182);
}

.buttom_undefine_color {
  background-color: #909399;
  color: #ffffff;
}

.questionCard {
  margin: 10px 0;
  /* width: 200px */
}

.ButtomCard {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 20px;
}

.questionButtomTag {
  display: flex;
  gap: 1rem;
  justify-content: center;
}

.highlight {
  /* border: 0.5px solid #2125fdff; #78a0ffff */
  box-shadow: 0 0 5px 5px #78a0ffff;
  transition: all 0.3s ease;
}

.turnTitle {
  margin-top: 20px;
  font-weight: 700;
  color: rgb(115, 118, 122);
}

.lowAccuracyColor {
  background-color: rgb(250, 182, 182);
}

.middleAccuracyColor {
  background-color: rgb(160, 207, 255);
}

.highAccuracyColor {
  background-color: rgb(179, 225, 157);
}

.asideContainer :deep(.el-scrollbar__view) {
  height: 100%;
}

/* 例如：让图片容器不填满父容器 */
/* 使用深度选择器 */
.preview-image :deep(.el-image__inner) {
  /* 你的自定义样式 */
  max-height: 300px !important;
  width: auto;
  height: auto;
}

.main :deep(.el-textarea) {
  display: block;
  margin-right: 20px;
  width: calc(100% - 20px);
}

.gaixie-flex {
  display: flex;
  gap: 16px;
}

.gaixie-anchor {
  width: 11%;
  min-width: 120px;
  /* margin-top: 28px; */
  border-right: 1px solid #dcdfe6;
}

.gaixie-rounds {
  flex: 1;
  min-width: 0;
}

.gaixie-anchor :deep(.el-anchor__item) {
  margin-bottom: 4px;
}

.gaixie-anchor :deep(.el-anchor__link) {
  font-size: 13px;
  padding: 4px 8px;
  white-space: nowrap;
}
</style>
