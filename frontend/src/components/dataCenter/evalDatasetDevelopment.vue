<template>
  <div class="dataContainer">
    <el-tabs
      v-model="activeTab"
      class="tabsContainer"
      @tab-click="tabClick"
      :class="{ 'no-slide': disableSlide }"
    >
      <el-tab-pane label="通用测试集" name="openSource">
        <div class="description">基准资源社区，提供丰富基准信息</div>
        <!-- 使用modelSquare风格的header横栏 -->
        <header class="ds-header">
          <div class="ds-btns">
            <button :class="{ active: screeningType === 'all' }" @click="screeningType = 'all'">全部</button>
            <button :class="{ active: screeningType === 'self' }" @click="screeningType = 'self'">自建</button>
            <button :class="{ active: screeningType === 'open' }" @click="screeningType = 'open'">开源</button>
            <el-button class="closebtn" @click="hideScreening">
              <el-icon>
                <Operation />
              </el-icon>
              <span v-if="!isClosed">展开筛选器</span>
              <span v-else>隐藏筛选器</span>
            </el-button>
          </div>
          <div class="ds-search">
            <el-radio-group v-model="viewMode" class="view-mode-toggle">
              <el-radio-button value="list">
                <el-icon><Tickets /></el-icon>&nbsp;列表模式
              </el-radio-button>
              <el-radio-button value="card">
                <el-icon><Grid /></el-icon>&nbsp;卡片模式
              </el-radio-button>
            </el-radio-group>
            <el-cascader
              v-model="tags"
              :options="tagsOptions"
              placeholder="请选择筛选项"
              class="ds-cascader"
              :show-all-levels="false"
              collapse-tags
              collapse-tags-tooltip
              :props="props"
              @change="handelTagsChange"
              style="min-width:200px"
            ></el-cascader>
            <el-input v-model="inputDatasetName" placeholder="请输入测试集名称" :suffix-icon="Search"></el-input>
            <el-select v-model="selectValue" placeholder="Select" style="width: 120px">
              <el-option
                v-for="item in options"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-button type="primary" class="register-btn" @click="datasetRegister">注册测试集</el-button>
            <el-switch
              v-model="showOnlyInUse"
              class="inuse-switch"
              active-text="使用中"
              inactive-text="全部"
            />
          </div>
        </header>
        <el-container class="dataShowContainer">
          <el-aside class="screening" width="250px" v-show="isClosed">
            <div style="margin: 20px">
              <div style="font-size: 18px;font-weight: 700;">筛选</div>
              <div style="margin: 20px 0; width: 100%">
                <div class="elIconLabel">
                  <el-icon>
                    <Reading />
                  </el-icon>
                  <b>文本</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <el-checkbox-button label="知识百科">知识百科</el-checkbox-button>
                  <el-checkbox-button label="逻辑推理">逻辑推理</el-checkbox-button>
                  <el-checkbox-button label="数学">数学</el-checkbox-button>
                  <el-checkbox-button label="代码">代码</el-checkbox-button>
                  <el-checkbox-button label="工具">工具</el-checkbox-button>
                  <el-checkbox-button label="指令遵从">指令遵从</el-checkbox-button>
                  <el-checkbox-button label="长文本">长文本</el-checkbox-button>
                  <el-checkbox-button label="Agent">Agent</el-checkbox-button>
                </el-checkbox-group>
              </div>
              <div style="margin: 20px 0; width: 100%">
                <div class="elIconLabel">
                  <el-icon>
                    <Picture />
                  </el-icon>
                  <b>图像</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <!-- <el-checkbox-button label="文字识别">文字识别</el-checkbox-button>
                  <el-checkbox-button label="图像分类">图像分类</el-checkbox-button>
                  <el-checkbox-button label="图像生成">图像生成</el-checkbox-button>
                  <el-checkbox-button label="图像编辑">图像编辑</el-checkbox-button>-->
                  <el-checkbox-button label="图像理解">图像理解</el-checkbox-button>
                  <el-checkbox-button label="图像推理">图像推理</el-checkbox-button>
                </el-checkbox-group>
              </div>
              <div style="margin: 20px 0; width: 100%">
                <div class="elIconLabel">
                  <el-icon>
                    <Headset />
                  </el-icon>
                  <b>音频</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <el-checkbox-button label="语音识别">语音识别</el-checkbox-button>
                  <!-- <el-checkbox-button label="语音合成">语音合成</el-checkbox-button>
                  <el-checkbox-button label="音频分类">音频分类</el-checkbox-button>
                  <el-checkbox-button label="音频生成">音频生成</el-checkbox-button>-->
                  <el-checkbox-button label="音频理解">音频理解</el-checkbox-button>
                  <el-checkbox-button label="音频推理">音频推理</el-checkbox-button>
                  <!-- <el-checkbox-button label="同声传译">同声传译</el-checkbox-button> -->
                </el-checkbox-group>
              </div>
              <div style="margin: 20px 0; width: 100%">
                <div class="elIconLabel">
                  <el-icon>
                    <VideoCamera />
                  </el-icon>
                  <b>视频</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <!-- <el-checkbox-button label="动作识别">动作识别</el-checkbox-button>
                  <el-checkbox-button label="行为理解">行为理解</el-checkbox-button>
                  <el-checkbox-button label="视频生成">视频生成</el-checkbox-button>
                  <el-checkbox-button label="视频编辑">视频编辑</el-checkbox-button>-->
                  <!-- <el-checkbox-button label="视频推理">视频推理</el-checkbox-button> -->
                  <el-checkbox-button label="视频理解">视频理解</el-checkbox-button>
                </el-checkbox-group>
              </div>
            </div>
          </el-aside>
          <div class="mainContentContainer">
            <div style="flex: 1">
              <div class="mainCardContainer">
                <el-main class="list-grid" v-if="viewMode === 'card'">
                  <el-card
                    class="el-card-container"
                    v-for="(item, key) in curFilteredDataInfos"
                    :key="key"
                    shadow="hover"
                    :body-style="{ padding: '5px' }"
                    @click="toDetail(key, item)"
                  >
                    <div style="font-size: larger; display: flex; margin: 10px; align-items: center">
                      <span style="font-size: medium; font-weight: bold">{{ item.dataset_name }}</span>
                      <span v-if="item.in_use" class="in-use-badge in-use-active">使用中</span>
                      <div class="button-container">
                        <el-link
                          underline="never"
                          @click.stop="handlerShare(key, item)"
                          v-if="hasSharePermission(item)"
                        >
                          <el-icon class="editClass">
                            <Share />
                          </el-icon>
                        </el-link>
                        <el-link
                          underline="never"
                          @click.stop="handlerEdit(key, item)"
                          v-if="hasEditPermission(item)"
                        >
                          <el-icon class="editClass">
                            <Edit />
                          </el-icon>
                        </el-link>
                        <el-link
                          underline="never"
                          @click.stop="handlerDelete(key, item)"
                          v-if="hasSharePermission(item)"
                        >
                          <el-icon class="editClass">
                            <Delete />
                          </el-icon>
                        </el-link>
                      </div>
                    </div>
                    <el-link underline="never" style="padding: 0 10px 10px 10px;display: block;">
                      <div class="tagsBox">
                        <div v-for="tag in item.testcase_tags" :key="tag" class="tags">{{ tag }}</div>
                      </div>
                      <div>
                        <el-tooltip :content="item.description || '暂无描述'">
                          <span class="description_data">{{ item.description || "暂无描述" }}</span>
                        </el-tooltip>
                      </div>

                      <div class="other_info">
                        <div class="info_left">
                          <el-avatar :size="30" src="/images/hugface.svg"></el-avatar>
                          <div>{{ item.group || "open" }}</div>
                        </div>
                        <div class="info_left">
                          <div class="littleInfo_1" v-if="item.establish_time">
                            <el-icon>
                              <Clock />
                            </el-icon>
                            <span>{{ item.establish_time.split(" ")[0] }}</span>
                          </div>
                          <div class="littleInfo_2">
                            <el-icon>
                              <Download />
                            </el-icon>
                            <span>{{ item.download_count || 0 }}</span>
                          </div>
                          <div class="littleInfo_3">
                            <el-icon>
                              <View />
                            </el-icon>
                            <span>{{ item.view_count || 0 }}</span>
                          </div>
                        </div>
                      </div>
                    </el-link>
                  </el-card>
                </el-main>
                <el-table
                  v-else
                  :data="tableData"
                  border
                  stripe
                  style="width: 100%"
                  class="dataset-list-table"
                  :max-height="tableMaxHeight"
                  @row-click="(row) => toDetail(row.key, row)"
                >
                  <el-table-column label="测试集名称" min-width="240">
                    <template #default="{ row }">
                      <span style="font-weight: bold">{{ row.dataset_name }}</span>
                      <span v-if="row.in_use" class="in-use-badge in-use-active table-inuse">使用中</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="标签" min-width="180">
                    <template #default="{ row }">
                      <div class="tagsBox table-tags">
                        <div v-for="tag in row.testcase_tags" :key="tag" class="tags">{{ tag }}</div>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="测试集描述" width="200" show-overflow-tooltip>
                    <template #default="{ row }">{{ row.description || "暂无描述" }}</template>
                  </el-table-column>
                  <el-table-column label="注册时间" width="150">
                    <template #default="{ row }">
                      <span v-if="row.establish_time">
                        <el-icon><Clock /></el-icon>&nbsp;{{ row.establish_time.split(" ")[0] }}
                      </span>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="注册者" width="130">
                    <template #default="{ row }">{{ row.register || "-" }}</template>
                  </el-table-column>
                  <el-table-column width="100">
                    <template #header>
                      <span><el-icon><Download /></el-icon>&nbsp;下载次数</span>
                    </template>
                    <template #default="{ row }">{{ row.download_count || 0 }}</template>
                  </el-table-column>
                  <el-table-column width="100">
                    <template #header>
                      <span><el-icon><View /></el-icon>&nbsp;查看次数</span>
                    </template>
                    <template #default="{ row }">{{ row.view_count || 0 }}</template>
                  </el-table-column>
                  <el-table-column label="操作" width="250" fixed="right">
                    <template #default="{ row }">
                      <div class="table-actions">
                        <el-link type="primary" @click.stop="toDetail(row.key, row)">详情</el-link>
                        <el-link type="primary" @click.stop="handlerDownload(row)" v-if="hasDownloadPermission(row)">下载</el-link>
                        <el-link
                          type="primary"
                          @click.stop="handlerShare(row.key, row)"
                          v-if="hasSharePermission(row)"
                        >分享</el-link>
                        <el-link
                          type="primary"
                          @click.stop="handlerEdit(row.key, row)"
                          v-if="hasEditPermission(row)"
                        >编辑</el-link>
                        <el-link
                          type="danger"
                          @click.stop="handlerDelete(row.key, row)"
                          v-if="hasSharePermission(row)"
                        >删除</el-link>
                      </div>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
            <div class="pagination" v-if="viewMode === 'card'">
              <!--              <span>{{ totalItems }}</span>-->
              <el-pagination
                background
                layout="sizes, prev, pager, next, jumper"
                :page-sizes="[12]"
                :page-size="pageSize"
                :total="totalItems"
                @size-change="handleSizeChange"
                @current-change="handleCurrentChange"
              ></el-pagination>
            </div>
          </div>
        </el-container>
      </el-tab-pane>
      <el-tab-pane label="领域测试集" name="domain">
        <div class="description">基准资源社区，提供丰富基准信息</div>
        <!-- 使用modelSquare风格的header横栏 -->
        <header class="ds-header">
          <div class="ds-btns">
            <button :class="{ active: screeningType === 'all' }" @click="screeningType = 'all'">全部</button>
            <button :class="{ active: screeningType === 'self' }" @click="screeningType = 'self'">自建</button>
            <button :class="{ active: screeningType === 'open' }" @click="screeningType = 'open'">开源</button>
            <el-button class="closebtn" @click="hideScreening">
              <el-icon>
                <Operation />
              </el-icon>
              <span v-if="!isClosed">展开筛选器</span>
              <span v-else>隐藏筛选器</span>
            </el-button>
          </div>
          <div class="ds-search">
            <el-radio-group v-model="viewMode" class="view-mode-toggle">
              <el-radio-button value="list">
                <el-icon><Tickets /></el-icon>&nbsp;列表模式
              </el-radio-button>
              <el-radio-button value="card">
                <el-icon><Grid /></el-icon>&nbsp;卡片模式
              </el-radio-button>
            </el-radio-group>
            <el-input v-model="inputDatasetName" placeholder="请输入测试集名称" :suffix-icon="Search"></el-input>
            <el-select v-model="selectValue" placeholder="Select" style="width: 120px">
              <el-option
                v-for="item in options"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-button type="primary" class="register-btn" @click="datasetRegister">注册测试集</el-button>
            <el-switch
              v-model="showOnlyInUse"
              class="inuse-switch"
              active-text="使用中"
              inactive-text="全部"
            />
          </div>
        </header>
        <el-container class="dataShowContainer">
          <el-aside class="screening" width="250px" v-show="isClosed">
            <div style="margin: 20px">
              <div style="margin: 10px 0; width: 200px">
                <div class="elIconLabel">
                  <el-icon>
                    <Reading />
                  </el-icon>
                  <b>文本</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <!-- <el-checkbox-button label="运维智能">运维智能</el-checkbox-button>
                  <el-checkbox-button label="AISF_NEW">AISF_NEW</el-checkbox-button>
                  <el-checkbox-button label="业务智能">业务智能</el-checkbox-button>
                  <el-checkbox-button label="算力主机">算力主机</el-checkbox-button>
                  <el-checkbox-button label="AISF">AISF</el-checkbox-button>-->
                  <el-checkbox-button label="改写">改写</el-checkbox-button>
                  <el-checkbox-button label="意图">意图</el-checkbox-button>
                  <el-checkbox-button label="记忆">记忆</el-checkbox-button>
                  <el-checkbox-button label="skill提参">skill提参</el-checkbox-button>
                  <el-checkbox-button label="GUI提参">GUI提参</el-checkbox-button>
                  <el-checkbox-button label="伴学提参">伴学提参</el-checkbox-button>
                  <el-checkbox-button label="Coordinator">Coordinator</el-checkbox-button>
                </el-checkbox-group>
              </div>
              <div style="margin: 20px 0; width: 100%">
                <div class="elIconLabel">
                  <el-icon>
                    <Picture />
                  </el-icon>
                  <b>图像</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <!-- <el-checkbox-button label="穿搭">穿搭</el-checkbox-button>
                  <el-checkbox-button label="VLA">VLA</el-checkbox-button>-->
                  <el-checkbox-button label="儿童伴读">儿童伴读</el-checkbox-button>
                </el-checkbox-group>
              </div>
            </div>
          </el-aside>
          <div class="mainContentContainer">
            <div style="flex: 1">
              <div class="mainCardContainer">
                <el-main class="list-grid" v-if="viewMode === 'card'">
                  <el-card
                    class="el-card-container"
                    v-for="(item, key) in curFilteredDataInfos"
                    :key="key"
                    shadow="hover"
                    :body-style="{ padding: '5px' }"
                    @click="toDetail(key, item)"
                  >
                    <div style="font-size: larger; display: flex; margin: 10px; align-items: center">
                      <span style="font-size: medium; font-weight: bold">{{ item.dataset_name }}</span>
                      <span v-if="item.in_use" class="in-use-badge in-use-active">使用中</span>
                      <div class="button-container">
                        <el-link
                          underline="never"
                          @click.stop="handlerShare(key, item)"
                          v-if="hasSharePermission(item)"
                        >
                          <el-icon class="editClass">
                            <Share />
                          </el-icon>
                        </el-link>
                        <el-link
                          underline="never"
                          @click.stop="handlerEdit(key, item)"
                          v-if="hasEditPermission(item)"
                        >
                          <el-icon class="editClass">
                            <Edit />
                          </el-icon>
                        </el-link>
                        <el-link
                          underline="never"
                          @click.stop="handlerDelete(key, item)"
                          v-if="hasSharePermission(item)"
                        >
                          <el-icon class="editClass">
                            <Delete />
                          </el-icon>
                        </el-link>
                      </div>
                    </div>
                    <el-link underline="never" style="padding: 0 10px 10px 10px;display: block;">
                      <div class="tagsBox">
                        <div v-for="tag in item.testcase_tags" :key="tag" class="tags">{{ tag }}</div>
                      </div>
                      <div>
                        <el-tooltip :content="item.description || '暂无描述'">
                          <span class="description_data">{{ item.description || "暂无描述" }}</span>
                        </el-tooltip>
                      </div>

                      <div class="other_info">
                        <div class="info_left">
                          <el-avatar :size="30" src="/images/icon.png"></el-avatar>
                          <div>{{ item.register || "domain" }}</div>
                        </div>
                        <div class="info_left">
                          <div class="littleInfo_1" v-if="item.establish_time">
                            <el-icon>
                              <Clock />
                            </el-icon>
                            <span>{{ item.establish_time.split(" ")[0] }}</span>
                          </div>
                          <div class="littleInfo_2">
                            <el-icon>
                              <Download />
                            </el-icon>
                            <span>{{ item.download_count || 0 }}</span>
                          </div>
                          <div class="littleInfo_3">
                            <el-icon>
                              <View />
                            </el-icon>
                            <span>{{ item.view_count || 0 }}</span>
                          </div>
                        </div>
                      </div>
                    </el-link>
                  </el-card>
                </el-main>
                <el-table
                  v-else
                  :data="tableData"
                  border
                  stripe
                  style="width: 100%"
                  class="dataset-list-table"
                  :max-height="tableMaxHeight"
                  @row-click="(row) => toDetail(row.key, row)"
                >
                  <el-table-column label="测试集名称" min-width="240">
                    <template #default="{ row }">
                      <span style="font-weight: bold">{{ row.dataset_name }}</span>
                      <span v-if="row.in_use" class="in-use-badge in-use-active table-inuse">使用中</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="标签" min-width="180">
                    <template #default="{ row }">
                      <div class="tagsBox table-tags">
                        <div v-for="tag in row.testcase_tags" :key="tag" class="tags">{{ tag }}</div>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="测试集描述" width="200" show-overflow-tooltip>
                    <template #default="{ row }">{{ row.description || "暂无描述" }}</template>
                  </el-table-column>
                  <el-table-column label="注册时间" width="150">
                    <template #default="{ row }">
                      <span v-if="row.establish_time">
                        <el-icon><Clock /></el-icon>&nbsp;{{ row.establish_time.split(" ")[0] }}
                      </span>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="注册者" width="130">
                    <template #default="{ row }">{{ row.register || "-" }}</template>
                  </el-table-column>
                  <el-table-column width="100">
                    <template #header>
                      <span><el-icon><Download /></el-icon>&nbsp;下载次数</span>
                    </template>
                    <template #default="{ row }">{{ row.download_count || 0 }}</template>
                  </el-table-column>
                  <el-table-column width="100">
                    <template #header>
                      <span><el-icon><View /></el-icon>&nbsp;查看次数</span>
                    </template>
                    <template #default="{ row }">{{ row.view_count || 0 }}</template>
                  </el-table-column>
                  <el-table-column label="操作" width="250" fixed="right">
                    <template #default="{ row }">
                      <div class="table-actions">
                        <el-link type="primary" @click.stop="toDetail(row.key, row)">详情</el-link>
                        <el-link type="primary" @click.stop="handlerDownload(row)" v-if="hasDownloadPermission(row)">下载</el-link>
                        <el-link
                          type="primary"
                          @click.stop="handlerShare(row.key, row)"
                          v-if="hasSharePermission(row)"
                        >分享</el-link>
                        <el-link
                          type="primary"
                          @click.stop="handlerEdit(row.key, row)"
                          v-if="hasEditPermission(row)"
                        >编辑</el-link>
                        <el-link
                          type="danger"
                          @click.stop="handlerDelete(row.key, row)"
                          v-if="hasSharePermission(row)"
                        >删除</el-link>
                      </div>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
            <div class="pagination" v-if="viewMode === 'card'">
              <!--              <span>{{ totalItems }}</span>-->
              <el-pagination
                background
                layout="sizes, prev, pager, next, jumper"
                :page-sizes="[12]"
                :page-size="pageSize"
                :total="totalItems"
                @size-change="handleSizeChange"
                @current-change="handleCurrentChange"
              ></el-pagination>
            </div>
          </div>
        </el-container>
      </el-tab-pane>
      <!-- <el-tab-pane label="开发态测试集" name="dev">
        <div class="description">基准资源社区，提供丰富基准信息</div>
        使用modelSquare风格的header横栏
        <header class="ds-header">
          <div class="ds-btns">
            <button :class="{ active: screeningType === 'all' }" @click="screeningType = 'all'">全部</button>
            <button :class="{ active: screeningType === 'self' }" @click="screeningType = 'self'">自建</button>
            <button :class="{ active: screeningType === 'open' }" @click="screeningType = 'open'">开源</button>
            <el-button class="closebtn" @click="hideScreening">
              <el-icon>
                <Operation />
              </el-icon>
              <span v-if="!isClosed">展开筛选器</span>
              <span v-else>隐藏筛选器</span>
            </el-button>
          </div>
          <div class="ds-search">
            <el-input v-model="inputDatasetName" placeholder="请输入测试集名称" :suffix-icon="Search"></el-input>
            <el-select v-model="selectValue" placeholder="Select" style="width: 120px">
              <el-option
                v-for="item in options"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-button type="primary" class="register-btn" @click="datasetRegister">注册测试集</el-button>
          </div>
        </header>
        <el-container class="dataShowContainer">
          <el-aside class="screening" width="250px">
            <div style="margin: 20px">
              <div style="margin: 10px 0; width: 200px">
                <div class="elIconLabel">
                  <el-icon>
                    <Reading />
                  </el-icon>
                  <b>文本</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <el-checkbox-button label="运维智能">运维智能</el-checkbox-button>
                  <el-checkbox-button label="业务智能">业务智能</el-checkbox-button>
                  <el-checkbox-button label="算力主机">算力主机</el-checkbox-button>
                  <el-checkbox-button label="AISF">AISF</el-checkbox-button>
                </el-checkbox-group>
              </div>
              <div style="margin: 10px 0; width: 200px">
                <div class="elIconLabel">
                  <el-icon>
                    <Mic />
                  </el-icon>
                  <b>同声传译</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <el-checkbox-button label="ASR">ASR</el-checkbox-button>
                  <el-checkbox-button label="MT">MT</el-checkbox-button>
                  <el-checkbox-button label="TTS">TTS</el-checkbox-button>
                </el-checkbox-group>
              </div>
              <div style="margin: 20px 0; width: 100%">
                <div class="elIconLabel">
                  <el-icon>
                    <Picture />
                  </el-icon>
                  <b>图像</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <el-checkbox-button label="VLA">VLA</el-checkbox-button>
                </el-checkbox-group>
              </div>
            </div>
          </el-aside>
          <div class="mainContentContainer">
            <div style="flex: 1">
              <div class="mainCardContainer">
                <el-main class="list-grid">
                  <el-card
                    class="el-card-container"
                    v-for="(item, key) in curFilteredDataInfos"
                    :key="key"
                    shadow="hover"
                    :body-style="{ padding: '5px' }"
                    @click="toDetail(key, item)"
                  >
                    <div style="font-size: larger; display: flex; margin: 10px">
                      <span style="font-size: medium; font-weight: bold">{{ item.dataset_name }}</span>
                      <div class="button-container" v-if="hasEditPermission(item)">
                        <el-link underline="never" @click.stop="handlerEdit(key, item)">
                          <el-icon class="editClass">
                            <Edit />
                          </el-icon>
                        </el-link>
                        <el-link underline="never" @click.stop="handlerDelete(key, item)">
                          <el-icon class="editClass">
                            <Delete />
                          </el-icon>
                        </el-link>
                      </div>
                    </div>
                    <el-link underline="never" style="padding: 0 10px 10px 10px;display: block;">
                      <div class="tagsBox">
                        <div v-for="tag in item.testcase_tags" :key="tag" class="tags">{{ tag }}</div>
                      </div>
                      <div>
                        <el-tooltip :content="item.description || '暂无描述'">
                          <span class="description_data">{{ item.description || "暂无描述" }}</span>
                        </el-tooltip>
                      </div>

                      <div class="other_info">
                        <div class="info_left">
                          <el-avatar :size="30" src="/images/icon.png"></el-avatar>
                          <div>{{ item.group || "dev" }}</div>
                        </div>
                        <div class="info_left">
                          <div class="littleInfo_1" v-if="item.establish_time">
                            <el-icon>
                              <Clock />
                            </el-icon>
                            <span>{{ item.establish_time.split(" ")[0] }}</span>
                          </div>
                          <div class="littleInfo_2">
                            <el-icon>
                              <Download />
                            </el-icon>
                            <span>{{ item.download_count || 0 }}</span>
                          </div>
                          <div class="littleInfo_3">
                            <el-icon>
                              <View />
                            </el-icon>
                            <span>{{ item.view_count || 0 }}</span>
                          </div>
                        </div>
                      </div>
                    </el-link>
                  </el-card>
                </el-main>
              </div>
            </div>
            <div class="pagination">
                           <span>{{ totalItems }}</span>
              <el-pagination
                background
                layout="sizes, prev, pager, next, jumper"
                :page-sizes="[12]"
                :page-size="pageSize"
                :total="totalItems"
                @size-change="handleSizeChange"
                @current-change="handleCurrentChange"
              ></el-pagination>
            </div>
          </div>
        </el-container>
      </el-tab-pane>-->
      <!-- <el-tab-pane label="同声传译语料标注" name="interpretation">
        <div class="description">同声传译测试集，包括ASR语料标注、MT语料、TTS语料</div>
        <el-card
          class="head_card"
          :body-style="{
          display: 'flex',
          'background-color': '#ffffff',
          width: '100%',
          'justify-content': 'space-between',
        }"
        >
          <el-radio-group v-model="interpretationScene" class="screeningButtonGroup">
            <el-radio-button label="ASR" v-if="!(interpretationScene==='label')">ASR</el-radio-button>
            <el-radio-button label="label" v-show="interpretationScene==='label'">ASR</el-radio-button>
            <el-radio-button label="MT">MT</el-radio-button>
            <el-radio-button label="TTS">TTS</el-radio-button>
            <el-button
              style="margin-left: 20px;"
              type="primary"
              @click="interpretationScene='label'"
              v-show="interpretationScene==='ASR'"
            >切换至标注</el-button>
            <el-button
              style="margin-left: 20px;"
              type="primary"
              @click="interpretationScene='ASR'"
              v-show="interpretationScene==='label'"
            >切换至语料</el-button>
          </el-radio-group>
          <div style="display: flex; align-items: center; gap: 12px">
            <el-button
              type="primary"
              class="registerButton"
              size="large"
              @click="interpretationDirectoryOpen"
            >添加新目录</el-button>
          </div>
        </el-card>
        <el-container class="dataShowContainer">
          <el-aside class="screening" width="250px" v-loading="loading">
            <div style="margin: 20px">
              <div style="margin: 10px 0; width: 200px">
                <div class="elIconLabel">
                  <el-icon>
                    <Menu />
                  </el-icon>
                  <b>一级目录</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="directoryA" class="checkButtonGroup">
                  <el-tooltip
                    v-for="(item,index) in optionsA"
                    :key="item.value"
                    :content="item.label"
                    :placement="index % 2 === 0 ? 'left' : 'right'"
                    trigger="hover"
                  >
                    <el-checkbox-button
                      :label="item.label"
                      :value="item.value"
                      class="truncated-checkbox"
                    >{{ item.label }}</el-checkbox-button>
                  </el-tooltip>
                </el-checkbox-group>
              </div>
              <div style="margin: 10px 0; width: 200px">
                <div class="elIconLabel">
                  <el-icon>
                    <Menu />
                  </el-icon>
                  <b>二级目录</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="directoryB" class="checkButtonGroup">
                  <el-tooltip
                    v-for="(item,index) in optionsB"
                    :key="item.value"
                    :content="item.label"
                    :placement="index % 2 === 0 ? 'left' : 'right'"
                    trigger="hover"
                  >
                    <el-checkbox-button
                      :label="item.label"
                      :value="item.value"
                      class="truncated-checkbox"
                    >{{ item.label }}</el-checkbox-button>
                  </el-tooltip>
                </el-checkbox-group>
                <el-checkbox-group v-model="directoryB" class="checkButtonGroup">
                  <el-checkbox-button
                    v-for="item in optionsB"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  >{{ item.label }}</el-checkbox-button>
                </el-checkbox-group>
                <div v-if="optionsB.length===0">请选择一级目录</div>
              </div>
              <div style="margin: 10px 0; width: 200px" v-if="interpretationScene==='ASR'">
                <div class="elIconLabel">
                  <el-icon>
                    <Menu />
                  </el-icon>
                  <b>三级目录</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="directoryC" class="checkButtonGroup">
                  <el-tooltip
                    v-for="(item,index) in optionsC"
                    :key="item.value"
                    :content="item.label"
                    :placement="index % 2 === 0 ? 'left' : 'right'"
                    trigger="hover"
                  >
                    <el-checkbox-button
                      :label="item.label"
                      :value="item.value"
                      class="truncated-checkbox"
                    >{{ item.label }}</el-checkbox-button>
                  </el-tooltip>
                </el-checkbox-group>
                <div v-if="optionsC.length===0">请选择二级目录</div>
              </div>
            </div>
          </el-aside>
          <div class="mainContentContainer" v-loading="loading">
            <div style="flex: 1">
              <div class="mainCardContainer">
                <el-main class="list-grid">
                  <el-card
                    class="el-card-container"
                    v-for="item in interpretationCardData"
                    :key="item.id"
                    shadow="hover"
                    :body-style="{ padding: '5px' }"
                  >
                    <div style="font-size: larger; display: flex; margin: 10px">
                      <span style="font-size: medium; font-weight: bold">
                        {{
                        item.directoryA + '/' + item.directoryB + '/' + item.directoryC +
                        (item.directoryD !== null ? '/' + item.directoryD : '')
                        }}
                      </span>
                      <div class="button-container">
                        <el-tooltip effect="dark" content="上传文件" placement="top">
                          <el-link underline="never" @click.stop="handlerAdd(item)">
                            <el-icon class="editClass" size="18">
                              <Plus />
                            </el-icon>
                          </el-link>
                        </el-tooltip>
                        <el-link underline="never" @click.stop="handlerDirectoryDelete(item)">
                          <el-icon class="editClass" size="18">
                            <Delete />
                          </el-icon>
                        </el-link>
                      </div>
                    </div>
                    <el-link underline="never" style="padding: 0 10px 10px 10px;display: block;">
                      <div class="tagsBox">
                        <div v-for="tag in item.testcase_tags" :key="tag" class="tags">{{ tag }}</div>
                      </div>
                    </el-link>
                  </el-card>
                </el-main>
              </div>
            </div>
          </div>
        </el-container>
      </el-tab-pane>-->
    </el-tabs>
    <el-dialog
      v-model="interpretatiionDialog"
      :title="'上传文件至'+fileDirectory+'（若已有则更新)'"
      width="30%"
      :before-close="handleClose"
    >
      <el-upload
        ref="uploadRef"
        drag
        action
        :auto-upload="false"
        :multiple="true"
        :limit="100"
        :on-exceed="handleExceed"
        :on-change="handleFileChange"
        :file-list="fileList"
      >
        <el-icon class="el-icon--upload">
          <upload-filled />
        </el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或
          <em>点击上传</em>
        </div>
        <div class="el-upload__tip" slot="tip">一次最多上传100个文件</div>
      </el-upload>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleClose">关闭</el-button>
          <el-button type="primary" @click="handleMultiUpload">确认上传</el-button>
        </div>
      </template>
    </el-dialog>
    <el-dialog
      v-model="interDirectoryDialog"
      :title="'新增目录至'+interpretationScene"
      width="30%"
      :before-close="handleDirectoryClose"
    >
      <el-form
        :ref="directoryFormRef"
        :model="directoryForm"
        label-width="auto"
        style="max-width: 600px"
        :rules="directoryRules"
      >
        <el-form-item label="一级目录" prop="directoryA">
          <el-select
            v-model="directoryForm.directoryA"
            placeholder="请选择一级目录"
            @change="directoryAChange"
          >
            <el-option
              v-for="item in optionsA"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="二级目录" prop="directoryB" v-if="!(interpretationScene==='MT')">
          <el-select
            v-model="directoryForm.directoryB"
            placeholder="请选择二级目录"
            :disabled="!directoryForm.directoryA"
            @change="directoryBChange"
          >
            <el-option
              v-for="item in directoryOptionsB"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="三级目录" prop="directoryC" v-if="interpretationScene==='ASR'">
          <el-select
            v-model="directoryForm.directoryC"
            placeholder="请选择三级目录"
            :disabled="!directoryForm.directoryB"
          >
            <el-option
              v-for="item in directoryOptionsC"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="新目录名称" prop="name">
          <el-input v-model="directoryForm.name" placeholder="请输入新目录名称" />
        </el-form-item>
        <el-form-item label="完整路径">
          <div>{{ computedFullPath }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleDirectoryClose">取消</el-button>
          <el-button type="primary" @click="handleSubmitDirectory">确认</el-button>
        </div>
      </template>
    </el-dialog>
    <el-dialog
      v-model="shareDialogVisible"
      title="分享测试集"
      width="50%"
      :before-close="handleShareClose"
    >
      <div style="display:flex;flex-direction:column;gap:20px;">
        <div>
          <div style="margin-bottom:8px;font-weight:600;">全员分享</div>
          <el-switch v-model="shareAll" active-text="是" inactive-text="否" />
          <div style="margin-top:8px;font-size:12px;color:#909399;">
            开启后全部用户拥有下方所勾选的全员权限；查看权限全员开放时，下载/编辑仍可针对用户单独分配
          </div>
        </div>
        <div>
          <div style="margin-bottom:8px;font-weight:600;">全员分享权限</div>
          <el-checkbox-group v-model="sharePermissions" :disabled="!shareAll">
            <el-checkbox label="查看" value="view" />
            <el-checkbox label="下载" value="download" />
            <el-checkbox label="编辑" value="edit" />
          </el-checkbox-group>
        </div>
        <div>
          <div style="margin-bottom:8px;font-weight:600;">指定用户</div>
          <div class="share-user-table">
            <div class="share-user-row share-user-table-header">
              <span class="share-user-name">用户（w3账号）</span>
              <span class="share-user-perm">查看</span>
              <span class="share-user-perm">下载</span>
              <span class="share-user-perm">编辑</span>
              <span class="share-user-delete"></span>
            </div>
            <div class="share-user-row" v-for="(row, index) in shareUserList" :key="index">
              <div class="share-user-name">
                <el-select
                  v-model="row.users"
                  multiple
                  filterable
                  allow-create
                  default-first-option
                  clearable
                  placeholder="输入w3账号，回车添加多个"
                  style="width:100%"
                >
                  <el-option v-for="opt in shareUserOptions" :key="opt" :label="opt" :value="opt" />
                </el-select>
              </div>
              <div class="share-user-perm"><el-checkbox v-model="row.view" /></div>
              <div class="share-user-perm"><el-checkbox v-model="row.download" /></div>
              <div class="share-user-perm"><el-checkbox v-model="row.edit" /></div>
              <div class="share-user-delete">
                <el-link type="danger" @click="removeShareUser(index)">
                  <el-icon><Delete /></el-icon>
                </el-link>
              </div>
            </div>
            <el-button type="primary" link @click="addShareUser" style="margin-top:8px;">+ 添加用户</el-button>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleShareClose">取消</el-button>
          <el-button type="primary" @click="confirmShare">确认分享</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, provide, watch, reactive } from "vue";
