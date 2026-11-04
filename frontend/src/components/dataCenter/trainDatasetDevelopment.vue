<template>
  <div class="dataContainer">
    <el-tabs
      v-model="activeTab"
      class="tabsContainer"
      @tab-click="tabClick"
      :class="{ 'no-slide': disableSlide }"
    >
      <el-tab-pane label="通用训练集" name="openSource">
        <div class="description">基准资源社区，提供丰富基准信息</div>
        <header class="ds-header">
          <div class="ds-btns">
            <button :class="{ active: screeningType === 'all' }" @click="screeningType = 'all'">全部</button>
            <button :class="{ active: screeningType === 'self' }" @click="screeningType = 'self'">自建</button>
            <button :class="{ active: screeningType === 'open' }" @click="screeningType = 'open'">开源</button>
            <el-button class="closebtn" @click="hideScreening">
              <el-icon><Operation /></el-icon>
              <span v-if="!isClosed">展开筛选器</span>
              <span v-else>隐藏筛选器</span>
            </el-button>
          </div>
          <div class="ds-search">
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
            ></el-cascader>
            <el-input v-model="inputDatasetName" placeholder="请输入训练集名称" :suffix-icon="Search">
            </el-input>
            <el-select v-model="selectValue" placeholder="Select" style="width: 120px">
              <el-option
                v-for="item in options"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-button type="primary" class="register-btn" @click="datasetRegister">注册训练集</el-button>
          </div>
        </header>
        <el-container class="dataShowContainer">
          <el-aside class="screening" width="250px" v-show="isClosed">
            <div style="margin: 20px">
              <div style="font-size: 18px;font-weight: 700;">筛选</div>
              <div style="margin: 20px 0; width: 100%">
                <div class="elIconLabel">
                  <el-icon><Reading /></el-icon>
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
                </el-checkbox-group>
              </div>
              <div style="margin: 20px 0; width: 100%">
                <div class="elIconLabel">
                  <el-icon><Picture /></el-icon>
                  <b>图像</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <el-checkbox-button label="文字识别">文字识别</el-checkbox-button>
                  <el-checkbox-button label="图像分类">图像分类</el-checkbox-button>
                  <el-checkbox-button label="图像生成">图像生成</el-checkbox-button>
                  <el-checkbox-button label="图像编辑">图像编辑</el-checkbox-button>
                </el-checkbox-group>
              </div>
              <div style="margin: 20px 0; width: 100%">
                <div class="elIconLabel">
                  <el-icon><Headset /></el-icon>
                  <b>音频</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <el-checkbox-button label="语音识别">语音识别</el-checkbox-button>
                  <el-checkbox-button label="语音合成">语音合成</el-checkbox-button>
                  <el-checkbox-button label="音频分类">音频分类</el-checkbox-button>
                  <el-checkbox-button label="音频生成">音频生成</el-checkbox-button>
                </el-checkbox-group>
              </div>
              <div style="margin: 20px 0; width: 100%">
                <div class="elIconLabel">
                  <el-icon><VideoCamera /></el-icon>
                  <b>视频</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <el-checkbox-button label="动作识别">动作识别</el-checkbox-button>
                  <el-checkbox-button label="行为理解">行为理解</el-checkbox-button>
                  <el-checkbox-button label="视频生成">视频生成</el-checkbox-button>
                  <el-checkbox-button label="视频编辑">视频编辑</el-checkbox-button>
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
                      <div class="button-container" v-if="item.can_edit">
                        <el-link underline="never" @click.stop="handlerEdit(key, item)">
                          <el-icon class="editClass"><Edit /></el-icon>
                        </el-link>
                        <el-link underline="never" @click.stop="handlerDelete(key, item)">
                          <el-icon class="editClass"><Delete /></el-icon>
                        </el-link>
                      </div>
                    </div>
                    <el-link underline="never" style="padding: 0 10px 10px 10px;display: block;">
                      <div class="tagsBox">
                        <div v-for="tag in item.train_tags" :key="tag" class="tags">{{ tag }}</div>
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
                            <el-icon><Clock /></el-icon>
                            <span>{{ item.establish_time.split(" ")[0] }}</span>
                          </div>
                          <div class="littleInfo_2">
                            <el-icon><Download /></el-icon>
                            <span>{{ item.download_count || 0 }}</span>
                          </div>
                          <div class="littleInfo_3">
                            <el-icon><View /></el-icon>
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
      <el-tab-pane label="领域训练集" name="domain">
        <div class="description">基准资源社区，提供丰富基准信息</div>
        <header class="ds-header">
          <div class="ds-btns">
            <button :class="{ active: screeningType === 'all' }" @click="screeningType = 'all'">全部</button>
            <button :class="{ active: screeningType === 'self' }" @click="screeningType = 'self'">自建</button>
            <button :class="{ active: screeningType === 'open' }" @click="screeningType = 'open'">开源</button>
            <el-button class="closebtn" @click="hideScreening">
              <el-icon><Operation /></el-icon>
              <span v-if="!isClosed">展开筛选器</span>
              <span v-else>隐藏筛选器</span>
            </el-button>
          </div>
          <div class="ds-search">
            <el-input v-model="inputDatasetName" placeholder="请输入训练集名称" :suffix-icon="Search">
            </el-input>
            <el-select v-model="selectValue" placeholder="Select" style="width: 120px">
              <el-option
                v-for="item in options"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-button type="primary" class="register-btn" @click="datasetRegister">注册训练集</el-button>
          </div>
        </header>
        <el-container class="dataShowContainer">
          <el-aside class="screening" width="250px">
            <div style="margin: 20px">
              <div style="margin: 10px 0; width: 200px">
                <div class="elIconLabel">
                  <el-icon><Reading /></el-icon>
                  <b>文本</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <el-checkbox-button label="运维智能">运维智能</el-checkbox-button>
                  <el-checkbox-button label="AISF_NEW">AISF_NEW</el-checkbox-button>
                  <el-checkbox-button label="业务智能">业务智能</el-checkbox-button>
                  <el-checkbox-button label="算力主机">算力主机</el-checkbox-button>
                  <el-checkbox-button label="AISF">AISF</el-checkbox-button>
                </el-checkbox-group>
              </div>
              <div style="margin: 20px 0; width: 100%">
                <div class="elIconLabel">
                  <el-icon><Picture /></el-icon>
                  <b>图像</b>
                </div>
                <div style="height: 10px"></div>
                <el-checkbox-group v-model="tags" class="checkButtonGroup">
                  <el-checkbox-button label="穿搭">穿搭</el-checkbox-button>
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
                      <div class="button-container" v-if="item.can_edit">
                        <el-link underline="never" @click.stop="handlerEdit(key, item)">
                          <el-icon class="editClass"><Edit /></el-icon>
                        </el-link>
                        <el-link underline="never" @click.stop="handlerDelete(key, item)">
                          <el-icon class="editClass"><Delete /></el-icon>
                        </el-link>
                      </div>
                    </div>
                    <el-link underline="never" style="padding: 0 10px 10px 10px;display: block;">
                      <div class="tagsBox">
                        <div v-for="tag in item.train_tags" :key="tag" class="tags">{{ tag }}</div>
                      </div>
                      <div>
                        <el-tooltip :content="item.description || '暂无描述'">
                          <span class="description_data">{{ item.description || "暂无描述" }}</span>
                        </el-tooltip>
                      </div>
                      <div class="other_info">
                        <div class="info_left">
                          <el-avatar :size="30" src="/images/icap-mark-v1.svg"></el-avatar>
                          <div>{{ item.group || "domain" }}</div>
                        </div>
                        <div class="info_left">
                          <div class="littleInfo_1" v-if="item.establish_time">
                            <el-icon><Clock /></el-icon>
                            <span>{{ item.establish_time.split(" ")[0] }}</span>
                          </div>
                          <div class="littleInfo_2">
                            <el-icon><Download /></el-icon>
                            <span>{{ item.download_count || 0 }}</span>
                          </div>
                          <div class="littleInfo_3">
                            <el-icon><View /></el-icon>
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
      <el-tab-pane label="开发态训练集" name="dev">
        <div class="description">基准资源社区，提供丰富基准信息</div>
        <header class="ds-header">
          <div class="ds-btns">
            <button :class="{ active: screeningType === 'all' }" @click="screeningType = 'all'">全部</button>
            <button :class="{ active: screeningType === 'self' }" @click="screeningType = 'self'">自建</button>
            <button :class="{ active: screeningType === 'open' }" @click="screeningType = 'open'">开源</button>
            <el-button class="closebtn" @click="hideScreening">
              <el-icon><Operation /></el-icon>
              <span v-if="!isClosed">展开筛选器</span>
              <span v-else>隐藏筛选器</span>
            </el-button>
          </div>
          <div class="ds-search">
            <el-input v-model="inputDatasetName" placeholder="请输入训练集名称" :suffix-icon="Search">
            </el-input>
            <el-select v-model="selectValue" placeholder="Select" style="width: 120px">
              <el-option
                v-for="item in options"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-button type="primary" class="register-btn" @click="datasetRegister">注册训练集</el-button>
          </div>
        </header>
        <el-container class="dataShowContainer">
          <el-aside class="screening" width="250px">
            <div style="margin: 20px">
              <div style="margin: 10px 0; width: 200px">
                <div class="elIconLabel">
                  <el-icon><Reading /></el-icon>
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
              <div style="margin: 20px 0; width: 100%">
                <div class="elIconLabel">
                  <el-icon><Picture /></el-icon>
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
                      <div class="button-container" v-if="item.can_edit">
                        <el-link underline="never" @click.stop="handlerEdit(key, item)">
                          <el-icon class="editClass"><Edit /></el-icon>
                        </el-link>
                        <el-link underline="never" @click.stop="handlerDelete(key, item)">
                          <el-icon class="editClass"><Delete /></el-icon>
                        </el-link>
                      </div>
                    </div>
                    <el-link underline="never" style="padding: 0 10px 10px 10px;display: block;">
                      <div class="tagsBox">
                        <div v-for="tag in item.train_tags" :key="tag" class="tags">{{ tag }}</div>
                      </div>
                      <div>
                        <el-tooltip :content="item.description || '暂无描述'">
                          <span class="description_data">{{ item.description || "暂无描述" }}</span>
                        </el-tooltip>
                      </div>
                      <div class="other_info">
                        <div class="info_left">
                          <el-avatar :size="30" src="/images/icap-mark-v1.svg"></el-avatar>
                          <div>{{ item.group || "dev" }}</div>
                        </div>
                        <div class="info_left">
                          <div class="littleInfo_1" v-if="item.establish_time">
                            <el-icon><Clock /></el-icon>
                            <span>{{ item.establish_time.split(" ")[0] }}</span>
                          </div>
                          <div class="littleInfo_2">
                            <el-icon><Download /></el-icon>
                            <span>{{ item.download_count || 0 }}</span>
                          </div>
                          <div class="littleInfo_3">
                            <el-icon><View /></el-icon>
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
    </el-tabs>
    <el-dialog v-model="editVisible" title="编辑训练资源" width="600px"><el-form label-position="top"><el-form-item label="名称"><el-input v-model="editForm.name" /></el-form-item><el-form-item label="描述"><el-input v-model="editForm.description" type="textarea" /></el-form-item><el-form-item label="可见范围"><el-select v-model="editForm.visibility"><el-option label="仅自己可见" value="private"/><el-option label="对所有用户开放" value="public"/></el-select></el-form-item></el-form><template #footer><el-button @click="editVisible=false">取消</el-button><el-button type="primary" @click="saveTraining">保存</el-button></template></el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, watch } from "vue";
