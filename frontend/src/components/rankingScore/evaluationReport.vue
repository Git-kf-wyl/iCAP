<template>
  <div class="container">
    <div class="titleContainer">
      <span style="padding: 0 5px"></span>
      <!-- <el-icon @click="goBack" style="cursor: pointer;">
        <Back />
      </el-icon>
      <span @click="goBack" style="color:rgba(18, 19, 22, 0.8);cursor: pointer;">返回</span>-->
      <img src="/images/return.png" class="returnicon" @click="goBack" style="left:10px;" />
      <span style="padding: 0 20px;"></span>
      <!-- <span @click="goBack" style="color: #969696;cursor: pointer;">模型榜单</span>
      <span style="padding: 0 8px;font-size:18px;font-weight:600;">/</span>-->
      <span style="font-size:18px;font-weight:600;">评测报告</span>
      <el-button type="primary" class="downloadBtn">
        <span
          style="color: #fff;"
          @click="exportMultipleToPDF(pageRefs)"
          v-loading.fullscreen.lock="isdownLoading"
        >下载评测报告</span>
      </el-button>
    </div>

    <div class="cardContainer" ref="pageref0">
      <div class="button-container">
        <button class="edit-btn" @click="cancelEdit(0)" v-if="isEditing[0]">取消</button>
        <button class="edit-btn" @click="toggleEdit(0)">{{ isEditing[0] ? '完成' : '编辑' }}</button>
      </div>
      <div style="height:100px"></div>
      <div class="pageOneContainer">
        <div class="first-image-container">
          <img src="/images/icap-mark-v1.svg" alt="iCAP" style="width:64px;height:64px" />
        </div>
        <div class="second-image-container">
          <img src="/images/evaluationReport_06.png" style="width: 100%" />
          <span class="FirstPageTitle">云核大模型综合基准测评报告</span>
          <div v-if="isEditing[0]" class="FirstPageSubtitle">
            <el-input
              v-model="evalReportData[0].content"
              :rows="1"
              type="text"
              placeholder="Please input"
              style="font-size:32px;width:600px;"
            />
          </div>
          <div v-else>
            <span
              class="FirstPageSubtitle"
            >{{evalReportData.length > 0 ? evalReportData[0].content : ''}}</span>
          </div>
        </div>
        <span class="FirstPageTeam">iCAP</span>
        <div v-if="isEditing[0]" class="FirstPageTeam">
          <el-input
            v-model="evalReportData[1].content"
            :rows="1"
            type="text"
            placeholder="Please input"
            style="font-size:32px;width:200px;"
          />
        </div>
        <div v-else>
          <span class="FirstPageTeam">{{evalReportData.length > 0 ? evalReportData[1].content : ''}}</span>
        </div>
      </div>
    </div>

    <div class="cardContainer" ref="pageref1">
      <img src="/images/report-intro-v1.svg" alt="模型评测体系概览" style="width:100%;height:100%" />
    </div>

    <div class="cardContainer" ref="pageref2">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">报告核心结论摘要</div>

        <div class="graphContainer">
          <div class="QuadrantContainer">
            <div class="button-container">
              <button class="edit-btn" @click="cancelEdit(1)" v-if="isEditing[1]">取消</button>
              <button class="edit-btn" @click="toggleEdit(1)">{{ isEditing[1] ? '完成' : '编辑' }}</button>
            </div>

            <div class="editable-wrapper" style="width:500px">
              <div class="card-body">
                <div v-if="isEditing[1]" class="editable-wrapper">
                  <el-input
                    class="editable-summary"
                    v-model="evalReportData[2].content"
                    :rows="3"
                    type="textarea"
                    placeholder="Please input"
                    style="min-width: 500px;font-size:18px;"
                  />
                </div>
                <div v-else class="editable-wrapper">
                  <div
                    class="readonly-summary"
                  >{{ evalReportData.length > 0 ? evalReportData[2].content : '' }}</div>
                </div>
              </div>
            </div>

            <QuadrantChart
              :data="quadrantModels"
              :ruler1-median="50"
              :ruler2-median="50"
              :quadrantLabels="quadrantLabels"
              title="云核大模型综合测评模型象限"
            />
          </div>

          <div style="width:200px" v-if="!isSmallScreen"></div>

          <div class="RadarContainer">
            <RadarChart
              :dimensions="ruler1RadarDimensions"
              :data="ruler1RadarValues"
              :maxValue="100"
              title="通用模型综合评分"
              width="500px"
              height="400px"
            />

            <RadarChart
              :dimensions="ruler2RadarDimensions"
              :data="ruler2RadarValues"
              :maxValue="100"
              title="领域模型综合评分"
              width="500px"
              height="400px"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="cardContainer" ref="pageref3">
      <img src="/images/report-contents-v1.svg" alt="报告目录" style="width:100%;height:100%" />
    </div>

    <div class="cardContainer" ref="pageref4">
      <img src="/images/report-overview-v1.svg" alt="第1部分：测评体系" style="width:100%;height:100%" />
    </div>

    <div class="cardContainer" ref="pageref5">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB大模型综合测评体系</div>
        <div class="QuadrantContainer">
          <div class="editable-EvaluationSystem">
            <div class="card-body">
              <div class="editable-EvaluationSystem">
                <div class="readonly-summary" v-html="$sanitizeHtml(CCNCEBEvaluationSystem)"></div>
              </div>
            </div>
          </div>
        </div>
        <img src="/images/CCNCEBEvaluationSystem .png" class="CCNCEBimg" />
      </div>
    </div>

    <div class="cardContainer" ref="pageref6">
      <img src="/images/report-general-v1.svg" alt="第2部分：通用能力测评" style="width:100%;height:100%" />
    </div>

    <div class="cardContainer" ref="pageref7">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB通用测评基准数据集</div>
        <div class="QuadrantContainer">
          <div class="editable-EvaluationSystem">
            <div class="card-body">
              <div class="editable-EvaluationSystem">
                <div class="readonly-summary" v-html="$sanitizeHtml(CCNCEBBenchmarkDataset)"></div>
              </div>
            </div>
          </div>
        </div>
        <img src="/images/evaluationReport_07.png" class="CCNCEBimg" />
      </div>
    </div>

    <div class="cardContainer" ref="pageref8">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">测评模型列表</div>
        <div class="QuadrantContainer" style="min-width: 800px;">
          <div class="button-container">
            <button class="edit-btn" @click="cancelEdit(2)" v-if="isEditing[2]">取消</button>
            <button class="edit-btn" @click="toggleEdit(2)">{{ isEditing[2] ? '完成' : '编辑' }}</button>
          </div>
          <div class="editable-wrapper">
            <div class="card-body">
              <div v-if="isEditing[2]" class="editable-wrapper">
                <el-input
                  class="editable-summary"
                  v-model="evalReportData[3].content"
                  :rows="2"
                  type="textarea"
                  placeholder="Please input"
                />
              </div>
              <div v-else class="editable-wrapper">
                <div
                  class="readonly-summary"
                >{{ evalReportData.length > 0 ? evalReportData[3].content : '' }}</div>
              </div>
            </div>
          </div>
        </div>
        <el-table
          :data="modelTableData"
          border
          table-layout="fixed"
          class="CCNCEBimg"
          stripe
          size="large"
        >
          <el-table-column prop="ID" label="id" width="100" />
          <el-table-column prop="name" label="模型" min-width="200" />
          <el-table-column prop="publisher" label="机构" width="180" />
          <el-table-column prop="introduction" label="简介" width="800" />
        </el-table>
      </div>
    </div>

    <div class="cardContainer" ref="pageref9">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB通用能力测评：一级总分</div>
        <div class="CCNEBContent">
          <BarChart :data="barCharData" class="barChart"></BarChart>
          <div class="modelResultContainer">
            <div class="modelResultTitle">大模型基础能力结果</div>
            <div class="QuadrantContainer">
              <div class="button-container">
                <button class="edit-btn" @click="cancelEdit(3)" v-if="isEditing[3]">取消</button>
                <button class="edit-btn" @click="toggleEdit(3)">{{ isEditing[3] ? '完成' : '编辑' }}</button>
              </div>
              <div class="editable-wrapper">
                <div class="card-body">
                  <div v-if="isEditing[3]" class="editable-wrapper">
                    <el-input
                      class="editable-summary"
                      v-model="evalReportData[4].content"
                      :rows="22"
                      type="textarea"
                      placeholder="Please input"
                    />
                  </div>
                  <div v-else class="editable-wrapper">
                    <div
                      class="readonly-summary"
                    >{{ evalReportData.length > 0 ? evalReportData[4].content : '' }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="cardContainer" ref="pageref10">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB-理科测评说明（数学）</div>
        <el-container class="assessment_instructions_container">
          <el-aside width="50%">
            <el-container>
              <el-header class="assessment_instructions_leftTopTitle">CCNCEB-数学能力评测数据集</el-header>
              <el-main class="assessment_instructions_leftTopMain">
                <div class="assessment_instructions_leftTopSubTitle">数学能力</div>
                <div>通过MATH-500全面评估模型在数学解题方面能力，覆盖从简单到复杂的各类数学主题，包括算术、代数、几何、数论和概率等数学问题。同时，使用美国高中生的顶级数学竞赛AIME2024的题目，进一步验证模型在解决高难度、进阶数学问题上的能力。</div>
              </el-main>
            </el-container>
            <div style="height: 20px;"></div>
            <el-container>
              <el-header class="assessment_instructions_leftTopTitle">测评方法</el-header>
              <el-main class="assessment_instructions_leftBottonMain">
                <div style="font-weight: bold;margin: 20px 0 10px 0;">评测流程：</div>针对每个问题我们通过设置temperature ≠ 0，采用pass@1方法来评估不同任务的表现。
                <br />以AIME 2024为例，每个问题每次生成k个响应（k在4~64之间），计算k个响应的平均值。
                <br />
                <img
                  src="/images/formula01.png"
                  style="margin: 20px auto 0 auto; width: 150px;display: block;"
                />
                <br />其中， 𝑝_𝑖表明第一个响应的正确性。该方法提供更可靠的性能评估。
                <br />最后将所有题目的结果进行归一化处理，以确保满分100分。这样每个任务的结果都能清晰的反映模型在不同标准下的表现。
                <br />
              </el-main>
            </el-container>
          </el-aside>
          <el-main>
            <el-container>
              <el-header class="assessment_instructions_rightTopTitle">示例</el-header>
              <el-main class="assessment_instructions_rightMain">
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">问题：</div>
                  Every morning Aya goes for a $9$-kilometer-long walk and stops at a coffee shop afterwards. When she walks at a constant speed of $s$ kilometers per hour, the walk takes her 4 hours, including $t$ minutes spent in the coffee shop. When she walks $s+2$ kilometers per hour, the walk takes her 2 hours and 24 minutes, including $t$ minutes spent in the coffee shop. Suppose Aya walks at $s+\\frac{1}{2}$ kilometers per hour. Find the number of minutes the walk takes her, including the $t$ minutes spent in the coffee shop.
                </div>
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">回答：</div>Thus, the number of minutes the walk takes her, including the coffee shop break, is 204.
                  <br />Thus, the number of minutes the walk takes her, including the coffee shop break, is 204.
                  <br />Thus, the number of minutes the walk takes her, including the coffee shop break, is 101.
                  <br />Thus, the number of minutes the walk takes her, including the coffee shop break, is 204.
                  <br />
                </div>
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">评价打分：</div>评估开始：
                  <br />基于pass@1的评估原理，本次共4个输出，第1次，第2次和第4次输出结果正确，第3次输出结果错误。
                  <br />综合以上，AI回答的综合结果为：（1+1+1）/4 = 0.75
                  <br />----逐项评估结束
                </div>
              </el-main>
            </el-container>
          </el-main>
        </el-container>
      </div>
    </div>

    <div class="cardContainer" ref="pageref11">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB-理科测评说明（逻辑推理）</div>
        <el-container class="assessment_instructions_container">
          <el-aside width="50%">
            <el-container>
              <el-header class="assessment_instructions_leftTopTitle">CCNCEB-逻辑推理评测数据集</el-header>
              <el-main class="assessment_instructions_leftTopMain">
                <div class="assessment_instructions_leftTopSubTitle">逻辑推理</div>
                <div>专注于在研究生水平专家推理的复杂推理场景中能力。</div>
              </el-main>
            </el-container>
            <div style="height: 20px;"></div>
            <el-container>
              <el-header class="assessment_instructions_leftTopTitle">测评方法</el-header>
              <el-main class="assessment_instructions_leftBottonMain">
                <div style="font-weight: bold;margin: 20px 0 10px 0;">评测流程：</div>针对每个问题我们通过设置temperature ≠ 0，采用pass@1方法来评估不同任务的表现。
                <br />以GPQA_Diamond为例，每个问题每次生成k个响应（k在4~64之间），计算k个响应的平均值。
                <br />
                <img
                  src="/images/formula01.png"
                  style="margin: 20px auto 0 auto; width: 150px;display: block;"
                />
                <br />其中， 𝑝_𝑖表明第一个响应的正确性。该方法提供更可靠的性能评估。
                <br />最后将所有题目的结果进行归一化处理，以确保满分100分。这样每个任务的结果都能清晰的反映模型在不同标准下的表现。
                <br />
              </el-main>
            </el-container>
          </el-aside>
          <el-main>
            <el-container>
              <el-header class="assessment_instructions_rightTopTitle">示例</el-header>
              <el-main class="assessment_instructions_rightMain">
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">问题：</div>Two quantum states with energies E1 and E2 have a lifetime of 10^-9 sec and 10^-8 sec, respectively. We want to clearly distinguish these two energy levels. Which one of the following options could be their energy difference so that they can be clearly resolved?
                  <br />A. 10^-4 eV B. 10^-9 eV C. 10^-8 eV D. 10^-11 eV
                </div>
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">回答：</div>Thus, the correct answer is: A
                  <br />Thus, the correct answer is: B
                  <br />Thus, the correct answer is: A
                  <br />Thus, the correct answer is: A
                  <br />
                </div>
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">评价打分：</div>评估开始：
                  <br />基于pass@1的评估原理，本次共4个输出，第1次，第3次和第4次输出结果正确，第2次输出结果错误。
                  <br />综合以上，AI回答的综合结果为：（1+1+1）/4 = 0.75
                  <br />----逐项评估结束
                </div>
              </el-main>
            </el-container>
          </el-main>
        </el-container>
      </div>
    </div>

    <div class="cardContainer" ref="pageref12">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB-理科测评说明（代码）</div>
        <el-container class="assessment_instructions_container">
          <el-aside width="50%">
            <el-container>
              <el-header class="assessment_instructions_leftTopTitle">CCNCEB-代码能力评测数据集</el-header>
              <el-main class="assessment_instructions_leftTopMain">
                <div class="assessment_instructions_leftTopSubTitle">代码能力</div>
                <div>通过HumanEval评估语言理解、推理、算法和简单数学方面能力，以评估模型功能正确性，并衡量模型问题解决能力。同时，从LeetCode、Atcodery以及CoderForces竞赛类平台收集问题，构建LiveCodeBench，进一步验证代码生成，自我修复和执行能力。</div>
              </el-main>
            </el-container>
            <div style="height: 20px;"></div>
            <el-container>
              <el-header class="assessment_instructions_leftTopTitle">测评方法</el-header>
              <el-main class="assessment_instructions_leftBottonMain">
                <div style="font-weight: bold;margin: 20px 0 10px 0;">评测流程：</div>针对每个问题我们通过设置temperature ≠ 0，采用pass@1方法来评估不同任务的表现。
                <br />以HumanEval为例，每个问题每次生成k个响应（k在4~64之间），计算k个响应的平均值。
                <br />
                <img
                  src="/images/formula01.png"
                  style="margin: 20px auto 0 auto; width: 150px;display: block;"
                />
                <br />其中， 𝑝_𝑖表明第一个响应的正确性。该方法提供更可靠的性能评估。
                <br />最后将所有题目的结果进行归一化处理，以确保满分100分。这样每个任务的结果都能清晰的反映模型在不同标准下的表现。
                <br />
              </el-main>
            </el-container>
          </el-aside>
          <el-main>
            <el-container>
              <el-header class="assessment_instructions_rightTopTitle">示例</el-header>
              <el-main class="assessment_instructions_rightMain">
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">问题：</div>from typing import List
                  <br />def has_close_elements(numbers: List[float], threshold: float) -> bool:
                  <br />""" Check if in given list of numbers, are any two numbers closer to each other than given threshold.
                  <br />>>> has_close_elements([1.0, 2.0, 3.0], 0.5)
                  <br />False
                  <br />>>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)
                  <br />True
                  <br />"""
                  <br />
                </div>
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">回答：</div>def has_close_elements(numbers: List[float], threshold: float) -> bool: …省略…
                  <br />def has_close_elements(numbers: List[float], threshold: float) -> bool: …省略…
                  <br />def has_close_elements(numbers: List[float], threshold: float) -> bool: …省略…
                  <br />def has_close_elements(numbers: List[float], threshold: float) -> bool: …省略…
                  <br />Test case:
                  <br />assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) == True
                  <br />
                </div>
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">评价打分：</div>评估开始：
                  <br />基于pass@1的评估原理，本次共4个输出，使用测试用例测试生成的代码，第1次，第2次和第3次输出结果正确，第4次输出结果错误。
                  <br />综合以上，AI回答的综合结果为：（1+1+1）/4 = 0.75
                  <br />----逐项评估结束
                </div>
              </el-main>
            </el-container>
          </el-main>
        </el-container>
      </div>
    </div>

    <div class="cardContainer" ref="pageref13">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB-文科测评说明（知识百科）</div>
        <el-container class="assessment_instructions_container">
          <el-aside width="50%">
            <el-container>
              <el-header class="assessment_instructions_leftTopTitle">CCNCEB-知识百科评测数据集</el-header>
              <el-main class="assessment_instructions_leftTopMain">
                <div class="assessment_instructions_leftTopSubTitle">知识百科</div>
                <div>基础知识类数据集，包括但不限于数学、物理、历史，法律、医学和伦理学等知识。</div>
              </el-main>
            </el-container>
            <div style="height: 20px;"></div>
            <el-container>
              <el-header class="assessment_instructions_leftTopTitle">测评方法</el-header>
              <el-main class="assessment_instructions_leftBottonMain">
                <div style="font-weight: bold;margin: 20px 0 10px 0;">评测流程：</div>针对每个问题我们通过设置temperature ≠ 0，采用pass@1方法来评估不同任务的表现。
                <br />以MMLU为例，每个问题每次生成k个响应（k在4~64之间），计算k个响应的平均值。
                <br />
                <img
                  src="/images/formula01.png"
                  style="margin: 20px auto 0 auto; width: 150px;display: block;"
                />
                <br />其中， 𝑝_𝑖表明第一个响应的正确性。该方法提供更可靠的性能评估。
                <br />最后将所有题目的结果进行归一化处理，以确保满分100分。这样每个任务的结果都能清晰的反映模型在不同标准下的表现。
                <br />
              </el-main>
            </el-container>
          </el-aside>
          <el-main>
            <el-container>
              <el-header class="assessment_instructions_rightTopTitle">示例</el-header>
              <el-main class="assessment_instructions_rightMain">
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">问题：</div>Find the degree for the given field extension Q(sqrt(2), sqrt(3), sqrt(18)) over Q.
                  <br />A. 0
                  <br />B. 4
                  <br />C. 2
                  <br />D. 6
                  <br />
                </div>
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">回答：</div>Thus, the correct answer is: B
                  <br />Thus, the correct answer is: B
                  <br />Thus, the correct answer is: B
                  <br />Thus, the correct answer is: C
                  <br />
                </div>
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">评价打分：</div>评估开始：
                  <br />基于pass@1的评估原理，本次共4个输出，第1次，第2次和第3次输出结果正确，第4次输出结果错误。
                  <br />综合以上，AI回答的综合结果为：（1+1+1）/4 = 0.75
                  <br />----逐项评估结束
                </div>
              </el-main>
            </el-container>
          </el-main>
        </el-container>
      </div>
    </div>

    <div class="cardContainer" ref="pageref14">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB-文科测评说明（工具使用）</div>
        <el-container class="assessment_instructions_container">
          <el-aside width="50%">
            <el-container>
              <el-header class="assessment_instructions_leftTopTitle">CCNCEB-工具选择评测数据集</el-header>
              <el-main class="assessment_instructions_leftTopMain">
                <div class="assessment_instructions_leftTopSubTitle">工具选择</div>
                <div>用来评估大模型的Agent能力，包括检索、调用工具的能力。</div>
              </el-main>
            </el-container>
            <div style="height: 20px;"></div>
            <el-container>
              <el-header class="assessment_instructions_leftTopTitle">测评方法</el-header>
              <el-main class="assessment_instructions_leftBottonMain">
                <div style="font-weight: bold;margin: 20px 0 10px 0;">评测流程：</div>针对每个问题我们通过设置temperature ≠ 0，采用accuracy方法来评估不同任务的表现。
                <br />以MMTB为例，每个问题每次生成1个响应，评估响应的结果是否正确。
                <br />
                <br />最后将所有题目的结果进行归一化处理，以确保满分100分。这样每个任务的结果都能清晰的反映模型在不同标准下的表现。
              </el-main>
            </el-container>
          </el-aside>
          <el-main>
            <el-container>
              <el-header class="assessment_instructions_rightTopTitle">示例</el-header>
              <el-main class="assessment_instructions_rightMain">
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">问题：</div>You are an expert in composing functions. You are given a question and a set of possible functions.
                  <br />……省略……
                  <br />
                  [{'name': 'get_user_info', 'description': 'Retrieve details for a specific user by their unique identifier. Note that the provided function is in Python 3 syntax.', 'parameters': {'type': ‘dict', 'required': ['user_id'], 'properties': {'user_id': {'type': 'integer', 'description': 'The unique identifier of the user. It is used to fetch the specific user details from the database.'}, 'special': {'type': 'string', 'description': 'Any special information or parameters that need to be considered while fetching user details.', 'default': 'none'}}}}]
                  <br />Can you retrieve the details for the user with the ID 7890, who has black as their special request?
                </div>
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">回答：</div>[get_user_info(user_id=7890, special='black')]
                  <br />[get_user_info(user_id=7890, special='black')]
                  <br />[get_user_info(user_id=7890, special='black')]
                  <br />[get_user_info(user_id=7890, special='black')]
                  <br />
                </div>
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">评价打分：</div>评估开始：
                  <br />基于accuracy的评估原理，每个任务输出的结果都正确。
                  <br />综合以上，AI回答的综合结果为：正确
                  <br />----逐项评估结束
                  <br />
                </div>
              </el-main>
            </el-container>
          </el-main>
        </el-container>
      </div>
    </div>

    <div class="cardContainer" ref="pageref15">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB-Hard测评说明（指令遵从）</div>
        <el-container class="assessment_instructions_container">
          <el-aside width="50%">
            <el-container>
              <el-header class="assessment_instructions_leftTopTitle">CCNCEB-指令遵从评测数据集</el-header>
              <el-main class="assessment_instructions_leftTopMain">
                <div class="assessment_instructions_leftTopSubTitle">指令遵从</div>
                <div>主要考察模型的指令遵循能力，要求AI严格按照给定的指令进行回复，包括但不限于定义的输出格式或标准来生成响应，精确地呈现要求的数据和信息。</div>
              </el-main>
            </el-container>
            <div style="height: 20px;"></div>
            <el-container>
              <el-header class="assessment_instructions_leftTopTitle">测评方法</el-header>
              <el-main class="assessment_instructions_leftBottonMain">
                <div style="font-weight: bold;margin: 20px 0 10px 0;">评测流程：</div>指令遵从有采用双维度评估体系，通过​​提示级/指令级​​与​​严格/宽松​​两个正交维度形成四类指标：Prompt-level strict-accuracy，Inst-level strict-accuracy，Prompt-level loose-accuracy，Inst-level loose-accuracy。
                <br />
                <b>Prompt</b>：指模型遵循所有指令的能力，只要有一个指令失效，就认为错误
                <br />
                <b>Inst</b>：指令级别遵循能力，如某道题三个指令，若只遵循了两个指令，则正确率2/3
                <br />
                <b>Strict</b>和
                <b>Loose</b>表示是否对模型回答进行后处理，比如指令要求输出P.S. I do like the cake，模型输出P.S. ​**​I do like the cake​**​（含Markdown加粗符号）， Strict因字符级差异被判定错误，loose会对结果后处理（删除标记符号）避免这种情况
                <br />以IF-Eval为例，使用Prompt-level strict-accuracy的评估指标。
                <br />最后将所有题目的结果进行归一化处理，以确保满分100分。这样每个任务的结果都能清晰的反映模型在不同标准下的表现。
                <br />
              </el-main>
            </el-container>
          </el-aside>
          <el-main>
            <el-container>
              <el-header class="assessment_instructions_rightTopTitle">示例</el-header>
              <el-main class="assessment_instructions_rightMain">
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">问题：</div>I am planning a trip to Japan, and I would like thee to write an itinerary for my journey in a Shakespearean style. You are not allowed to use any commas in your response.
                </div>
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">回答：</div>Hark fair voyager to Nippon's fair isle
                  <br />Where cherry blossoms dance and tales beguile
                  <br />Day One: In Edo's realm thy feet shall tread
                  <br />The bustling streets where ancient ghosts are led
                  <br />Ascend Sky Tree's lofty spire by morn
                  <br />Then Senso-ji’s blessings shalt thou be sworn
                  <br />……省略……
                  <br />Fare thee well pilgrim 'cross the orient foam
                  <br />May Nippon's spirit guide thee safely home
                  <br />
                </div>
                <div style="margin-bottom: 10px;">
                  <div style="color:blue;margin-bottom: 10px;">评价打分：</div>评估开始：
                  <br />基于Prompt-level strict-accuracy的评估原理，输出结果必须满足
                  <br />"instruction":["punctuation:no_comma"]
                  <br />综合以上，AI回答的综合结果为：正确
                  <br />----逐项评估结束
                  <br />
                </div>
              </el-main>
            </el-container>
          </el-main>
        </el-container>
      </div>
    </div>

    <div class="cardContainer" ref="pageref16">
      <img src="/images/report-domain-v1.svg" alt="第3部分：领域能力测评" style="width:100%;height:100%" />
    </div>

    <div class="cardContainer" ref="pageref17">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB-运维智能领域测评基准</div>
        <el-container class="assessment_instructions_container">
          <el-aside width="35%" style="margin-top: 20PX;">
            <el-container>
              <el-header>
                <el-divider
                  content-position="center"
                  border-style="dashed"
                  class="dividerTitle"
                >基准说明</el-divider>
              </el-header>
              <el-main class="domain_benchmark_leftMain" style="margin-top: 40px;">
                <div class="QuadrantContainer">
                  <div class="button-container">
                    <button class="edit-btn" @click="cancelEdit(4)" v-if="isEditing[4]">取消</button>
                    <button class="edit-btn" @click="toggleEdit(4)">{{ isEditing[4] ? '完成' : '编辑' }}</button>
                  </div>
                  <div class="editable-wrapper">
                    <div class="card-body">
                      <div v-if="isEditing[4]" class="editable-wrapper">
                        <el-input
                          class="editable-summary"
                          v-model="evalReportData[5].content"
                          :rows="15"
                          type="textarea"
                          placeholder="Please input"
                        />
                      </div>
                      <div v-else class="editable-wrapper">
                        <div
                          class="readonly-summary"
                        >{{ evalReportData.length > 0 ? evalReportData[5].content : '' }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </el-main>
            </el-container>
          </el-aside>
          <el-main>
            <el-header>
              <el-divider content-position="center" border-style="dashed" class="dividerTitle">测试结果</el-divider>
            </el-header>
            <el-main>
              <el-container>
                <el-main>
                  <el-container>
                    <el-header class="domain_benchmark_middleHeader">运维智能的4大场景表现</el-header>
                    <el-main class="center-content">
                      <RadarChart
                        :dimensions="radarDataMap.operations.dimensions"
                        :data="radarDataMap.operations.values"
                        :maxValue="100"
                        title="运维智能的4大场景表现"
                        width="500px"
                        height="500px"
                      />
                    </el-main>
                  </el-container>
                </el-main>
                <el-aside width="35%" class="domain_benchmark_leftMain" style="padding:0">
                  <div class="QuadrantContainer">
                    <div class="button-container">
                      <button class="edit-btn" @click="cancelEdit(5)" v-if="isEditing[5]">取消</button>
                      <button
                        class="edit-btn"
                        @click="toggleEdit(5)"
                      >{{ isEditing[5] ? '完成' : '编辑' }}</button>
                    </div>
                    <div class="editable-wrapper">
                      <div class="card-body">
                        <div v-if="isEditing[5]" class="editable-wrapper">
                          <el-input
                            class="editable-summary"
                            v-model="evalReportData[6].content"
                            :rows="22"
                            type="textarea"
                            placeholder="Please input"
                            style="font-size:16px;"
                          />
                        </div>
                        <div v-else class="editable-wrapper">
                          <div
                            class="readonly-summary"
                            style="font-size:16px;"
                          >{{ evalReportData.length > 0 ? evalReportData[6].content : '' }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </el-aside>
              </el-container>
            </el-main>
          </el-main>
        </el-container>
      </div>
    </div>

    <div class="cardContainer" ref="pageref18">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB-业务智能领域测评基准</div>
        <el-container class="assessment_instructions_container">
          <el-aside width="35%" style="margin-top: 20PX;">
            <el-container>
              <el-header>
                <el-divider
                  content-position="center"
                  border-style="dashed"
                  class="dividerTitle"
                >基准说明</el-divider>
              </el-header>
              <el-main class="domain_benchmark_leftMain" style="margin-top: 40px;">
                <div class="QuadrantContainer">
                  <div class="button-container">
                    <button class="edit-btn" @click="cancelEdit(6)" v-if="isEditing[6]">取消</button>
                    <button class="edit-btn" @click="toggleEdit(6)">{{ isEditing[6] ? '完成' : '编辑' }}</button>
                  </div>
                  <div class="editable-wrapper">
                    <div class="card-body">
                      <div v-if="isEditing[6]" class="editable-wrapper">
                        <el-input
                          class="editable-summary"
                          v-model="evalReportData[7].content"
                          :rows="15"
                          type="textarea"
                          placeholder="Please input"
                        />
                      </div>
                      <div v-else class="editable-wrapper">
                        <div
                          class="readonly-summary"
                        >{{ evalReportData.length > 0 ? evalReportData[7].content : '' }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </el-main>
            </el-container>
          </el-aside>
          <el-main>
            <el-header>
              <el-divider content-position="center" border-style="dashed" class="dividerTitle">测试结果</el-divider>
            </el-header>
            <el-main>
              <el-container>
                <el-main>
                  <el-container>
                    <el-header class="domain_benchmark_middleHeader">业务智能3大能力上的表现</el-header>
                    <el-main class="center-content">
                      <RadarChart
                        :dimensions="radarDataMap.service.dimensions"
                        :data="radarDataMap.service.values"
                        :maxValue="100"
                        title="业务智能3大能力上的表现"
                        width="500px"
                        height="500px"
                      />
                    </el-main>
                  </el-container>
                </el-main>
                <el-aside width="35%" class="domain_benchmark_leftMain" style="padding:0">
                  <div class="QuadrantContainer">
                    <div class="button-container">
                      <button class="edit-btn" @click="cancelEdit(7)" v-if="isEditing[7]">取消</button>
                      <button
                        class="edit-btn"
                        @click="toggleEdit(7)"
                      >{{ isEditing[7] ? '完成' : '编辑' }}</button>
                    </div>
                    <div class="editable-wrapper">
                      <div class="card-body">
                        <div v-if="isEditing[7]" class="editable-wrapper">
                          <el-input
                            class="editable-summary"
                            v-model="evalReportData[8].content"
                            :rows="22"
                            type="textarea"
                            placeholder="Please input"
                            style="font-size:16px;"
                          />
                        </div>
                        <div v-else class="editable-wrapper">
                          <div
                            class="readonly-summary"
                            style="font-size:16px"
                          >{{ evalReportData.length > 0 ? evalReportData[8].content : '' }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </el-aside>
              </el-container>
            </el-main>
          </el-main>
        </el-container>
      </div>
    </div>

    <div class="cardContainer" ref="pageref19">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB-算力主机领域测评基准</div>
        <el-container class="assessment_instructions_container">
          <el-aside width="35%" style="margin-top: 20PX;">
            <el-container>
              <el-header>
                <el-divider
                  content-position="center"
                  border-style="dashed"
                  class="dividerTitle"
                >基准说明</el-divider>
              </el-header>
              <el-main class="domain_benchmark_leftMain" style="margin-top: 40px;">
                <div class="QuadrantContainer">
                  <div class="button-container">
                    <button class="edit-btn" @click="cancelEdit(8)" v-if="isEditing[8]">取消</button>
                    <button class="edit-btn" @click="toggleEdit(8)">{{ isEditing[8] ? '完成' : '编辑' }}</button>
                  </div>
                  <div class="editable-wrapper">
                    <div class="card-body">
                      <div v-if="isEditing[8]" class="editable-wrapper">
                        <el-input
                          class="editable-summary"
                          v-model="evalReportData[9].content"
                          :rows="15"
                          type="textarea"
                          placeholder="Please input"
                        />
                      </div>
                      <div v-else class="editable-wrapper">
                        <div
                          class="readonly-summary"
                        >{{ evalReportData.length > 0 ? evalReportData[9].content : '' }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </el-main>
            </el-container>
          </el-aside>
          <el-main>
            <el-header>
              <el-divider content-position="center" border-style="dashed" class="dividerTitle">测试结果</el-divider>
            </el-header>
            <el-main>
              <el-container>
                <el-main>
                  <el-container>
                    <el-header class="domain_benchmark_middleHeader">算力主机3大场景的表现</el-header>
                    <el-main class="center-content">
                      <RadarChart
                        :dimensions="radarDataMap.box_tool_use.dimensions"
                        :data="radarDataMap.box_tool_use.values"
                        :maxValue="100"
                        title="算力主机3大场景的表现"
                        width="500px"
                        height="500px"
                      />
                    </el-main>
                  </el-container>
                </el-main>
                <el-aside width="35%" class="domain_benchmark_leftMain" style="padding:0">
                  <div class="QuadrantContainer">
                    <div class="button-container">
                      <button class="edit-btn" @click="cancelEdit(9)" v-if="isEditing[9]">取消</button>
                      <button
                        class="edit-btn"
                        @click="toggleEdit(9)"
                      >{{ isEditing[9] ? '完成' : '编辑' }}</button>
                    </div>
                    <div class="editable-wrapper">
                      <div class="card-body">
                        <div v-if="isEditing[9]" class="editable-wrapper">
                          <el-input
                            class="editable-summary"
                            v-model="evalReportData[10].content"
                            :rows="22"
                            type="textarea"
                            placeholder="Please input"
                            style="font-size:16px;"
                          />
                        </div>
                        <div v-else class="editable-wrapper">
                          <div
                            class="readonly-summary"
                            style="font-size:16px;"
                          >{{ evalReportData.length > 0 ? evalReportData[10].content : '' }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </el-aside>
              </el-container>
            </el-main>
          </el-main>
        </el-container>
      </div>
    </div>

    <div class="cardContainer" ref="pageref20">
      <div class="CCNCEBContainer">
        <div class="CCNEBTitle">CCNCEB-AISF领域测评基准</div>
        <el-container class="assessment_instructions_container">
          <el-aside width="35%" style="margin-top: 20PX;">
            <el-container>
              <el-header>
                <el-divider
                  content-position="center"
                  border-style="dashed"
                  class="dividerTitle"
                >基准说明</el-divider>
              </el-header>
              <el-main class="domain_benchmark_leftMain" style="margin-top: 40px;">
                <div class="QuadrantContainer">
                  <div class="button-container">
                    <button class="edit-btn" @click="cancelEdit(10)" v-if="isEditing[10]">取消</button>
                    <button
                      class="edit-btn"
                      @click="toggleEdit(10)"
                    >{{ isEditing[10] ? '完成' : '编辑' }}</button>
                  </div>
                  <div class="editable-wrapper">
                    <div class="card-body">
                      <div v-if="isEditing[10]" class="editable-wrapper">
                        <el-input
                          class="editable-summary"
                          v-model="evalReportData[11].content"
                          :rows="15"
                          type="textarea"
                          placeholder="Please input"
                        />
                      </div>
                      <div v-else class="editable-wrapper">
                        <div
                          class="readonly-summary"
                        >{{ evalReportData.length > 0 ? evalReportData[11].content : '' }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </el-main>
            </el-container>
          </el-aside>
          <el-main>
            <el-header>
              <el-divider content-position="center" border-style="dashed" class="dividerTitle">测试结果</el-divider>
            </el-header>
            <el-main>
              <el-container>
                <el-main>
                  <el-container>
                    <el-header class="domain_benchmark_middleHeader">AISF的4大场景表现</el-header>
                    <el-main class="center-content">
                      <RadarChart
                        :dimensions="radarDataMap.aisf.dimensions"
                        :data="radarDataMap.aisf.values"
                        :maxValue="100"
                        title="AISF的4大场景表现"
                        width="500px"
                        height="500px"
                      />
                    </el-main>
                  </el-container>
                </el-main>
                <el-aside width="35%" class="domain_benchmark_leftMain" style="padding:0">
                  <div class="QuadrantContainer">
                    <div class="button-container">
                      <button class="edit-btn" @click="cancelEdit(11)" v-if="isEditing[11]">取消</button>
                      <button
                        class="edit-btn"
                        @click="toggleEdit(11)"
                      >{{ isEditing[11] ? '完成' : '编辑' }}</button>
                    </div>
                    <div class="editable-wrapper">
                      <div class="card-body">
                        <div v-if="isEditing[11]" class="editable-wrapper">
                          <el-input
                            class="editable-summary"
                            v-model="evalReportData[12].content"
                            :rows="22"
                            type="textarea"
                            placeholder="Please input"
                            style="font-size:16px;"
                          />
                        </div>
                        <div v-else class="editable-wrapper">
                          <div
                            class="readonly-summary"
                            style="font-size:16px;"
                          >{{ evalReportData.length > 0 ? evalReportData[12].content : '' }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </el-aside>
              </el-container>
            </el-main>
          </el-main>
        </el-container>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { DATASET_MAPPING, useRankingStore } from "@/stores/rankingStore.js";
import { formatValue } from "./utils";
import RadarChart from "@/components/modelSquare/radarChart.vue";
import QuadrantChart from "@/components/rankingScore/QuadrantChart.vue";
import BarChart from "./BarChart.vue";
import html2canvas from "html2canvas";
import html2pdf from "html2pdf.js";
import { jsPDF } from "jspdf";
import {
  getEvalReport,
  modifyEvalReport,
  getEvalModelList
} from "@/api/dataService.js";

const router = useRouter();
const goBack = () => {
  router.back();
};

const evalReportData = ref([]);

const mainSubTitle = ref("— 2025年度云核大模型阶段性进展评估");
const mainTitleTime = ref("2025. 04. 27");
const summary = ref(
  "1、Qwen-30B-A3B，Qwen3-32B和DS-R1的总体表现相当\n" +
    "2、Qwen3-253B-A22B的总体结果略强于DS-R1\n" +
    "3、Qwen3-8B的指令遵从能力已接近于DS-R1和Qwq-32B模型，适用于强指令遵从的业务"
);
const CCNCEBEvaluationSystem = ref(
  "云核大模型综合测评体系：打造兼具高效性、客观性与权威性的开源模型技术评估基准，基于两把尺子（尺子一使用开源测评集校准结果可信，\n" +
    "尺子二使用领域摸高测评集，评估领域表现），通过系统性框架设计与平台自动化能力支撑，为云核提供兼具时效性与公信力的开源模型评估基准。\n"
);
const CCNCEBBenchmarkDataset = ref(
  "为进一步真实反应大模型能力，本次测评采用多维度、多层次的综合性测评方案，由理科、文科和Hard三大维度构成。\n" +
    "【理科任务】认为数学、逻辑推理、代码数据集；【文科任务】分为知识百科、工具选择测评集；【Hard任务】本次Hard任务纳入指令遵从测评集、另外复杂多步推理Hard测评集后续推出。"
);
const modelList = ref(
  "本次测评数据选取了CCNCEB-4月测评结果，模型选取了国内外有代表性的10个大模型在4月份的版本。"
);
const modelResult = ref(
  "<b>1. Qwen3-235-A22B领跑，国内大模型进展迅速</b>\n" +
    "Qwen3-235B-2B以78.7分领跑CCNCEB通用能力基准测试，展现出强大的数学，代码，逻辑推理等能力\n" +
    "国内大模型上半年发展迅速，在DeepSeek-R1发布引领潮流后，Qwen3系列模型后来居上。\n" +
    "<b>2. 国内模型形成三大梯队，头部企业引领发展</b>\n" +
    "国内大模型市场形成多梯队格局，头部企业凭借快速迭代、技术积累或资源优势，引领国内大模型发展，例如大厂模型以阿里的Qwen3-235B-A22B，深度求索DeepSeek-R1等均以75+的分数位居国内大模型第一梯队。\n" +
    "<b>3. 开源模型极大的发展</b>\n" +
    "开源Qwen3系列模型在CCNCEB通用基准中表现非常出色，超过之前的行业领袖Deepseek-R1。\n" +
    "\n\n随着技术进步和应用场景拓展，2025年上半年国内外大模型市场竞争将持续加剧，推动技术创新和产业升级。"
);
const benchmarkDescription = ref(
  "问：你是核心网运维工程师，你的任务是根据<用户问题>在<场景列表>中选择对应的场景。\n" +
    "\n<场景列表>：\n" +
    "{'场景名称': '聊天场景', '场景描述': '日常交流与咨询'}\n" +
    "{'场景名称': '故障诊断', '场景描述': '快速定位并修复故障'}\n" +
    "{'场景名称': '知识问答', '场景描述': '专业解答核心网知识'}\n" +
    "{'场景名称': '信息采集', '场景描述': '现网信息收集'}\n" +
    "\n接下来，根据<用户问题>在<场景列表>中选择对应的场景，按照{'场景名称':'...'}的JSON格式输出，只需要输出场景名称。\n" +
    "\n<用户问题>：AMF901网元在2024-02-01 10:00:00到2024-02-01 11:00:00期间，4G附着成功率下降。"
);
const modelTableData = ref([
  {
    id: 1,
    name: "Qwen3-235B-A22B",
    publisher: "阿里巴巴",
    introduction: "官方开源：Qwen3-235B-A22B",
  },
  {
    id: 2,
    name: "Qwen3-235B-A22B",
    publisher: "阿里巴巴",
    introduction: "官方开源：Qwen3-235B-A22B",
  },
  {
    id: 3,
    name: "Qwen3-235B-A22B",
    publisher: "阿里巴巴",
    introduction: "官方开源：Qwen3-235B-A22B",
  },
  {
    id: 4,
    name: "Qwen3-235B-A22B",
    publisher: "阿里巴巴",
    introduction: "官方开源：Qwen3-235B-A22B",
  },
  {
    id: 5,
    name: "Qwen3-235B-A22B",
    publisher: "阿里巴巴",
    introduction: "官方开源：Qwen3-235B-A22B",
  },
  {
    id: 6,
    name: "Qwen3-235B-A22B",
    publisher: "阿里巴巴",
    introduction: "官方开源：Qwen3-235B-A22B",
  },
  {
    id: 7,
    name: "Qwen3-235B-A22B",
    publisher: "阿里巴巴",
    introduction: "官方开源：Qwen3-235B-A22B",
  },
  {
    id: 8,
    name: "Qwen3-235B-A22B",
    publisher: "阿里巴巴",
    introduction: "官方开源：Qwen3-235B-A22B",
  },
  {
    id: 9,
    name: "Qwen3-235B-A22B",
    publisher: "阿里巴巴",
    introduction: "官方开源：Qwen3-235B-A22B",
  },
  {
    id: 10,
    name: "Qwen3-235B-A22B",
    publisher: "阿里巴巴",
    introduction: "官方开源：Qwen3-235B-A22B",
  },
]);

const isEditing = ref([]);
const editablesummary = ref(null);
const gap = ref("200px");
const isSmallScreen = ref(false);

const checkScreenWidth = () => {
  isSmallScreen.value = window.innerWidth < 1500;
};

const toggleEdit = (index) => {
  if (isEditing.value[index]) {
    nextTick(() => {
      if (editablesummary.value) {
        editablesummary.value.innerHTML = summary.value;
        editablesummary.value.focus();
      }
      if (index === 0) {
        modifyEvalReport(evalReportData.value[0]);
        modifyEvalReport(evalReportData.value[1]);
      } else {
        modifyEvalReport(evalReportData.value[index + 1]);
      }
    });
  }
  isEditing.value[index] = !isEditing.value[index];
};

const cancelEdit = (index) => {
  isEditing.value[index] = !isEditing.value[index];
  console.log(evalReportData.value[index]);
  console.log(response.value.data[index]);
  if (index === 0) {
    evalReportData.value[0] = response.value.data[0];
    evalReportData.value[1] = response.value.data[1];
  } else {
    evalReportData.value[index + 1] = response.value.data[index + 1];
  }
};

const onInput = (event) => {
  summary.value = event.target.innerHTML;
};

const ruler1LabelsMap = new Map(
  DATASET_MAPPING["ruler1"].subsets.map((key) => [
    key,
    DATASET_MAPPING["ruler1"].labels[key],
  ])
);

const ruler2LabelsMap = new Map([
  ["operations", "运维智能"],
  ["service", "业务智能"],
  ["box_tool_use", "算力主机"],
  ["aisf", "AISF"],
]);

const rankingStore = useRankingStore();
const modelScores = ref({});

const ruler1Models = ref([]);
const ruler1RadarDimensions = ref([]);
const ruler1RadarValues = ref([]);

const setRuler1Data = () => {
  const scoreMap = new Map();
  modelScores.value = [];
  ruler1Models.value.forEach((model) => {
    if (model.subsets && Array.isArray(model.subsets)) {
      let totalScore = 0;
      let totalNum = 0;
      model.subsets.forEach((subset) => {
        const subsetName = subset?.key;
        const label = ruler1LabelsMap.get(subsetName);

        if (label) {
          const score = parseFloat(subset?.score);
          const validScore = isNaN(score) ? 0 : score;

          totalScore += validScore;
          totalNum += 1;

          if (!scoreMap.has(label)) {
            scoreMap.set(label, []);
          }

          scoreMap.get(label).push(validScore);
        }
      });

      const averageScore =
        totalNum > 0 ? formatValue(totalScore / totalNum) : 0;
      const modelName = model.name.replace(/\s+/g, "");
      modelScores.value[modelName] = {
        name: modelName,
        ruler1Score: averageScore,
        ruler2Score: 0,
      };
    } else {
      console.warn("model.subsets 无效：", model);
    }
  });

  ruler1RadarDimensions.value = [];
  ruler1RadarValues.value = [];
  for (const [label, scores] of scoreMap.entries()) {
    if (scores.length > 0) {
      const total = scores.reduce((sum, score) => sum + score, 0);
      ruler1RadarDimensions.value.push(label);
      ruler1RadarValues.value.push(formatValue(total / scores.length));
    }
  }

  //console.log(modelScores.value);
};

const ruler2Models = ref({});
const ruler2RadarDimensions = ref([]);
const ruler2RadarValues = ref([]);

const radarDataMap = ref({
  operations: {
    values: [],
    dimensions: [],
  },
  service: {
    values: [],
    dimensions: [],
  },
  box_tool_use: {
    values: [],
    dimensions: [],
  },
  aisf: {
    values: [],
    dimensions: [],
  },
});

const operationsRadarValues = ref([]);

const singleRadarOptions = ref({
  operations: operationsRadarValues,
  service: {
    values: [],
    dimensions: [],
  },
  box_tool_use: {
    values: [],
    dimensions: [],
  },
  aisf: {
    values: [],
    dimensions: [],
  },
});

const setRuler2Data = () => {
  ruler2RadarDimensions.value = [];
  ruler2RadarValues.value = [];
  //console.log(ruler2Models.value);
  Object.entries(ruler2Models.value).forEach(([category, models]) => {
    //console.log(category);
    //console.log(models);
    const totalNum = models.length;
    let totalScore = 0;
    let subsetTotalScore = {};

    models.forEach((model, index) => {
      //console.log(model);
      const avgScore = parseFloat(model.averageScore);
      totalScore += Number.isNaN(avgScore) ? 0 : avgScore;

      let totalSubsetScore = 0;
      let totalSubsetNum = 0;
      let subsetScores = [];
      let subsetDimentions = [];

      if (Array.isArray(model.subsets)) {
        model.subsets.forEach((subset) => {
          const key = subset.key;
          const subsetScore = parseFloat(subset?.score);
          totalSubsetScore += Number.isNaN(subsetScore) ? 0 : subsetScore;
          totalSubsetNum += 1;

          //console.log(subset);

          if (!subsetTotalScore[key]) {
            subsetTotalScore[key] = { sum: 0, count: 0 };
          }
          subsetTotalScore[key].sum += Number.isNaN(subsetScore)
            ? 0
            : subsetScore;
          subsetTotalScore[key].count += 1;
          subsetScores.push(subset.score);
          subsetDimentions.push(subset.key);
        });
      }

      if (category === "operations") {
        operationsRadarValues.value.push({
          values: subsetScores,
          dimensions: subsetDimentions,
        });
      }

      const modelName = model.name.replace(/\s+/g, "");
      const averageSubsetScore =
        totalSubsetNum > 0 ? formatValue(totalSubsetScore / totalSubsetNum) : 0;
      if (!modelScores.value[modelName]) {
        modelScores.value[modelName] = {
          name: modelName,
          ruler1Score: 0,
          ruler2Score: averageSubsetScore,
        };
      } else {
        modelScores.value[modelName] = {
          ...modelScores.value[modelName],
          ruler2Score: averageSubsetScore,
        };
      }
    });

    //console.log(operationsRadarValues.value);

    const averageScore = totalNum > 0 ? formatValue(totalScore / totalNum) : 0;
    ruler2RadarDimensions.value.push(ruler2LabelsMap.get(category) || category);
    ruler2RadarValues.value.push(averageScore);

    const Ruler2RadarValues = {};
    for (const key in subsetTotalScore) {
      Ruler2RadarValues[key] =
        subsetTotalScore[key].count > 0
          ? formatValue(subsetTotalScore[key].sum / subsetTotalScore[key].count)
          : 0;
    }
    //console.log(Ruler2RadarValues);

    const labels = DATASET_MAPPING[category].labels;
    const radarData = radarDataMap.value[category];
    radarData.values = Object.values(Ruler2RadarValues);
    radarData.dimensions = Object.keys(Ruler2RadarValues).map(
      (key) => labels[key]
    );
  });

  //console.log(operationsRadarValues.value);
  // console.log(serviceRadarValues.value);
  // console.log(box_tool_useRadarValues.value);
  // console.log(aisfRadarValues.value);
};

const quadrantModels = computed(() => {
  return Object.values(modelScores.value).map((item) => ({
    name: item.name,
    ruler1: parseFloat(item.ruler1Score) || 0,
    ruler2: parseFloat(item.ruler2Score) || 0,
  }));
});

const quadrantLabels = {
  topLeft: "实用主义者",
  bottomLeft: "潜力探索者",
  topRight: "卓越领导者",
  bottomRight: "技术领跑者",
};

const barCharData = computed(() => {
  const sortedArray = Object.values(modelScores.value)
    .map((item) => ({
      name: item.name,
      value: parseFloat(item.ruler1Score) || 0,
    }))
    .sort((a, b) => b.value - a.value);

  return sortedArray.map((item, index) => ({
    ...item,
    index: index + 1,
  }));
});

const isdownLoading = ref(false);

const pageref0 = ref(null);
const pageref1 = ref(null);
const pageref2 = ref(null);
const pageref3 = ref(null);
const pageref4 = ref(null);
const pageref5 = ref(null);
const pageref6 = ref(null);
const pageref7 = ref(null);
const pageref8 = ref(null);
const pageref9 = ref(null);
const pageref10 = ref(null);
const pageref11 = ref(null);
const pageref12 = ref(null);
const pageref13 = ref(null);
const pageref14 = ref(null);
const pageref15 = ref(null);
const pageref16 = ref(null);
const pageref17 = ref(null);
const pageref18 = ref(null);
const pageref19 = ref(null);
const pageref20 = ref(null);
const pageRefs = [
  pageref0,
  pageref1,
  pageref2,
  pageref3,
  pageref4,
  pageref5,
  pageref6,
  pageref7,
  pageref8,
  pageref9,
  pageref10,
  pageref11,
  pageref12,
  pageref13,
  pageref14,
  pageref15,
  pageref16,
  pageref17,
  pageref18,
  pageref19,
  pageref20,
];

const exportMultipleToPDF = async (components) => {
  if (components && components.length > 0) {
    isdownLoading.value = true;
    const options = {
      margin: 1,
      filename: "exported-components.pdf",
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2, dpi: 72, logging: true, excludeImages: [] },
      jsPDF: { unit: "in", format: "A4", orientation: "portrait" },
    };

    const doc = new jsPDF(options.jsPDF);

    const elementsToExclude = document.querySelectorAll(".button-container");
    const elementsToExcludeArray = Array.from(elementsToExclude);

    // 隐藏这些元素
    elementsToExcludeArray.forEach(
      (element) => (element.style.display = "none")
    );

    for (let index = 0; index < components.length; index++) {
      const component = components[index];
      console.log(`Processing component ${index}...`);

      const canvas = await html2canvas(component.value, options.html2canvas);
      const imgData = canvas.toDataURL("image/jpeg", options.image.quality);
      const imgProps = doc.getImageProperties(imgData);
      const pdfWidth = doc.internal.pageSize.getWidth();
      const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;

      // 验证图片尺寸
      if (imgProps.width && imgProps.height) {
        // 添加图片到当前页面
        doc.addImage(imgData, "JPEG", 0, 0, pdfWidth, pdfHeight);

        // 如果不是最后一个组件，添加新页面
        if (index < components.length - 1) {
          doc.addPage();
        }
      }
    }
    elementsToExcludeArray.forEach((element) => (element.style.display = ""));

    // 保存 PDF
    doc.save(options.filename);
    isdownLoading.value = false;
  }
};

const response = ref(null);
watch(response, () => {
  console.log("变了！！！！!");
  console.log(response.value);
});

const loadData = async () => {
  try {
    response.value = await getEvalReport();
    evalReportData.value = JSON.parse(JSON.stringify(response.value.data));
    // console.log(evalReportData.value);

    await rankingStore.getRankingData();
    ruler1Models.value = [...rankingStore.ruler1Values];
    ruler2Models.value = rankingStore.ruler2Values;

    const res = await getEvalModelList();
    modelTableData.value = res.data.slice(0, 10);

    setRuler1Data();
    setRuler2Data();
  } catch (error) {
    console.error("Error fetching data:", error);
  }
};

onMounted(async () => {
  loadData();
  checkScreenWidth();
  window.addEventListener("resize", checkScreenWidth);
});
</script>

<style scoped>
.graphContainer {
  display: flex;
  max-width: 100%;
}

.QuadrantContainer {
  flex: 1;
  /* min-width: 500px; */
  max-width: 100%;
  align-items: center;
  gap: 20px;
  max-height: 100%;
  position: relative;
  justify-content: center;
  display: block;
}

.button-container {
  position: absolute;
  top: 0;
  right: 0;
  display: flex;
  gap: 10px;
  align-items: center;
}

.edit-btn {
  position: relative;
  padding: 6px 12px;
  background-color: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.editable-wrapper {
  border: none;
  background-color: transparent;
  padding-top: 10px;
  min-height: 100px;
  font-size: 15px;
  line-height: 1.5;
  border-radius: 4px;
  outline: none;
  margin-top: 10px;
  margin-bottom: 20px;
  max-width: 800px;
}

.CCNCEBContainer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  width: 100%;
}

.editable-EvaluationSystem {
  border: none;
  background-color: transparent;
  padding: 10px;
  font-size: 15px;
  line-height: 1.5;
  border-radius: 4px;
  outline: none;
  margin-top: 10px;
  margin-bottom: 20px;
  justify-content: center;
}

.card-body {
  justify-content: center;
}

.editable-summary {
  padding-top: 10px;
  min-height: 40px;
  font-size: 20px;
  outline: none;
  box-sizing: border-box;
}

.readonly-summary {
  border: 1px solid transparent;
  font-size: 18px;
  line-height: 1.6;
  color: #333;
  padding: 10px;
  min-height: 40px;
  max-height: 100%;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.RadarContainer {
  min-width: 300px;
  display: relative;
  flex-direction: column;
  gap: 20px;
  align-items: center;
}

.CCNEBTitle {
  font-size: 30px;
}

.CCNCEBimg {
  display: block;
  max-width: 80%;
  font-size: 20px;
  text-align: center;
  --el-table-border-color: #000 !important;
  --el-table-border: 2px #000 solid !important;
}

/* 表头样式 */
.CCNCEBimg :deep(th) {
  background-color: #4589d1cc;
  color: white;
  text-align: center;
  font-size: 24px;
  font-weight: bold;
  height: 60px;
}

/* 偶数行样式 */
.CCNCEBimg :deep(tr:nth-child(even)) {
  background-color: #f0f0f0;
  font-size: 24px;
  height: 60px;
}

/* 奇数行样式 */
.CCNCEBimg :deep(tr:nth-child(odd)) {
  background-color: #e5ebf3de;
  font-size: 24px;
  height: 60px;
}

.CCNEBContent {
  display: flex;
  flex-direction: row;
  width: 95%;
}

.barChart {
  width: 75%;
  height: auto;
  box-sizing: border-box;
}

.modelResultContainer {
  width: 25%;
  height: 1000px;
  box-sizing: border-box;
}

.modelResultTitle {
  text-align: center;
  font-size: 24px;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: black solid 1px;
  color: rgb(0, 0, 151);
}

.cardContainer {
  position: relative;
  height: 1200px;
  max-width: 100%;
  /* margin: 12px 0 12px 10px;  */
  /* page-break-after: always; */
}

.assessment_instructions_container {
  height: 100%;
  width: 90%;
}

.assessment_instructions_leftTopTitle {
  text-align: center;
  font-size: 24px;
  margin-bottom: 20px;
  margin-top: 22px;
  padding-bottom: 10px;
  border-bottom: rgb(75, 147, 255) solid 5px;
  box-shadow: 0 5px 10px rgba(0, 0, 0, 0.3);
}

.assessment_instructions_leftTopMain {
  background-color: #d6e3fc3d;
  height: 350px;
  font-size: 20px;
  padding: 40px;
}

.assessment_instructions_leftTopSubTitle {
  text-align: center;
  font-size: 20px;
  font-weight: bold;
  margin-bottom: 10px;
}

.assessment_instructions_leftBottonMain {
  height: 500px;
  font-size: 20px;
  padding: 40px;
  border: 3px rgb(224, 190, 255) solid;
}

.assessment_instructions_rightTopTitle {
  text-align: center;
  font-size: 24px;
}

.assessment_instructions_rightMain {
  height: 995px;
  font-size: 20px;
  padding: 40px;
  border: 3px rgb(161, 188, 255) dashed;
  display: grid;
  grid-template-rows: repeat(3, 1fr);
  grid-row-gap: 10px;
}

.domain_benchmark_leftMain {
  height: 800px;
  background-color: #abcfec9c;
  border-radius: 10px;
  padding: 40px;
  display: flex;
  align-items: center;
}

.domain_benchmark_middleHeader {
  text-align: center;
  font-size: 24px;
}

.dividerTitle :deep(.el-divider__text) {
  font-size: 24px !important;
}
.dividerTitle {
  border-top: 3px blue var(--el-border-style);
}

.downloadBtn {
  position: absolute;
  right: 0;
  margin-right: 10px;
}

.pageOneContainer {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.first-image-container {
  display: flex;
  justify-content: center;
  width: 100%;
  margin-bottom: 20px; /* 调整间距 */
}

.second-image-container {
  position: relative;
  width: 100%;
  max-width: 100%;
}

.FirstPageTitle,
.FirstPageSubtitle {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
  z-index: 1;
  font-weight: bold;
  color: #333;
  min-width: 1000px;
}

.FirstPageTitle {
  top: 35%;
  font-size: 64px;
  color: #fff;
}

.FirstPageSubtitle {
  top: 60%;
  left: 60%;
  font-size: 32px;
  color: #fff;
}

.FirstPageTeam {
  font-size: 24px;
  margin-bottom: 10px;
}

.center-content {
  display: flex;
  justify-content: center;
  align-items: center;
}

.titleContainer {
  background-color: #fff;
  line-height: 50px;
  height: 50px;
}

.container {
  gap: 0;
  margin: 0;
  max-width: 100%;
}
</style>