import { useRouter, useRoute } from "vue-router";
import {
  get_datasets,
  delete_datasets,
  get_count,
  update_view,
  getIntepretationDatasets,
  addInterpretationFile,
  addInterpretationDirectory,
  deleteInterpretationDirectory,
  edit_datasets,
  get_dataset_files,
  downloadDatasetZip,
} from "@/api/dataSetApi";
import { downloadFile } from "@/api/runService";
import { manager_list } from "@/consts/copyrightConsts";
import { useDatasetStore } from "@/stores/datasetStore";
import { useStore } from "vuex";
import {
  ElMessage,
  ElMessageBox,
  UploadInstance,
  UploadProps,
  UploadRawFile,
  genFileId,
  FormRules,
  FormInstance,
} from "element-plus";

const activeTab = ref("");
const screeningType = ref("all");
const tags = ref([]);
const selectTags = ref([]);
const router = useRouter();
const route = useRoute();
const store = useStore();
const inputDatasetName = ref("");
const selectValue = ref("updateTime");
const dataInfos = ref({});
const counts = ref({});

const props = {
  emitPath: false,
  multiple: true,
};

const tagsOptions = ref([
  {
    value: 1,
    label: "文本",
    children: [
      {
        value: "知识百科",
        label: "知识百科",
      },
      {
        value: "逻辑推理",
        label: "逻辑推理",
      },
      {
        value: "数学",
        label: "数学",
      },
      {
        value: "代码",
        label: "代码",
      },
      {
        value: "工具",
        label: "工具",
      },
      {
        value: "指令遵从",
        label: "指令遵从",
      },
      {
        value: "长文本",
        label: "长文本",
      },
      {
        value: "Agent",
        label: "Agent",
      },
    ],
  },
  {
    value: 2,
    label: "图像",
    children: [
      // {
      //   value: "文字识别",
      //   label: "文字识别",
      // },
      // {
      //   value: "图像分类",
      //   label: "图像分类",
      // },
      // {
      //   value: "图像生成",
      //   label: "图像生成",
      // },
      // {
      //   value: "图像编辑",
      //   label: "图像编辑",
      // },
      {
        value: "图像理解",
        label: "图像理解",
      },
      {
        value: "图像推理",
        label: "图像推理",
      },
    ],
  },
  {
    value: 3,
    label: "音频",
    children: [
      // {
      //   value: "语音识别",
      //   label: "语音识别",
      // },
      // {
      //   value: "语音合成",
      //   label: "语言识别",
      // },
      // {
      //   value: "音频分类",
      //   label: "音频分类",
      // },
      // {
      //   value: "音频生成",
      //   label: "音频生成",
      // },
      // {
      //   value: "同声传译",
      //   label: "同声传译",
      // },
      {
        value: "音频理解",
        label: "音频理解",
      },
      {
        value: "音频推理",
        label: "音频推理",
      },
    ],
  },
  {
    value: 4,
    label: "视频",
    children: [
      // {
      //   value: "动作识别",
      //   label: "动作识别",
      // },
      // {
      //   value: "行为理解",
      //   label: "行为理解",
      // },
      // {
      //   value: "视频生成",
      //   label: "视频生成",
      // },
      // {
      //   value: "视频编辑",
      //   label: "视频编辑",
      // },
      {
        value: "视频理解",
        label: "视频理解",
      },
      // {
      //   value: "视频推理",
      //   label: "视频推理",
      // },
    ],
  },
]);