import axios from "axios";
import { useRouter, useRoute } from "vue-router";
import { useStore } from "vuex";
import { ElMessage, ElMessageBox } from "element-plus";

// 从当前账号可见的资源库读取训练数据。
async function getDatasets(isField: string): Promise<any> {
  const {data: rows}=await axios.get('/api/datasets');
  const result:Record<string,any>={};
  for(const row of rows.filter(row=>row.category==='训练集')) result[row.id]={
    dataset_name:row.name,train_tags:row.tags||[],description:row.description,
    group:row.owner_name||'平台资源',establish_time:row.created_at||'',
    download_count:(row.files||[]).reduce((n,file)=>n+(file.downloads||0),0),view_count:row.views||0,
    is_open_source:row.visibility==='public',visibility:row.visibility,
    can_edit:localStorage.getItem('ic_role')==='admin'||row.owner_user_id===localStorage.getItem('ic_user_id'),
    files:row.files||[],is_field:isField,
  };
  return isField==='1'?result:{};
}
async function deleteDatasets(requestData:{dataset_id:string;is_field:string}):Promise<any>{
  return axios.delete('/api/datasets/'+encodeURIComponent(requestData.dataset_id));
}

/** 从 HG URL 或仓库名称中提取数据集标识 */
function extractDatasetKey(urlOrName: string): string {
  // 尝试从 URL 中提取仓库名
  const match = urlOrName.match(/huggingface\.co\/(?:datasets|models)\/([^/\s]+(?:\/[^/\s]+)?)/i);
  if (match) return match[1];
  // 直接返回输入
  return urlOrName.trim();
}

// ============================================================
// 3. 组件逻辑
// ============================================================
const activeTab = ref("");
const screeningType = ref("all");
const tags = ref([]);
const router = useRouter();
const route = useRoute();
const store = useStore();
const inputDatasetName = ref("");
const selectValue = ref("name");
const dataInfos = ref({});

const props = {
  emitPath: false,
  multiple: true,
};

const tagsOptions = ref([
  {
    value: 1,
    label: "文本",
    children: [
      { value: "知识百科", label: "知识百科" },
      { value: "逻辑推理", label: "逻辑推理" },
      { value: "数学", label: "数学" },
      { value: "代码", label: "代码" },
      { value: "工具", label: "工具" },
      { value: "指令遵从", label: "指令遵从" },
      { value: "长文本", label: "长文本" },
    ],
  },
  {
    value: 2,
    label: "图像",
    children: [
      { value: "文字识别", label: "文字识别" },
      { value: "图像分类", label: "图像分类" },
      { value: "图像生成", label: "图像生成" },
      { value: "图像编辑", label: "图像编辑" },
    ],
  },
  {
    value: 3,
    label: "音频",
    children: [
      { value: "语音识别", label: "语音识别" },
      { value: "语音合成", label: "语音合成" },
      { value: "音频分类", label: "音频分类" },
      { value: "音频生成", label: "音频生成" },
    ],
  },
  {
    value: 4,
    label: "视频",
    children: [
      { value: "动作识别", label: "动作识别" },
      { value: "行为理解", label: "行为理解" },
      { value: "视频生成", label: "视频生成" },
      { value: "视频编辑", label: "视频编辑" },
    ],
  },
]);