const handelTagsChange = () => {
  // console.log(tags.value);
};

const handlerEdit = (key, item) => {
  router.push({
    name: "datasetRegister",
    query: {
      id: key,
      type: activeTab.value,
      value: JSON.stringify(item),
    },
  });
};

const fleshDatasets = async (isField) => {
  await get_datasets(isField).then((res) => {
    dataInfos.value = res.data;
    datasetStore.setDatasets("ruler" + isField, res.data);
  });
  if (counts.value[isField]) {
    Object.keys(counts.value[isField]).forEach((k) => {
      if (dataInfos.value[k]) {
        dataInfos.value[k] = {
          ...dataInfos.value[k],
          ...counts.value[isField][k],
        };
      }
    });
  }
  // console.log('dataInfos');
  // console.log(dataInfos.value);
  // console.log('counts')
  // console.log(counts.value)
};

const handlerDelete = (key, item) => {
  ElMessageBox.confirm(
    "确认删除数据集： " + key + ": " + item.dataset_name + " 吗？",
    "提示",
    {
      confirmButtonText: "确认",
      cancelButtonText: "取消",
      type: "warning",
    }
  )
    .then(() => {
      delete_datasets({ dataset_id: key, is_field: item.is_field }).then(
        (res) => {
          ElMessage({
            type: "success",
            message: "删除成功",
          });
          fleshDatasets(item.is_field);
        },
        (err) => {
          ElMessage({
            type: "error",
            message: "删除失败：" + err,
          });
        }
      );
    })
    .catch(() => {
      ElMessage({
        type: "info",
        message: "取消删除",
      });
    });
};