const handelTagsChange = () => {};

const editKey=ref(''), editVisible=ref(false),editForm=ref({name:'',description:'',visibility:'private'});
async function saveTraining(){await axios.put('/api/datasets/'+encodeURIComponent(editKey.value),{...editForm.value,category:'训练集',version:'main'});editVisible.value=false;await loadDatasets('1');}
const handlerEdit = (key, item) => {
  editKey.value=key; editForm.value={name:item.dataset_name,description:item.description||'',visibility:item.visibility||'private'}; editVisible.value=true;
};

const loadDatasets = async (isField: string) => {
  try {
    const res = await getDatasets(isField);
    dataInfos.value = res;
  } catch (err) {
    console.error('[trainDataset] 加载训练集失败:', err);
    dataInfos.value = {};
  }
};

const handlerDelete = (key, item) => {
  ElMessageBox.confirm(
    "确认删除训练集： " + key + ": " + item.dataset_name + " 吗？",
    "提示",
    {
      confirmButtonText: "确认",
      cancelButtonText: "取消",
      type: "warning",
    }
  )
    .then(async () => {
      try {
        await deleteDatasets({ dataset_id: key, is_field: item.is_field || '' });
        ElMessage({ type: "success", message: "删除成功" });
        await loadDatasets(activeTab.value === "openSource" ? "1" : activeTab.value === "domain" ? "2" : "3");
      } catch (err) {
        ElMessage({ type: "error", message: "删除失败：" + err });
      }
    })
    .catch(() => {
      ElMessage({ type: "info", message: "取消删除" });
    });
};