const datasetStore = useDatasetStore();

const getDatasetFromStore = (isField) => {
  if (
    Object.keys(datasetStore.getDatasets("ruler" + isField)) &&
    Object.keys(datasetStore.getDatasets("ruler" + isField)).length === 0
  ) {
    fleshDatasets(isField);
  } else {
    dataInfos.value = datasetStore.getDatasets("ruler" + isField);
  }
  if (counts.value[isField]) {
    Object.keys(counts.value[isField]).forEach((k) => {
      if (dataInfos.value[k]) {
        dataInfos.value[k] = {
          ...dataInfos.value[k],
          ...counts.value[isField][k],
        };
      }
    });
  }
};

const tabChange = async (tabName) => {
  await get_count().then((res) => {
    counts.value = res.data;
  });
  if (tabName === "openSource") {
    getDatasetFromStore("1");
  } else if (tabName === "domain") {
    getDatasetFromStore("2");
  } else if (tabName === "dev") {
    getDatasetFromStore("3");
  } else if (tabName === "interpretation") {
    // await loadInterpretationData();
  }
};

// TODO tab点击时候过滤字段要清理
const tabClick = async (tab, event) => {
  tags.value = [];
  screeningType.value = "all";
  tabChange(tab.props.name);
  router.push({
    name: "evalDatasetDevelopment",
    query: { type: tab.props.name },
  });
  if (tab.props.name === "interpretation") {
    loading.value = true;
    await loadInterpretationData();
    loadOptionsA("ASR");
  }
};

const options = [
  {
    value: "name",
    label: "名称",
  },
  {
    value: "updateTime",
    label: "更新时间",
  },
  {
    value: "views",
    label: "浏览量",
  },
];

/* 处理分页相关 */
const pageSize = ref(12);
const currentPage = ref(1);
const totalItems = computed(() => {
  return Object.keys(filteredDataInfos.value).length;
});
const handleSizeChange = (val) => {
  pageSize.value = val;
  currentPage.value = 1; // 切换每页数量时回到第一页
  console.log("csh, handleSizeChange", pageSize.value);
};
const handleCurrentChange = (val) => {
  currentPage.value = val;
  console.log("csh, handleCurrentChange", currentPage.value);
};

// 获取当前用户名
const currentUsername = localStorage.getItem("username") || "";

// 判断当前用户是否是管理员
const isManager = manager_list.includes(currentUsername);

// 判断用户名是否匹配（支持前缀匹配，例如当前用户 "123" 可匹配名单中的 "123456"）
const matchUser = (list = [], username) => {
  return list.some((u) => u === "all" || u === username || u.startsWith(username));
};

// 判断当前用户是否有查看权限
const hasViewPermission = (item) => {
  if (isManager) return true; // 管理员拥有全部权限
  if (currentUsername === item.register) return true; // 注册人拥有查看权限
  if (item.is_published) return true; // 已发布，所有人可查看
  // 未发布：必须在 viewer_users 或 editor_users 中
  const viewers = item.viewer_users || [];
  const editors = item.editor_users || [];
  return matchUser(viewers, currentUsername) || matchUser(editors, currentUsername);
};

// 判断当前用户是否有编辑权限
const hasEditPermission = (item) => {
  if (isManager) return true; // 管理员拥有全部权限
  const editors = item.editor_users || [];
  return currentUsername === item.register || matchUser(editors, currentUsername);
};

const hasSharePermission = (item) => {
  if (isManager) return true; // 管理员拥有全部权限
  return currentUsername === item.register;
};

// 判断当前用户是否有下载测评集权限
const hasDownloadPermission = (item) => {
  if (isManager) return true; // 管理员默认拥有下载权限
  const download_users = item.download_users || [];
  const editors = item.editor_users || [];
  return (
    currentUsername === item.register ||
    matchUser(download_users, currentUsername) ||
    matchUser(editors, currentUsername)
  );
};

// 下载测评集（与详情页逻辑一致）
const handlerDownload = async (row) => {
  try {
    let local_path;
    if (activeTab.value === "openSource") {
      local_path = row.local_path;
    } else {
      local_path = row.input_path;
    }
    const res = await get_dataset_files({
      local_path: local_path,
      is_field: row.is_field,
      dataset: row.key,
      user_name: currentUsername,
    });
    const files = res.data;
    if (!files || files.length === 0) {
      ElMessage({ type: "error", message: "没有可供下载的文件" });
      return;
    }
    if (files.length === 1) {
      // 单个文件，直接下载
      const response = await downloadFile({ filepath: files[0] });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = files[0].split("/").pop().split("\\").pop();
      a.click();
      window.URL.revokeObjectURL(url);
    } else {
      // 多个文件或文件夹，压缩后下载
      const response = await downloadDatasetZip({
        filepaths: files,
        zip_name: row.key || "dataset",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${row.key || "dataset"}.zip`;
      a.click();
      window.URL.revokeObjectURL(url);
    }
    ElMessage({ type: "success", message: "下载成功" });
  } catch (err) {
    const msg = err.response?.data?.error || err.message || "下载失败";
    ElMessage({ type: "error", message: "下载失败: " + msg });
  }
};

// 分享相关
const shareDialogVisible = ref(false);
const shareAll = ref(false);
const sharePermissions = ref([]);
const shareTargetKey = ref("");
const shareUserList = ref([]);

const shareUserOptions = computed(() =>
  shareUserList.value.flatMap((row) => row.users).filter(Boolean)
);

const handlerShare = (key, item) => {
  shareTargetKey.value = key;
  shareAll.value = !!item.is_published;

  // 回显全员分享的权限
  sharePermissions.value = [];
  if (shareAll.value) {
    const allPerms = {
      view: (item.viewer_users || []).includes("all"),
      download: (item.download_users || []).includes("all"),
      edit: (item.editor_users || []).includes("all"),
    };
    if (allPerms.view) sharePermissions.value.push("view");
    if (allPerms.download) sharePermissions.value.push("download");
    if (allPerms.edit) sharePermissions.value.push("edit");
  }

  // 将现有已授权用户按权限组合分组：同一权限组合的用户放在同一行
  const viewerSet = new Set((item.viewer_users || []).filter((u) => u !== "all"));
  const downloadSet = new Set((item.download_users || []).filter((u) => u !== "all"));
  const editorSet = new Set((item.editor_users || []).filter((u) => u !== "all"));
  const allUsers = new Set([...viewerSet, ...downloadSet, ...editorSet]);

  const groups = new Map();
  allUsers.forEach((name) => {
    const keyPerm = `${viewerSet.has(name) ? 1 : 0}-${downloadSet.has(name) ? 1 : 0}-${editorSet.has(name) ? 1 : 0}`;
    if (!groups.has(keyPerm)) groups.set(keyPerm, []);
    groups.get(keyPerm).push(name);
  });

  shareUserList.value = [...groups.entries()].map(([permKey, users]) => {
    const parts = permKey.split("-").map((v) => v === "1");
    return { users, view: parts[0], download: parts[1], edit: parts[2] };
  });

  shareDialogVisible.value = true;
};

const addShareUser = () => {
  shareUserList.value.push({ users: [], view: true, download: false, edit: false });
};

const removeShareUser = (index) => {
  shareUserList.value.splice(index, 1);
};

const handleShareClose = () => {
  shareDialogVisible.value = false;
};

const confirmShare = async () => {
  const item = dataInfos.value[shareTargetKey.value];
  if (!item) return;

  const hasAllPerm = shareAll.value && sharePermissions.value.length > 0;
  const validRows = shareUserList.value.filter(
    (row) =>
      (row.users || []).some((name) => name && String(name).trim()) &&
      (row.view || row.download || row.edit)
  );
  if (!hasAllPerm && validRows.length === 0) {
    ElMessage({
      type: "warning",
      message: "请至少选择一条全员权限，或添加一个指定用户并选择权限",
    });
    return;
  }

  const viewer_users = [];
  const download_users = [];
  const editor_users = [];

  if (shareAll.value) {
    if (sharePermissions.value.includes("view")) viewer_users.push("all");
    if (sharePermissions.value.includes("download")) download_users.push("all");
    if (sharePermissions.value.includes("edit")) editor_users.push("all");
  }

  shareUserList.value.forEach((row) => {
    (row.users || []).forEach((rawName) => {
      const name = String(rawName || "").trim();
      if (!name) return;
      if (row.view && !viewer_users.includes(name)) viewer_users.push(name);
      if (row.download && !download_users.includes(name)) download_users.push(name);
      if (row.edit && !editor_users.includes(name)) editor_users.push(name);
    });
  });

  const formData = {
    dataset_id: shareTargetKey.value,
    is_field: item.is_field,
    dataset_name: item.dataset_name,
    description: item.description || "",
    testcase_tags: item.testcase_tags || [],
    is_open_source: item.is_open_source,
    is_published: shareAll.value,
    few_shot_num: item.few_shot_num ?? 0,
    subset_list: item.subset_list || [],
    metric_list: item.metric_list || [],
    default_subsets: item.default_subsets || [],
    dataSet_cases: item.dataSet_cases || "",
    system_prompt: item.system_prompt || "",
    user_prompt: item.user_prompt || "",
    file_list: item.file_list || [],
    few_file_list: item.few_file_list || [],
    register: item.register || currentUsername,
    viewer_users,
    download_users,
    editor_users,
  };

  try {
    await edit_datasets(formData);
    ElMessage({ type: "success", message: "分享成功" });
    shareDialogVisible.value = false;
    await fleshDatasets(item.is_field);
  } catch (err) {
    ElMessage({
      type: "error",
      message:
        "分享失败: " + (err.response?.data?.err_info || err.message || err),
    });
  }
};

// 是否仅展示“使用中”的测试集（默认展示全部）
const showOnlyInUse = ref(false);

const filteredDataInfos = computed(() => {
  let result = dataInfos.value;
  console.log("result");
  console.log(result);
  if (tags.value.length !== 0) {
    result = {};
    for (const key in dataInfos.value) {
      const item = dataInfos.value[key];
      if (
        item.testcase_tags &&
        item.testcase_tags.some((tag) => tags.value.includes(tag))
      ) {
        result[key] = item;
      }
    }
  }
  let fiter = "establish_time";
  if (selectValue.value === "name") {
    fiter = "dataset_name";
  } else if (selectValue.value === "updateTime") {
    fiter = "establish_time";
  } else if (selectValue.value === "views") {
    fiter = "name";
  }
  let re = Object.keys(result)
    .filter((k) => {
      // 仅展示“使用中”的测试集
      if (showOnlyInUse.value && !result[k].in_use) return false;
      // 权限过滤：无查看权限的不显示
      // if (!hasViewPermission(result[k])) return false;
      if (screeningType.value === "all") {
        return k.includes(inputDatasetName.value);
      } else if (screeningType.value === "open") {
        return k.includes(inputDatasetName.value) && result[k].is_open_source;
      } else if (screeningType.value === "self") {
        return k.includes(inputDatasetName.value) && !result[k].is_open_source;
      }
    })
    .sort((a, b) => {
      if (!result[a][fiter]) return a;
      if (!result[b][fiter]) return b;
      if (selectValue.value === "updateTime") {
        return (
          Date.parse(result[b][fiter].replace(" ", "T")) -
          Date.parse(result[a][fiter].replace(" ", "T"))
        );
      } else {
        return (
          Date.parse(result[a][fiter].replace(" ", "T")) -
          Date.parse(result[b][fiter].replace(" ", "T"))
        );
      }
    })
    .reduce((obj, k) => {
      obj[k] = result[k];
      return obj;
    }, {});
  return re;
});

const curFilteredDataInfos = computed(() => {
  // console.log("csh, curDatalist");
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  // console.log("csh, curDatalist 更新", start, end);
  const keys = [];
  const filteredValue = filteredDataInfos.value;
  return Object.keys(filteredValue)
    .slice(start, end)
    .reduce((obj, k) => {
      obj[k] = filteredValue[k];
      return obj;
    }, {});
});

// 展示模式：card（卡片模式） / list（列表模式）
// 从 store 读取出初始值，进入详情/注册页再返回时不重置为默认卡片模式
const viewMode = ref(store.getters.getViewMode || "card");

// 记录列表/卡片模式到 store，保证在详情/注册等页面间切换时保持用户选择
watch(viewMode, (val) => {
  store.dispatch("updateViewMode", val);
});

// 列表模式下表格最大高度：与 mainContentContainer / screening 筛选栏高度保持一致
const tableMaxHeight = ref(600);
let tableResizeObserver = null;

const updateTableHeight = () => {
  const containers = document.querySelectorAll(".mainContentContainer");
  for (const c of containers) {
    if (c.offsetHeight > 0) {
      // 去除顶部与底部少量留白，与另一侧 screening 高度一致
      const h = c.offsetHeight - 4;
      tableMaxHeight.value = h > 0 ? h : 600;
      break;
    }
  }
};

// 列表模式数据：展示全部筛选/排序后的数据（不分页），并带上 key 供操作使用
const tableData = computed(() => {
  const cur = filteredDataInfos.value;
  return Object.keys(cur).map((k) => ({ key: k, ...cur[k] }));
});

const isClosed = ref(true);
const screenWidth = ref("250px");
const hideScreening = () => {
  isClosed.value = !isClosed.value;
  const newValue = screenWidth.value === "250px" ? "0px" : "250px";
  setTimeout(() => {
    screenWidth.value = newValue;
    const screeningElement = document.querySelector(".screening");
    if (screeningElement) {
      screeningElement.style.marginLeft = newValue === "250px" ? "20px" : "0px";
    }
  }, 0);
};

const disableSlide = ref(true);

watch(route, async () => {
  // console.log(route.query.type);
  if (route.query.type === undefined) {
    activeTab.value = "openSource";
    await fleshDatasets("1");
  }
});

watch(tags, () => {
  // console.log("tags");
  // console.log(tags.value);
});

watch(screeningType, () => {
  // console.log("screeningType");
  // console.log(screeningType.value);
  store.dispatch("updateScreeningType", screeningType.value);
});

watch(
  () => store.getters.getTags,
  (newTags) => {
    tags.value = newTags;
  }
);

watch(
  () => store.getters.getScreeningType,
  (newScreeningType) => {
    screeningType.value = newScreeningType;
  }
);

const searchButton = () => {
  // const filteredEntries = Object.entries(dataInfos.value).filter(
  //   ([key, value]) => key === input3.value
  // );
  // filteredDataInfos.value = Object.fromEntries(filteredEntries);
};

const datasetRegister = () => {
  router.push({
    name: "datasetRegister",
    query: {
      type: activeTab.value,
    },
  });
};

const toDetail = async (id, item) => {
  store.dispatch("updateTags", tags.value);
  store.dispatch("updateScreeningType", screeningType.value);
  router.push("/child");
  router.push({
    name: "datasetDetail",
    query: {
      id: id,
      type: activeTab.value,
    },
  });
  let is_field;
  if (activeTab.value === "openSource") {
    is_field = "1";
  } else if (activeTab.value === "domain") {
    is_field = "2";
  } else if (activeTab.value === "dev") {
    is_field = "3";
  }
  //  else if (activeTab.value === "interpretation") {
  //   is_field = "4";
  // }
  await update_view({ is_field: is_field, dataset: id });
};

const filter = (str) => {
  return str.length > 24 ? str.slice(0, 24) + "..." : str;
};

//同声传译相关
const interpretationData = ref([]);
const interpretationScene = ref("ASR");
const rawInterpretationCard = ref([]);
const interpretationCardData = ref([]);

const loading = ref(true);

const directoryA = ref([]);
const directoryB = ref([]);
const directoryC = ref([]);

const optionsA = ref([]);
const optionsB = ref([]);
const optionsC = ref([]);

const loadInterpretationData = async () => {
  const storedData = localStorage.getItem("interpretationData");

  // if (!refresh) {
  //   interpretationData.value = JSON.parse(storedData);
  // } else {
  const res = await getIntepretationDatasets();
  localStorage.setItem("interpretationData", JSON.stringify(res.data));
  interpretationData.value = res.data;
  // }
  rawInterpretationCard.value = transformData(
    interpretationData.value,
    interpretationScene.value && interpretationScene.value !== ""
      ? interpretationScene.value
      : ""
  );
  interpretationCardData.value = []; // 先清空
  interpretationCardData.value.splice(0, 0, ...rawInterpretationCard.value); // 插入新数据
  console.log("interpretationCardData");
  console.log(interpretationCardData.value);
  // if (directoryA.value.length > 0) {
  //   const temp = directoryA.value;
  directoryA.value = [];
  //   directoryA.value = temp;
  // }
  // if (directoryB.value.length > 0) {
  //   const temp = directoryB.value;
  directoryB.value = [];
  //   directoryB.value = temp;
  // }
  // if (directoryC.value.length > 0) {
  //   const temp = directoryC.value;
  directoryC.value = [];
  //   directoryC.value = temp;
  // }
  loading.value = false;
};

const filtered1TableData = ref([]);
const filtered2TableData = ref([]);

watch(directoryA, (value) => {
  // console.log("directoryA:");
  // console.log(value);
  if (value.length > 0) {
    interpretationCardData.value = rawInterpretationCard.value.filter((item) =>
      value.includes(item.directoryA)
    );
    directoryB.value = [];
    setDirectoryBOptions(value);
    filtered1TableData.value = interpretationCardData.value;
  } else {
    interpretationCardData.value = rawInterpretationCard.value;
    filtered1TableData.value = interpretationCardData.value;
    directoryB.value = [];
    directoryC.value = [];
    optionsB.value = [];
    optionsC.value = [];
  }
});

watch(directoryB, (val) => {
  // console.log("directoryB:");
  // console.log(val);

  if (val.length > 0) {
    interpretationCardData.value = filtered1TableData.value.filter((item) =>
      val.includes(item.directoryB)
    );
    if (interpretationScene.value === "ASR") {
      directoryC.value = [];
      setDirectoryCOptions(val);
      filtered2TableData.value = interpretationCardData.value;
    }
  } else {
    interpretationCardData.value = filtered1TableData.value;
    filtered2TableData.value = interpretationCardData.value;
    directoryC.value = [];
    optionsC.value = [];
  }
});

watch(directoryC, (values) => {
  if (values.length > 0) {
    interpretationCardData.value = filtered2TableData.value.filter((item) =>
      values.includes(item.directoryC)
    );
  } else {
    interpretationCardData.value = filtered2TableData.value;
  }
});

const loadOptionsA = (val) => {
  optionsA.value = [];
  if (Object.keys(interpretationData.value).length !== 0) {
    let uniqueKeys = new Set(); // 创建一个 Set 用于存储唯一的 key
    switch (val) {
      case "ASR":
        Object.keys(interpretationData.value.ASRAllData).forEach((key) => {
          if (!uniqueKeys.has(key)) {
            // 检查 key 是否已存在
            uniqueKeys.add(key); // 将 key 添加到 Set 中
            optionsA.value.push({
              value: key,
              label: key,
            });
          }
        });
        break;
      case "label":
        Object.keys(interpretationData.value.ASRTagging).forEach((key) => {
          if (!uniqueKeys.has(key)) {
            // 检查 key 是否已存在
            uniqueKeys.add(key); // 将 key 添加到 Set 中
            optionsA.value.push({
              value: key,
              label: key,
            });
          }
        });
        break;
      case "MT":
        Object.keys(interpretationData.value.MTAllData).forEach((key) => {
          if (!uniqueKeys.has(key)) {
            uniqueKeys.add(key);
            optionsA.value.push({
              value: key,
              label: key,
            });
          }
        });
        break;
      case "TTS":
        Object.keys(interpretationData.value.TTSAllData).forEach((key) => {
          if (!uniqueKeys.has(key)) {
            uniqueKeys.add(key);
            optionsA.value.push({
              value: key,
              label: key,
            });
          }
        });
        break;
      default:
        Object.keys(interpretationData.value.ASRAllData).forEach((key) => {
          if (!uniqueKeys.has(key)) {
            uniqueKeys.add(key);
            optionsA.value.push({
              value: key,
              label: key,
            });
          }
        });
        break;
    }
  }
};

const setDirectoryBOptions = (values) => {
  optionsB.value = [];
  const uniqueOptions = new Set();
  values.forEach((value) => {
    if (interpretationScene.value === "ASR") {
      Object.keys(interpretationData.value.ASRAllData[value]).forEach(
        (item: any) => {
          uniqueOptions.add(item);
        }
      );
    } else if (interpretationScene.value === "label") {
      Object.keys(interpretationData.value.ASRTagging[value]).forEach(
        (item: any) => {
          uniqueOptions.add(item);
        }
      );
    } else if (interpretationScene.value === "MT") {
      Object.keys(interpretationData.value.MTAllData[value]).forEach(
        (item: any) => {
          uniqueOptions.add(item);
        }
      );
    } else if (interpretationScene.value === "TTS") {
      Object.keys(interpretationData.value.TTSAllData[value]).forEach(
        (item: any) => {
          uniqueOptions.add(item);
        }
      );
    }
  });
  // 将去重后的选项添加到 optionsB.value
  uniqueOptions.forEach((item) => {
    optionsB.value.push({
      value: item,
      label: item,
    });
  });
};

const setDirectoryCOptions = (values) => {
  optionsC.value = [];
  const uniqueOptions = new Set();
  values.forEach((value) => {
    if (interpretationScene.value === "ASR") {
      Object.keys(
        interpretationData.value.ASRAllData[directoryA.value][value]
      ).forEach((item: any) => {
        uniqueOptions.add(item);
      });
    } else if (interpretationScene.value === "label") {
      Object.keys(
        interpretationData.value.ASRTagging[directoryA.value][value]
      ).forEach((item: any) => {
        uniqueOptions.add(item);
      });
    } else if (interpretationScene.value === "MT") {
      Object.keys(
        interpretationData.value.MTAllData[directoryA.value][value]
      ).forEach((item: any) => {
        uniqueOptions.add(item);
      });
    } else if (interpretationScene.value === "TTS") {
      Object.keys(
        interpretationData.value.TTSAllData[directoryA.value][value]
      ).forEach((item: any) => {
        uniqueOptions.add(item);
      });
    }
  });
  // 将去重后的选项添加到 optionsC.value
  uniqueOptions.forEach((item) => {
    optionsC.value.push({
      value: item,
      label: item,
    });
  });
};

watch(
  interpretationScene,
  (val: String) => {
    console.log("scene");
    console.log(val);
    rawInterpretationCard.value = transformData(interpretationData.value, val);
    interpretationCardData.value = rawInterpretationCard.value;
    directoryA.value = [];
    directoryB.value = [];
    directoryC.value = [];
    loadOptionsA(val);
    // console.log("interpretationCardData");
    // console.log(interpretationCardData.value);
  },
  { deep: true }
);

const data = {
  英阿互译: {
    英语语料: {},
    阿语语料: {
      "参考测试集_关键词.xlsx": ["1", "2"],
    },
  },
};

const transformData = (data, sceneVal) => {
  // console.log("transformData");
  // console.log(data);
  const result = [];
  let index = 0;
  function recurse(currentData, path) {
    const isLeafNode = Object.keys(currentData).length === 0;

    if (isLeafNode) {
      // 处理空目录（叶子节点）
      result.push(createRecord(path, null));
      return;
    }

    // 遍历当前节点的所有属性
    for (const key in currentData) {
      if (currentData.hasOwnProperty(key)) {
        const newPath = path.concat(key);
        const value = currentData[key];

        if (isFile(value)) {
          // 处理文件节点
          result.push(createRecord(newPath, value));
        } else {
          // 递归处理子目录
          recurse(value, newPath);
        }
      }
    }
  } // 判断是否为文件（数组或非对象类型）
  function isFile(value) {
    return Array.isArray(value) || typeof value !== "object" || value === null;
  }

  // 创建标准化记录
  function createRecord(path, files) {
    return {
      id: index++,
      directoryA: path[0] || null,
      directoryB: path[1] || null,
      directoryC: path[2] || null,
      directoryD: path[3] || null,
      files: files,
    };
  }
  if (sceneVal === "ASR") {
    result.length = 0;
    recurse(data.ASRAllData, []);
  } else if (sceneVal === "label") {
    recurse(data.ASRTagging, []);
  } else if (sceneVal === "MT") {
    recurse(data.MTAllData, []);
    result.forEach((item) => {
      if (item.directoryC === null) {
        item.directoryC = "";
      }
    });
  } else if (sceneVal === "TTS") {
    recurse(data.TTSAllData, []);
  }
  // console.log("result");
  // console.log(result);
  return result;
};

const fileDirectory = ref("");
const interpretatiionDialog = ref(false);

const handlerAdd = (dataset) => {
  interpretatiionDialog.value = true;
  let directory = "";
  switch (interpretationScene.value) {
    case "ASR":
      directory += "testcases_asr/";
      break;
    case "label":
      directory += "asr_label/";
      break;
    case "MT":
      directory += "testcases_mt/";
      break;
    case "TTS":
      directory += "testcases_tts/";
  }
  directory += dataset.directoryA + "/" + dataset.directoryB;
  if (interpretationScene.value === "ASR") {
    directory += "/" + dataset.directoryC + "/" + dataset.directoryD;
  } else if (
    interpretationScene.value === "label" ||
    interpretationScene.value === "TTS"
  ) {
    directory += "/" + dataset.directoryC;
  }

  console.log("directory");
  console.log(directory);

  fileDirectory.value = directory;
};

//上传文件相关
const upload = ref<UploadInstance>();

const uploadFile = async (file) => {
  const isLt2M = file.file.size / 1024 / 1024 < 2;
  if (!isLt2M) {
    ElMessage.error("上传文件大小不能超过 2MB!");
    // upload.value!.clearFiles();
    fileList.value = [];
  } else {
    const formData = new FormData();
    formData.append("directory", fileDirectory.value);
    formData.append("file", file.file);

    try {
      const response = await addInterpretationFile(formData);
      console.log("上传成功:", response.data);
    } catch (error) {
      console.error("上传失败:", error);
    }
  }
  fileDirectory.value = "";
};
const handleSuccess = (response, file, fileList) => {
  ElMessage.success("文件上传成功");
  console.log("文件上传成功", response, file, fileList);
};

const handleError = (error, file, fileList) => {
  ElMessage.error("文件上传失败");
  console.log("文件上传失败", error, file, fileList);
};

const handleExceed: UploadProps["onExceed"] = (files) => {
  // upload.value!.clearFiles();
  fileList.value = [];
  const file = files[0] as UploadRawFile;
  file.uid = genFileId();
  upload.value!.handleStart(file);
};
const handleClose = () => {
  // upload.value!.clearFiles();
  fileList.value = [];
  fileDirectory.value = "";
  interpretatiionDialog.value = false;
};

const uploadRef = ref(null);
const fileList = ref([]); // 存储选择的文件

const handleFileChange = (file, files) => {
  console.log("files");
  console.log(files);
  // 更新文件列表
  fileList.value = files;
};

const handleMultiUpload = async () => {
  console.log("fileList");
  console.log(fileList.value);
  if (fileList.value.length === 0) {
    ElMessage.warning("请选择文件");
    return;
  }

  try {
    const formData = new FormData();

    // 添加所有文件到FormData
    formData.append("directory", fileDirectory.value);
    fileList.value.forEach((file) => {
      formData.append("files", file.raw); // file.raw是原始文件对象
    });

    const response = await addInterpretationFile(formData);

    ElMessage.success(`${response.data.message}`);
    fileList.value = [];
    interpretatiionDialog.value = false;
    loading.value = true;
    loadInterpretationData();
  } catch (error) {
    ElMessage.error("文件上传失败");
    console.error("上传错误:", error);
  }
};

//添加新目录
interface RuleForm {
  directoryA: String;
  directoryB: String;
  directoryC: String;
  name: string;
}
const interDirectoryDialog = ref(false);
const directoryFormRef = ref<FormInstance>();
const directoryForm = reactive<RuleForm>({
  directoryA: "",
  directoryB: "",
  directoryC: "",
  name: "",
});
const directoryOptionsB = ref([]);
const directoryOptionsC = ref([]);

const directoryRules = reactive<FormRules<RuleForm>>({
  name: [{ required: true, message: "请输入新目录名称", trigger: "change" }],
});

const interpretationDirectoryOpen = () => {
  interDirectoryDialog.value = true;
  resetDirectoryForm();
};

const directoryAChange = (value) => {
  directoryOptionsB.value = [];
  const uniqueOptions = new Set();
  if (interpretationScene.value === "ASR") {
    Object.keys(interpretationData.value.ASRAllData[value]).forEach(
      (item: any) => {
        uniqueOptions.add(item);
      }
    );
  } else if (interpretationScene.value === "label") {
    Object.keys(interpretationData.value.ASRTagging[value]).forEach(
      (item: any) => {
        uniqueOptions.add(item);
      }
    );
  } else if (interpretationScene.value === "MT") {
    Object.keys(interpretationData.value.MTAllData[value]).forEach(
      (item: any) => {
        uniqueOptions.add(item);
      }
    );
  } else if (interpretationScene.value === "TTS") {
    Object.keys(interpretationData.value.TTSAllData[value]).forEach(
      (item: any) => {
        uniqueOptions.add(item);
      }
    );
  }
  // 将去重后的选项添加到 directoryOptionsB.value
  uniqueOptions.forEach((item) => {
    directoryOptionsB.value.push({
      value: item,
      label: item,
    });
  });
};

const directoryBChange = (value) => {
  directoryOptionsC.value = [];
  const uniqueOptions = new Set();
  if (interpretationScene.value === "ASR") {
    Object.keys(
      interpretationData.value.ASRAllData[directoryForm.directoryA][value]
    ).forEach((item: any) => {
      uniqueOptions.add(item);
    });
  } else if (interpretationScene.value === "label") {
    Object.keys(
      interpretationData.value.ASRTagging[directoryForm.directoryA][value]
    ).forEach((item: any) => {
      uniqueOptions.add(item);
    });
  } else if (interpretationScene.value === "MT") {
    Object.keys(
      interpretationData.value.MTAllData[directoryForm.directoryA][value]
    ).forEach((item: any) => {
      uniqueOptions.add(item);
    });
  } else if (interpretationScene.value === "TTS") {
    Object.keys(
      interpretationData.value.TTSAllData[directoryForm.directoryA][value]
    ).forEach((item: any) => {
      uniqueOptions.add(item);
    });
  }
  // 将去重后的选项添加到 optionsC.value
  uniqueOptions.forEach((item) => {
    directoryOptionsC.value.push({
      value: item,
      label: item,
    });
  });
};

const resetDirectoryForm = () => {
  directoryForm.directoryA = "";
  directoryForm.directoryB = "";
  directoryForm.directoryC = "";
  directoryForm.name = "";
};
const handleDirectoryClose = () => {
  resetDirectoryForm();
  directoryFormRef.value?.resetFields();
  interDirectoryDialog.value = false;
};

const computedFullPath = computed(() => {
  const parts = [];
  switch (interpretationScene.value) {
    case "ASR":
      parts.push("testcases_asr");
      break;
    case "label":
      parts.push("asr_label/");
      break;
    case "MT":
      parts.push("testcases_mt");
      break;
    case "TTS":
      parts.push("testcases_tts");
  }

  // 添加一级目录（如果存在）
  if (directoryForm.directoryA) {
    const dirA = optionsA.value.find(
      (item) => item.value === directoryForm.directoryA
    );
    dirA && parts.push(dirA.label);
  }

  // 添加二级目录（如果存在）
  if (directoryForm.directoryB) {
    const dirB = directoryOptionsB.value.find(
      (item) => item.value === directoryForm.directoryB
    );
    dirB && parts.push(dirB.label);
  }

  // 添加三级目录（如果是ASR场景且存在）
  if (interpretationScene.value === "ASR" && directoryForm.directoryC) {
    const dirC = directoryOptionsC.value.find(
      (item) => item.value === directoryForm.directoryC
    );
    dirC && parts.push(dirC.label);
  }

  // 添加新目录名称（如果已输入）
  if (directoryForm.name) {
    parts.push(directoryForm.name);
  }

  // 拼接完整路径
  return parts.length > 0 ? parts.join("/") : "请选择目录并输入名称";
});

const handleSubmitDirectory = () => {
  addInterpretationDirectory({
    directory: computedFullPath.value,
  })
    .then((res) => {
      if (res.status === 200) {
        ElMessage({
          type: "success",
          message: res.data.success,
        });
      }
      handleDirectoryClose();
      loading.value = true;
      loadInterpretationData();
    })
    .catch((error) => {
      ElMessage({
        type: "error",
        message: error.response.data.error,
      });
    });
};

const handlerDirectoryDelete = (dataset) => {
  console.log("dataset");
  console.log(dataset);
  let directory = "";
  switch (interpretationScene.value) {
    case "ASR":
      directory += "testcases_asr/";
      break;
    case "label":
      directory += "asr_label/";
      break;
    case "MT":
      directory += "testcases_mt/";
      break;
    case "TTS":
      directory += "testcases_tts/";
  }
  directory +=
    dataset.directoryA +
    (dataset.directoryB !== null ? "/" + dataset.directoryB : "") +
    (dataset.directoryC !== null ? "/" + dataset.directoryC : "") +
    (dataset.directoryD !== null ? "/" + dataset.directoryD : "");
  // console.log("directory");
  // console.log(directory);
  ElMessageBox.confirm(
    "确认删除目录：</br>" +
      directory +
      " 吗？</br>此操作会删除该目录及其下全部文件，且无法撤回！",
    "提示",
    {
      confirmButtonText: "确认",
      cancelButtonText: "取消",
      type: "warning",
      dangerouslyUseHTMLString: true,
    }
  )
    .then(() => {
      deleteInterpretationDirectory({ directory: directory }).then(
        (res) => {
          ElMessage({
            type: "success",
            message: "删除成功",
          });
          loading.value = true;
          loadInterpretationData();
        },
        (err) => {
          ElMessage({
            type: "error",
            message: "删除失败：" + err,
          });
        }
      );
    })
    .catch(() => {
      // ElMessage({
      //   type: "info",
      //   message: "取消删除",
      // });
    });
};

onMounted(async () => {
  tags.value = store.getters.getTags;
  screeningType.value = store.getters.getScreeningType;
  console.log("route type:", route.query.type);
  // await fleshDatasets();
  if (route.query.type) {
    activeTab.value = route.query.type as string;
    if (route.query.refresh) {
      if (activeTab.value === "openSource") {
        await fleshDatasets("1");
      } else if (activeTab.value === "domain") {
        await fleshDatasets("2");
      } else if (activeTab.value === "dev") {
        await fleshDatasets("3");
      } else if (activeTab.value === "interpretation") {
        await loadInterpretationData();
      }
    } else if (activeTab.value === "interpretation") {
      await loadInterpretationData();
      loadOptionsA("ASR");
    }
  } else {
    activeTab.value = "openSource";
  }
  setTimeout(() => {
    disableSlide.value = false;
  }, 1);
  tabChange(activeTab.value);

  // 监听 mainContentContainer 尺寸变化，保持列表表格与筛选栏高度一致
  nextTick(() => {
    updateTableHeight();
    const containers = document.querySelectorAll(".mainContentContainer");
    if (typeof ResizeObserver !== "undefined") {
      tableResizeObserver = new ResizeObserver(updateTableHeight);
      containers.forEach((c) => tableResizeObserver.observe(c));
    }
  });
  window.addEventListener("resize", updateTableHeight);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", updateTableHeight);
  if (tableResizeObserver) {
    tableResizeObserver.disconnect();
    tableResizeObserver = null;
  }
});
</script>

<style scoped>
.editClass {
  /* margin-right: 10px; */
}

.button-container {
  /* position: absolute;  */
  margin-left: auto;
  margin-right: 10px;
  display: flex;
  top: 10px;
  right: 10px;
  gap: 10px;
}

.description {
  font-size: 12px;
  color: #9a9a9a;
}

.screening {
  /* margin-left: 10px; */
  /* padding-top: 20px; */
  margin-left: 0 !important ;
  background-color: #fff;
  border-radius: 5px;
  box-shadow: 0px 0px 8px rgba(158, 158, 158, 0.3);
  /* margin-bottom: 10px; */
}

.screeningButtonGroup {
  height: 40px;
  /* flex-wrap: nowrap; */
}

.screeningButtonGroup :deep(.el-radio-button__inner) {
  background-color: #f3f3f3;
  color: #333;
  border: none;
}

.screeningButtonGroup
  :deep(.el-radio-button.is-active .el-radio-button__inner) {
  background-color: #0067d1;
  color: #fff;
  border: none;
}

.elIconLabel {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 5px;
}

.checkButtonGroup {
  width: 100%;
  margin: 0 auto;
}

.checkButtonGroup .el-checkbox-button {
  width: 48%;
  margin-bottom: 10px;
}

.checkButtonGroup .el-checkbox-button :deep(.el-checkbox-button__inner) {
  /* margin-right: 10px; */
  padding: 8px 8px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.checkButtonGroup .el-checkbox-button:nth-child(2n-1) {
  margin-right: 4%;
}

.checkButtonGroup :deep(.el-checkbox-button .el-checkbox-button__inner) {
  background-color: #e7ebfe;
  color: #265ab7;
  border: 1px solid transparent;
  border-radius: 6px;
  width: 100%;
}

.checkButtonGroup
  :deep(.el-checkbox-button.is-checked .el-checkbox-button__inner) {
  color: #ffffff;
  background-color: #5990fd;
  border: none;
}

inputSearch {
  width: 140px;
  height: 32px;
  flex-shrink: 0;
}
.selectOrder {
  width: 100px;
  height: 32px;
  flex-shrink: 0;
}
.cascader-select {
  width: 100px;
  flex-shrink: 0;
}

/* 确保所有组件强制不换行 */
.selectOrder,
.inputSearch,
.registerButton,
.cascader-select {
  flex-shrink: 0;
}

/* 单独为注册按钮设置样式 */
.registerButton {
  width: 70px;
  height: 32px;
  padding: 0 10px;
  font-size: 12px;
  margin-left: 8px;
}
.tagsBox {
  height: 19px;
  margin-top: 10px;
  display: flex;
  gap: 0.5rem;
}

.tags {
  border-radius: 8px;
  padding: 0px 5px;
  color: rgb(75, 72, 255);
  background-color: rgba(220, 220, 255, 0.712);
  /* transform: scale(0.8); */
  transform-origin: top left;
}

.in-use-badge {
  margin-left: 8px;
  flex-shrink: 0;
  font-size: 12px;
  line-height: 20px;
  padding: 0 8px;
  border-radius: 10px;
  color: #909399;
  background-color: #f0f2f5;
  border: 1px solid #dcdfe6;
  white-space: nowrap;
  user-select: none;
}

.in-use-badge.in-use-active {
  color: #4aa155;
  background-color: #eaffed;
  border-color: #b7e3bd;
}

/* 列表/卡片模式切换按钮 */
.view-mode-toggle {
  flex-shrink: 0;
}

.view-mode-toggle :deep(.el-radio-button__inner) {
  height: 30px;
  line-height: 30px;
  padding: 0 12px;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
}

/* 列表模式表格 */
.dataset-list-table {
  background-color: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.dataset-list-table :deep(.el-table__header th) {
  background-color: #f5f7fa;
  color: #333;
  font-weight: 600;
}

.dataset-list-table :deep(.el-table__row) {
  cursor: pointer;
}

/* 表格内标题旁的“使用中”标识 */
.table-inuse {
  margin-left: 8px;
  display: inline-block;
  vertical-align: middle;
}

/* 表格内标签 */
.table-tags {
  height: auto;
  margin-top: 0;
  flex-wrap: wrap;
  row-gap: 4px;
}

/* 表格操作列 */
.table-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  white-space: nowrap;
}

.description_data {
  margin-top: 10px;
  font-size: 12px;
  color: rgb(119, 119, 119);
  line-height: 1.4;
  height: calc(12px * 1.4 * 2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  /* 指定最多显示几行 */
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.other_info {
  margin-top: 10px;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
}

.info_left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.littleInfo_1 {
  display: flex;
  align-items: center;
  height: 25px;
  background-color: #eaffed;
  color: #4aa155;
  border-radius: 8px;
  padding: 0px 2px;
  gap: 0.1rem;
  justify-content: center;
  width: 110px;
}

.littleInfo_2 {
  display: flex;
  align-items: center;
  height: 25px;
  background-color: #e7f1ff;
  color: #3a7aaf;
  border-radius: 8px;
  padding: 0px 3px;
  gap: 0.1rem;
  justify-content: center;
  width: 56px;
}

.littleInfo_3 {
  display: flex;
  align-items: center;
  height: 25px;
  background-color: #ffe7ff;
  color: #cf6ef5;
  border-radius: 8px;
  padding: 0px 3px;
  gap: 0.1rem;
  justify-content: center;
  width: 56px;
}

.el-main {
  align-self: flex-start;
  padding: 0;
  flex-wrap: wrap;
  display: flex;
}

.dataContainer {
  background-color: #f5f5f5;
  width: 100%;
  height: 100%;
  display: flex;
  /* padding: 20px; */
  max-width: 100%;
  min-height: 100%;
  padding: 0px 28px 20px;
  gap: 12px;
  flex-direction: column;
}

.el-tabs {
  flex: 1;
}

.el-tabs :deep(.el-tabs__content) {
  display: flex;
  flex-direction: column;
}

.el-tabs__header {
}

.el-tab-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* datasetDevelopment横栏样式 - 基于modelSquare.vue模式 */

.ds-header {
  flex: 0 0 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-radius: 6px;
  background-color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  border-bottom: 1px solid #eee;
  transition: 0.3s ease-in-out;
  margin-bottom: 16px;
}

.ds-btns {
  border-radius: 4px;
  overflow: hidden;
}

.ds-btns button:not(:last-child) {
  flex: 1 1 0;
  min-height: 0;
  border: none;
  outline: none;
  background-color: rgb(242, 242, 242);
  color: rgb(51, 51, 51);
  font-size: 14px;
  padding: 8px 16px;
  transition: 0.3s ease-in-out;
  line-height: 1;
}

.ds-btns button.active {
  background-color: rgb(0, 103, 209);
  color: white;
}

.ds-search {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ds-search .el-input {
  height: 30px;
  min-width: 280px;
  border-radius: 4px;
  border: 1px solid rgb(201, 201, 201);
  /* padding: 0 8px; */
  font-size: 12px;
}

.ds-search .el-input:focus {
  border-color: rgb(0, 103, 209);
  outline: 1px solid rgb(0, 103, 209);
}

.ds-search .el-select {
  height: 30px;
  min-width: 120px;
}

.ds-cascader {
  height: 30px;
  min-width: 200px;
  border-radius: 4px;
  border: 1px solid rgb(201, 201, 201);
}

.register-btn {
  background-color: rgb(0, 103, 209);
  color: white;
  height: 30px;
  min-width: 120px;
  border: none;
  outline: none;
  border-radius: 4px;
  transition: all 0.2s ease-in-out;
}

.register-btn:hover {
  background-color: rgb(0, 90, 178);
}

.register-btn:active {
  background-color: rgb(0, 80, 160);
}

/* “使用中”开关 */
.inuse-switch {
  flex-shrink: 0;
}

.inuse-switch :deep(.el-switch__label) {
  font-size: 12px;
  color: #555;
}

/* 修改关闭筛选器的按钮样式 */
.closebtn {
  background-color: rgb(242, 242, 242);
  color: rgb(51, 51, 51);
  border: none;
  outline: none;
  border-radius: 4px;
  padding: 8px 12px;
  font-size: 14px;
  transition: all 0.2s ease-in-out;
}

.closebtn:hover {
  background-color: rgb(230, 230, 230);
}

.dataShowContainer {
  /* padding: 5px 0px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06); */
  /* border-radius: 4px; */
  margin-top: 10px;
  display: flex;
  flex: 1;
  gap: 16px;
}

.datasetContainer {
  position: relative;
  align-items: center;
  color: rgba(18, 19, 22, 0.8);
  line-height: 36px;
  height: 36px;
  margin-bottom: 18px;
}

.el-card {
  border-radius: 8px;
}

.el-link :deep(.el-link__inner) {
  display: block;
}

.mainContentContainer {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.mainCardContainer {
  display: flex;
  flex-direction: column;
}

.list-grid {
  height: 25%;
  width: 100%;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(375px, 1fr));
  gap: 1rem;
}

.el-card-container {
  max-height: 100%;
  border-radius: 8px;
  border-width: 2px;
}

.el-card-container:hover {
  border-color: #0590f3;
  border-width: 2px;
}

.newrank {
  position: absolute;
  top: 104px;
  right: 42px;
  box-sizing: border-box;
  font-size: 10px;
  line-height: 14px;
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

.pagination {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 10px;
  margin-right: 10px;
}

.no-slide :deep(.el-tabs__active-bar) {
  transition: none !important;
}

.closebtn {
  border-color: #d9d9d9;
  box-shadow: 0 2px 0 rgba(0, 0, 0, 0.02);
  font-size: 16px;
  line-height: 1.5;
  height: 30px;
  margin-left: 20px;
  padding: 7px 15px;
  border-radius: 8px;
}

.share-user-table {
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  padding: 4px 12px 10px;
}

.share-user-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

.share-user-row + .share-user-row {
  border-top: 1px dashed #ebeef5;
}

.share-user-table-header {
  font-size: 13px;
  color: #909399;
  border-bottom: 1px solid #ebeef5 !important;
}

.share-user-name {
  flex: 1;
  min-width: 0;
}

.share-user-perm {
  width: 48px;
  text-align: center;
  flex-shrink: 0;
}

.share-user-delete {
  width: 32px;
  text-align: center;
  flex-shrink: 0;
}
</style>