const tabChange = async (tabName: string) => {

  if (tabName === "openSource") {
    await loadDatasets("1");
  } else if (tabName === "domain") {
    await loadDatasets("2");
  } else if (tabName === "dev") {
    await loadDatasets("3");
  }
};

const tabClick = async (tab, event) => {
  tags.value = [];
  screeningType.value = "all";
  await tabChange(tab.props.name);
  router.push({ name: "trainDatasetDevelopment", query: { type: tab.props.name } });
};

const options = [
  { value: "name", label: "名称" },
  { value: "updateTime", label: "更新时间" },
  { value: "views", label: "浏览量" },
];

/* 分页相关 */
const pageSize = ref(12);
const currentPage = ref(1);
const totalItems = computed(() => {
  return Object.keys(filteredDataInfos.value).length;
});
const handleSizeChange = (val) => {
  pageSize.value = val;
  currentPage.value = 1;
};
const handleCurrentChange = (val) => {
  currentPage.value = val;
};

const filteredDataInfos = computed(() => {
  let result = dataInfos.value;
  if (tags.value.length !== 0) {
    result = {};
    for (const key in dataInfos.value) {
      const item = dataInfos.value[key];
      if (
        item.train_tags &&
        item.train_tags.some((tag) => tags.value.includes(tag))
      ) {
        result[key] = item;
      }
    }
  }
  let fiter = "name";
  if (selectValue.value === "name") {
    fiter = "dataset_name";
  } else if (selectValue.value === "updateTime") {
    fiter = "establish_time";
  } else if (selectValue.value === "views") {
    fiter = "name";
  }
  let re = Object.keys(result)
    .filter((k) => {
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
      return (
        Date.parse(result[a][fiter].replace(" ", "T")) -
        Date.parse(result[b][fiter].replace(" ", "T"))
      );
    })
    .reduce((obj, k) => {
      obj[k] = result[k];
      return obj;
    }, {});
  return re;
});

const curFilteredDataInfos = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  const filteredValue = filteredDataInfos.value;
  return Object.keys(filteredValue)
    .slice(start, end)
    .reduce((obj, k) => {
      obj[k] = filteredValue[k];
      return obj;
    }, {});
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

// watch(
//   () => route.query.type,
//   async (newType) => {
//     if (!newType) {
//       activeTab.value = "openSource";
//       await loadDatasets("1");
//     }
//   }
// );

watch(screeningType, () => {
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

const datasetRegister = () => {
  router.push('/datasets/manage');
};

const toDetail = async (id, item) => { router.push('/datasets/manage'); };

onMounted(async () => {
  tags.value = store.getters.getTags;
  screeningType.value = store.getters.getScreeningType;
  if (route.query.type) {
    activeTab.value = route.query.type as string;
  } else {
    activeTab.value = "openSource";
  }
  setTimeout(() => {
    disableSlide.value = false;
  }, 1);
  await tabChange(activeTab.value);
});

// 监听 localStorage 变化（HG 下载完成后自动刷新）
watch(
  () => {
    const records = localStorage.getItem('hgDownloadRecords:'+localStorage.getItem('ic_user_id'));
    return records;
  },
  async () => {
    if (activeTab.value) {
      await loadDatasets(
        activeTab.value === "openSource" ? "1" : activeTab.value === "domain" ? "2" : "3"
      );
    }
  }
);
</script>

<style scoped>
.editClass {
}
.button-container {
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
  margin-left: 0 !important;
  background-color: #fff;
  border-radius: 5px;
  box-shadow: 0px 0px 8px rgba(158, 158, 158, 0.3);
  margin-bottom: 10px;
}
.screeningButtonGroup {
  height: 40px;
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
.selectOrder,
.inputSearch,
.registerButton,
.cascader-select {
  flex-shrink: 0;
}
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
  transform-origin: top left;
}
.description_data {
  margin-top: 10px;
  font-size: 12px;
  color: rgb(119, 119, 119);
  line-height: 1.4;
  height: calc(12px * 1.4 * 2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
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
.el-tab-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
}
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
  padding: 0 8px;
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
  min-width: 160px;
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
</style>