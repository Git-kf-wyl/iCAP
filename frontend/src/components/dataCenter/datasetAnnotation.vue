<template>
  <div class="container" v-loading="excelLoading" style="height: 100%;">
    <div class="tableBox">
      <div class="buttonRow">
        <input
          ref="folderInput"
          type="file"
          webkitdirectory
          directory
          multiple
          accept="image/*"
          style="display: none"
          @change="handleFolderUpload"
        />
        <input
          ref="excelInput"
          type="file"
          accept=".xlsx, .xls"
          style="display: none"
          @change="handleExcelUpload"
        />

        <el-button
          class="fileUploadBtn"
          @click="triggerFolderInput"
          :icon="Upload"
          :loading="folderUploading"
        >上传图片集</el-button>
        <el-button class="fileUploadBtn" @click="triggerExcelInput" :icon="Document">上传已标注表格</el-button>

        <el-button
          class="fileUploadBtn"
          @click="downLoadAsExcel"
          :icon="Download"
          v-if="excelData.length>0"
        >下载更新后数据</el-button>

        <!-- <el-button
          class="fileUploadBtn"
          @click="downloadExcelWithImg"
          :icon="Download"
          v-if="excelData.length>0"
          v-loading.fullscreen.lock="downloading"
        >下载更新后数据（带图片）</el-button>-->

        <div class="upload-result" v-if="uploadResult">
          <div :class="['result-header', uploadResult.success ? 'success' : 'error']">
            <el-icon :size="20" :color="uploadResult.success ? '#67C23A' : '#F56C6C'">
              <component :is="uploadResult.success ? CircleCheckFilled : CircleCloseFilled" />
            </el-icon>
            <p>{{ uploadResult.message }}</p>
          </div>
          <div v-if="!uploadResult.success" class="error-details">
            <p>失败文件列表：</p>
            <ul>
              <li
                v-for="(file, index) in uploadResult.failedFiles"
                :key="index"
              >{{ file.name }}: {{ file.error }}</li>
            </ul>
          </div>
        </div>

        <div v-if="excelData.length > 0">
          <div class="result-header">
            <el-icon :size="20" color="#67C23A">
              <CircleCheckFilled />
            </el-icon>
            <p>已解析表格数据: {{ excelData.length }}条记录，{{ tableColumns.length }}列</p>
          </div>
        </div>
        <div v-else>请上传数据</div>

        <div v-if="excelData.length > 0||uploadResult">
          <el-tooltip class="box-item" effect="dark" content="清空已有数据，请下载后点击" placement="top">
            <el-button type="danger" :icon="Delete" circle @click="deleteTempFolders" />
          </el-tooltip>
        </div>
      </div>

      <div class="resultArea">
        <div v-if="currentData.length > 0" class="pair-container">
          <div class="single-item">
            <div class="image-area">
              <div v-if="currentData[0].imageLoading" class="image-loading">
                <el-icon class="is-loading">
                  <Loading />
                </el-icon>
                <span>加载中...</span>
              </div>
              <el-image
                v-else-if="currentData[0].imageData"
                :src="currentData[0].imageData"
                class="item-image"
                alt="左图"
                :preview-src-list="[getImageUrl(currentData[0].imageData)]"
                :max-scale="7"
                :min-scale="0.2"
                show-progress
                fit="contain"
              />
              <span v-else class="no-image">无图片</span>
            </div>
            <el-scrollbar class="table-container">
              <el-table
                :data="formatTableData(currentData[0])"
                fit
                show-header
                class="propertyTable"
                :header-cell-style="tableHeaderStyle"
                border
                stripe
                height="820px"
              >
                <el-table-column prop="key" label="属性名" min-width="120" />
                <el-table-column prop="value" label="属性值" min-width="150">
                  <template #default="{ row }">
                    <!-- 保留原有的输入框和下拉框逻辑 -->
                    <template v-if="shouldRenderSelect(row.key)&&!shouldMultiSelect(row.key)">
                      <el-select
                        v-model="row.value"
                        placeholder="请选择"
                        size="small"
                        style="width: 100%"
                        @change="value => handleSelectChange(row.key, value,'left')"
                      >
                        <el-option
                          v-for="item in getOptions(row.key)"
                          :key="item.value"
                          :label="item.label"
                          :value="item.value"
                        />
                      </el-select>
                    </template>

                    <template v-else-if="shouldMultiSelect(row.key)">
                      <el-select
                        v-model="multiSelectValues[row.key]"
                        multiple
                        placeholder="请选择"
                        size="small"
                        style="width: 100%"
                        @change="value => handleMultiSelectChange(row, value)"
                      >
                        <el-option
                          v-for="item in getOptions(row.key)"
                          :key="item.value"
                          :label="item.label"
                          :value="item.value"
                        />
                      </el-select>
                    </template>

                    <template v-else-if="shouldRenderInput(row.key)">
                      <el-input
                        v-model="row.value"
                        size="small"
                        clearable
                        @change="value => handleSelectChange(row.key, value,'left')"
                      />
                    </template>

                    <span v-else>{{ row.value }}</span>
                  </template>
                </el-table-column>
              </el-table>

              <!-- 在表格下方添加按钮区域 -->
              <div class="table-footer" v-if="excelData.length > 0">
                <el-button
                  class="pagination-btn"
                  @click="prevPair"
                  :disabled="currentPairIndex === 0"
                  type="primary"
                >上一张</el-button>
                <el-button
                  class="pagination-btn"
                  @click="nextPair"
                  :disabled="currentPairIndex >= excelData.length - 1"
                  type="primary"
                >下一张</el-button>
                <!-- 显示当前对次信息 -->
                <div class="pair-info" v-if="currentData.length > 0">
                  当前展示:
                  <el-input
                    v-model="displayedIndex"
                    style="width: 50px"
                    :min="1"
                    :max="totalPairs"
                    controls-position="right"
                    @change="indexChange"
                  />
                  / {{ totalPairs }}
                </div>
              </div>
            </el-scrollbar>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
  
  <script lang="ts" setup>
import {
  ref,
  computed,
  onMounted,
  onBeforeMount,
  onBeforeUnmount,
  watch,
  nextTick,
} from "vue";
import * as XLSX from "xlsx";
import {
  Upload,
  Document,
  UploadFilled,
  CircleCheckFilled,
  CircleCloseFilled,
  Loading,
  Download,
  Delete,
} from "@element-plus/icons-vue";

import {
  upload_file,
  delete_folder,
  edit_file,
  retrieve_files,
} from "@/api/dataSetApi.js";
import ExcelJS from "exceljs";

// 获取DOM元素引用
const folderInput = ref<HTMLInputElement | null>(null);
const excelInput = ref<HTMLInputElement | null>(null);

// 存储图片文件
// const imageFiles = ref<File[]>([]);
// 存储Excel解析数据
const excelData = ref<Record<string, any>[]>([]);
// 当前分页
const currentPage = ref(1);

// 动态生成表格列
const tableColumns = computed(() => {
  if (currentData.value.length === 0) return [];

  // 获取所有列名
  const columns = new Set<string>();
  currentData.value.forEach((row) => {
    Object.keys(row).forEach((key) => {
      if (key !== "imageLoading") {
        columns.add(key);
      }
    });
  });

  // 转换为列配置
  return Array.from(columns).map((col) => ({
    prop: col,
    label: col,
  }));
});

// 触发文件夹选择
const triggerFolderInput = () => {
  if (folderInput.value) {
    folderInput.value.value = ""; // 重置以允许重复选择相同文件夹
    folderInput.value.click();
  }
};

// 触发Excel文件选择
const triggerExcelInput = () => {
  if (excelInput.value) {
    excelInput.value.click();
  }
};

// 上传状态
const folderUploading = ref(false);
const uploadResult = ref<{
  success: boolean;
  message: string;
  failedFiles?: Array<{ name: string; error: string }>;
} | null>(null);

const uploadPaths = ref([]);
const imagesFullPath = ref([]);

// 文件夹上传处理
const handleFolderUpload = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (!input.files || input.files.length === 0) return;

  // 过滤图片文件
  const files = Array.from(input.files).filter((file) =>
    file.type.startsWith("image/")
  );

  if (files.length === 0) {
    uploadResult.value = {
      success: false,
      message: "未找到有效的图片文件",
    };
    return;
  }

  folderUploading.value = true;
  uploadResult.value = null;

  try {
    uploadPaths.value = [];
    imagesFullPath.value = [];
    const failedFiles: Array<{ name: string; error: string }> = [];
    let successCount = 0;

    // 逐个上传文件
    for (const file of files) {
      try {
        const formData = new FormData();

        let fileName = file.name;
        if (file.webkitRelativePath) {
          // 分割路径并移除顶层目录
          const pathParts = file.webkitRelativePath.split("/");
          if (pathParts.length > 1) {
            pathParts.shift(); // 移除顶层目录
            fileName = pathParts.join("/"); // 重组路径
          }
        }

        // 使用处理后的文件名
        formData.append("file", file, fileName);

        // 调用上传接口
        const response = await upload_file(formData);
        // console.log(response);

        if (response.status === 200) {
          successCount++;
          uploadPaths.value.push(
            response.data.filename.split("/")[0].split("\\")[0]
          );
          imagesFullPath.value.push(response.data.filename);
        } else {
          failedFiles.push({
            name: file.name,
            error: response.message || "上传失败",
          });
        }
      } catch (error) {
        failedFiles.push({
          name: file.name,
          error: error.message || "请求异常",
        });
      }
    }

    // 处理上传结果
    if (failedFiles.length === 0) {
      uploadResult.value = {
        success: true,
        message: `成功上传 ${successCount} 张图片`,
      };
    } else {
      uploadResult.value = {
        success: false,
        message: `上传完成，成功 ${successCount} 张，失败${failedFiles.length} 张`,
        failedFiles,
      };
    }
  } catch (error) {
    uploadResult.value = {
      success: false,
      message: `上传过程出错: ${error.message}`,
    };
  } finally {
    folderUploading.value = false; // 正确存储数组的方法
    localStorage.setItem(
      "uploadImgPaths",
      JSON.stringify(imagesFullPath.value)
    );

    clearCurrentImages();
    loadImagesForCurrentPair();
  }
};

const excelLoading = ref(false);
const excelTempPath = ref("");

// 处理Excel文件的核心函数（接收Base64编码）
const processExcelFromBase64 = async (base64Data: string) => {
  try {
    // 从Base64读取工作簿（注意type设为'base64'）
    const workbook = XLSX.read(base64Data, { type: "base64" });
    const firstSheetName = workbook.SheetNames[0];
    const worksheet = workbook.Sheets[firstSheetName];

    // 确保工作表有数据范围
    if (!worksheet["!ref"]) throw new Error("工作表无有效数据范围");
    const range = XLSX.utils.decode_range(worksheet["!ref"]);

    // 提取表头（第一行）
    const headers: string[] = [];
    for (let col = range.s.c; col <= range.e.c; col++) {
      const cellAddress = XLSX.utils.encode_cell({ r: range.s.r, c: col });
      const cell = worksheet[cellAddress];
      headers[col] = cell ? cell.v : ""; // 空表头设为空字符串
    }

    // 处理数据行（空值替换为'-'）
    const processedData = [];
    for (let rowIdx = range.s.r + 1; rowIdx <= range.e.r; rowIdx++) {
      const rowData: Record<string, any> = {};
      for (let colIdx = range.s.c; colIdx <= range.e.c; colIdx++) {
        const header = headers[colIdx];
        if (!header) continue; // 跳过无表头列

        const cellAddress = XLSX.utils.encode_cell({ r: rowIdx, c: colIdx });
        const cell = worksheet[cellAddress];
        let value = cell?.v;

        // 空值处理逻辑
        if (value == null || value === "") value = "-";
        rowData[header] = value;
      }
      processedData.push(rowData);
    }
    return processedData;
  } catch (error) {
    console.error("Excel解析失败:", error);
    throw new Error("Excel数据处理异常");
  }
};

// 使用示例（修改后的上传处理函数）
const handleExcelUpload = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (!input.files?.[0]) return;

  excelLoading.value = true;
  const file = input.files[0];

  try {
    const base64String = await readFileAsBase64(file);
    const processedData = await processExcelFromBase64(base64String);

    excelData.value = processedData;
    console.log("处理后的表格数据:", processedData);

    // 后续上传逻辑
    const formData = new FormData();
    formData.append("file", file, file.name);
    const response = await upload_file(formData);

    if (response.status === 200) {
      const [tempPath] = response.data.filename.split(/[\/\\]/);
      excelTempPath.value = tempPath;
      localStorage.setItem("excelTempPath", tempPath);
    }
  } catch (error) {
    console.error("处理失败:", error);
    alert("Excel处理异常");
  } finally {
    excelLoading.value = false;
    clearCurrentImages();
    loadImagesForCurrentPair();
  }
};

// 文件转Base64的辅助函数
const readFileAsBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      // 移除Base64前缀（如"data:application/vnd.ms-excel;base64,"）
      const content = reader.result as string;
      const base64Content = content.split(",")[1] || content;
      resolve(base64Content);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

// 获取图片URL用于预览
const getImageUrl = (base64Data) => {
  if (!base64Data || !base64Data.startsWith("data:image")) return "";

  try {
    // 提取MIME类型和Base64数据
    const parts = base64Data.split(";base64,");
    const mimeType = parts[0].split(":")[1];
    const byteCharacters = atob(parts[1]);

    // 转换为字节数组
    const byteArrays = new Uint8Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteArrays[i] = byteCharacters.charCodeAt(i);
    }

    // 创建Blob并生成URL
    const blob = new Blob([byteArrays], { type: mimeType });
    return URL.createObjectURL(blob);
  } catch (error) {
    console.error("Error creating image URL:", error);
    return "";
  }
};

// 判断列是否为图片列
const isImageColumn = (columnName: string) => {
  return (
    columnName.toLowerCase().includes("image") ||
    columnName.toLowerCase().includes("img") ||
    columnName.toLowerCase().includes("picture")
  );
};

const tableHeaderStyle = {
  backgroundColor: "#f5f6fd",
  color: "#000000",
  fontSize: "14px",
  fontWeight: "bold",
};

const handleBeforeUnload = () => {
  const deletePaths = [...uploadPaths.value, excelTempPath.value];
  deletePaths.forEach((path) => {
    // const url = "http://127.0.0.1:8081/v1/delete/folder";
    const url = "http://7.194.131.207:30101/v1/delete/folder";
    const data = JSON.stringify({ uuid_val: path });

    // 使用 fetch 替代 sendBeacon 确保请求发送
    fetch(url, {
      method: "POST",
      body: data,
      headers: { "Content-Type": "application/json" },
      keepalive: true, // 确保在页面卸载时请求能完成
    }).catch((e) => console.error("删除请求失败:", e));
  });
};

const currentPairIndex = ref(0);

const displayedIndex = computed({
  get: () => currentPairIndex.value + 1,
  set: (newValue) => {
    // 处理非数字输入
    const num = Number(newValue);
    if (isNaN(num)) return;

    // 处理边界值（1~totalPairs）
    const clampedValue = Math.min(Math.max(1, num), totalPairs.value);

    // 转换回实际索引（0~N-1）
    currentPairIndex.value = clampedValue - 1;
  },
});

const indexChange = (val) => {
  nextTick(() => {
    clearCurrentImages();
    loadImagesForCurrentPair();
  });
};

const imageCache = ref<Record<number, string>>({});

// 计算属性
const totalPairs = computed(() => {
  return Math.ceil(excelData.value.length);
});

const isLastPair = computed(() => {
  return currentPairIndex.value >= totalPairs.value - 1;
});

const currentData = computed(() => {
  const startIndex = currentPairIndex.value;
  const pairData = excelData.value.slice(startIndex, startIndex + 1);

  // 添加图片加载状态和图片数据字段
  return pairData.map((row, index) => ({
    ...row,
    imageData: imageCache.value[startIndex + index] || null,
    // imageLoading: false,
  }));
});

// 导航方法
const prevPair = () => {
  if (currentPairIndex.value > 0) {
    clearCurrentImages();
    currentPairIndex.value--;
    loadImagesForCurrentPair();

    saveExcelFile();
  }
};

const nextPair = () => {
  if (currentPairIndex.value < totalPairs.value - 1) {
    clearCurrentImages();
    currentPairIndex.value++;
    loadImagesForCurrentPair();

    saveExcelFile();
  }

  //   console.log("imageCache");
  //   console.log(imageCache.value);
};

const saveExcelFile = async () => {
  try {
    // 创建工作簿和工作表
    const worksheet = XLSX.utils.json_to_sheet(excelData.value);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Sheet1");

    // 生成Excel二进制数据
    const excelBuffer = XLSX.write(workbook, {
      bookType: "xlsx",
      type: "array",
    });

    // 创建Blob对象
    const blob = new Blob([excelBuffer], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    // 创建FormData并添加字段
    const formData = new FormData();
    formData.append("uuid_val", excelTempPath.value);
    formData.append("file", blob, "data.xlsx");

    // 发送请求到后端接口
    const response = await edit_file(formData);

    if (response.status !== 200) {
      throw new Error(`请求失败: ${response.status}`);
    }

    const result = response.data;
    console.log("文件保存成功:", result);
  } catch (error) {
    console.error("保存Excel文件时出错:", error);
  }
};

// 图片加载方法
const loadImagesForCurrentPair = () => {
  //   console.log("loadImagesForCurrentPair");
  const startIndex = currentPairIndex.value;

  // 遍历当前对的两行数据
  //   for (let i = 0; i < 2; i++) {
  const globalIndex = startIndex;
  const row = excelData.value[globalIndex];

  if (!row) return;

  // 标记为加载状态
  row.imageLoading = true;

  // 获取图片路径
  const imagePath = row["图片路径"]; // 根据实际列名调整

  if (imagePath) {
    // 在imagesFullPath中查找匹配路径
    let normalizedPath = imagePath.replace(/\\/g, "/");
    normalizedPath = normalizedPath.split("/").pop();
    // console.log("normalizedPath");
    // console.log(normalizedPath);
    const fullPath = findFullPathForImage(normalizedPath);

    if (fullPath) {
      // 调用API获取图片
      // console.log("fullPath");
      // console.log(fullPath);
      fetchImage(fullPath.split("\\")[0].split("/")[0], globalIndex);
    } else {
      row.imageLoading = false;
    }
  } else {
    row.imageLoading = false;
  }
  //   }
};

const loadAllImages = async () => {
  // 收集所有图片加载的 Promise
  const imagePromises = [];

  excelData.value.forEach((row, index) => {
    const imagePath = row["图片路径"];
    if (!imagePath) return;

    // 处理图片路径
    let normalizedPath = imagePath.replace(/\\/g, "/").split("/").pop();
    const fullPath = findFullPathForImage(normalizedPath);
    if (!fullPath) return;

    // 封装图片加载操作为 Promise
    const promise = (async (idx, path) => {
      await fetchImage(path.split("\\")[0].split("/")[0], idx);
      excelData.value[idx]["图片预览"] = imageCache.value[idx];
    })(index, fullPath); // 立即执行并传入当前值

    imagePromises.push(promise);
  });

  // 等待所有图片加载完成
  await Promise.all(imagePromises);
};

// 辅助方法：根据文件名查找完整路径
const findFullPathForImage = (filename: string) => {
  return imagesFullPath.value.find((path) => {
    // 处理不同操作系统路径分隔符
    const normalizedPath = path.replace(/\\/g, "/");
    // console.log("normalizedPath");
    // console.log(normalizedPath);
    return normalizedPath.endsWith(`/${filename}`);
  });
};

// 获取图片数据
const fetchImage = async (fullPath: string, index: number) => {
  try {
    const response = await retrieve_files({
      uuid_val: fullPath,
    });
    if (response.data && response.data.fileList.length > 0) {
      // 取第一个图片的Base64数据
      //   console.log(response);
      const base64Data = response.data.fileList[0].data;
      // 缓存图片数据
      imageCache.value[index] = `data:image/jpeg;base64,${base64Data}`;
    }
  } catch (error) {
    console.error("图片加载失败:", error);
  } finally {
    // 更新加载状态
    if (excelData.value[index]) {
      excelData.value[index].imageLoading = false;
    }
  }
};

// 清理当前图片数据
const clearCurrentImages = () => {
  imageCache.value = {};
  //   const startIndex = currentPairIndex.value;
  //   // 只删除当前对的图片缓存
  //   //   for (let i = 0; i < 2; i++) {
  //   const index = startIndex;
  //   if (imageCache.value[index]) {
  //     delete imageCache.value[index];
  //   }
  //   }
};

// 在切换数据对时加载图片
watch(currentPairIndex, () => {
  //   loadImagesForCurrentPair();
});

const formatTableData = (item) => {
  return tableColumns.value
    .filter((column) => !notDisplayEnum.includes(column.prop)) // 排除图片列
    .map((column) => ({
      key: column.label,
      value: item[column.prop] || "",
    }));
};

const downLoadAsExcel = () => {
  try {
    // 创建工作簿
    const workBook = XLSX.utils.book_new();

    // 处理数据：移除每个对象的 imageLoading 属性
    const filteredData = excelData.value.map((item) => {
      // 创建新对象，排除 imageLoading 属性
      const { imageLoading, ...rest } = item;
      return rest;
    });

    // 将处理后的JSON数据转换为工作表
    const workSheet = XLSX.utils.json_to_sheet(filteredData);

    // 将工作表添加到工作簿
    XLSX.utils.book_append_sheet(workBook, workSheet, "数据表");

    // 生成文件名（时间戳格式）
    const fileName = `${new Date().getTime()}.xlsx`;

    // 写入文件并下载
    XLSX.writeFile(workBook, fileName);

    console.log("Excel文件下载成功");
  } catch (error) {
    console.error("导出Excel失败:", error);
  }
};

// 图片压缩函数（异步）
const compressImage = (base64, maxWidth = 400) => {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.src = base64;
    img.onload = () => {
      const canvas = document.createElement("canvas");
      const scale = maxWidth / img.width;
      const height = img.height * scale;
      canvas.width = maxWidth;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, maxWidth, height);
      resolve({
        base64: canvas.toDataURL("image/jpeg", 1), // 压缩质量 0.7
        width: maxWidth,
        height: height,
      });
    };
    img.onerror = (e) => reject(e);
  });
};

const downloading = ref(false);

// 修改后的下载函数（异步）
const downloadExcelWithImg = async () => {
  try {
    downloading.value = true;
    await loadAllImages();

    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet("数据表");

    // 获取表头（排除 imageLoading）
    const headers = Object.keys(excelData.value[0]).filter(
      (key) => key !== "imageLoading"
    );
    worksheet.addRow(headers);

    // 获取图片预览列的索引
    const imagePreviewColIndex = headers.indexOf("图片预览");

    // 遍历数据行
    const imageInsertPromises = [];
    excelData.value.forEach((item, rowIndex) => {
      // 添加数据行
      const rowData = headers.map((header) =>
        header === "图片预览" ? null : item[header]
      );
      const currentRow = worksheet.addRow(rowData);
      const currentRowNumber = currentRow.number; // 获取实际行号

      // 处理图片
      if (item["图片预览"] && isValidBase64(item["图片预览"])) {
        const promise = compressImage(item["图片预览"])
          .then((compressed) => {
            if (!compressed || !compressed.base64) {
              console.warn(`图片压缩失败 (行 ${currentRowNumber})`);
              return;
            }

            // 添加图片到工作簿
            const imageId = workbook.addImage({
              base64: compressed.base64,
              extension: "jpeg",
            });

            // 插入图片到单元格
            worksheet.addImage(imageId, {
              tl: { col: imagePreviewColIndex, row: currentRowNumber - 1 },
              br: { col: imagePreviewColIndex + 1, row: currentRowNumber },
            });

            const PIXELS_PER_CHAR = 7; // Excel每字符约7像素
            const POINTS_PER_PIXEL = 0.75; // 1像素≈0.75磅

            // 设置行高（基于压缩后的高度）
            worksheet.getRow(currentRowNumber).height =
              compressed.height * POINTS_PER_PIXEL;

            // 设置列宽（基于压缩后的宽度）
            const colWidth = compressed.width / PIXELS_PER_CHAR;
            worksheet.getColumn(imagePreviewColIndex + 1).width = colWidth;
          })
          .catch((error) => {
            console.error(`图片处理错误 (行 ${currentRowNumber}):`, error);
          });

        imageInsertPromises.push(promise);
      } else {
        console.warn(`缺少图片预览数据 (行 ${currentRowNumber})`);
      }
    });

    // 设置图片列宽
    worksheet.getColumn(imagePreviewColIndex + 1).width = 15;

    // 等待所有图片插入完成（包括失败的情况）
    await Promise.allSettled(imageInsertPromises);

    // 生成并下载文件
    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob([buffer], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${new Date().getTime()}.xlsx`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 100);
  } catch (error) {
    console.error("导出Excel失败:", error);
  } finally {
    excelData.value.forEach((element) => {
      element["图片预览"] = "";
    });
    downloading.value = false;
  }
};

// 辅助函数：验证Base64字符串
const isValidBase64 = (str) => {
  try {
    return (
      /^data:image\/[a-z]+;base64,/.test(str) &&
      atob(str.split(",")[1]) !== null
    );
  } catch (e) {
    return false;
  }
};

const eyesStatusEnum = [
  "眼睛距离书本0-10cm",
  "眼睛距离书本10-25cm",
  "眼睛距离书本25cm以上",
  "视线不在书本上",
  "视线不可见",
  "闭眼",
];
const mouthStatusEnum = ["正常"];
const handsStatusEnum = [
  "正常",
  "手持食物",
  "手持电子设备",
  "手操作摆弄玩具",
  "双手撑脸且手肘撑在桌子上",
  "手部没有拿笔和书",
];
const headStatusEnum = [
  "正常",
  "左转头超过20°",
  "右转头超过20°",
  "低头与躯干夹角超过17°",
  "仰头与躯干夹角超过20°",
  "头部向肩膀倾斜28度以上",
  "头部重心落在桌子上",
  "其他非学习相关头部动作",
];
const shoulderStatusEnum = ["正常", "肩部水平偏角10°以上"];
const bodyStatusEnum = [
  "正常",
  "躯干后仰与水平夹角大于110°",
  "躯干前倾与桌面夹角小于45°",
];
const legsStatusEnum = ["正常", "直立"];
const electricStatusEnum = ["正常", "直立"];
const hasElectricStatusEnum = ["是", "否"];
const eyeTableStatusEnum = ["正常", "头桌距离小于25cm"];
const imgAngleStatusEnum = ["正面", "左侧", "右侧", "远景", "图片里没人"];
const ageTypeEnum = ["小学", "中学", "成人", "图片里没人"];
const humanCntEnum = ["1个人", "2个人", "超过2个人", "图片里没人"];
const sourceEnum = [
  "模型生成",
  "公开评测",
  "网图",
  "手机真实拍摄",
  "算力主机真实拍摄",
  "图片增强-模型生成",
  "图片增强-公开评测集",
  "图片增强-网图",
  "图片增强-手机真实拍摄",
  "图片增强-算力主机真实拍摄",
];
const focusStatusEnum = ["注意力集中", "注意力不集中", "离座", "遮挡"];
const focusSmallEnum = [
  "集中",
  "吃零食",
  "使用电子设备",
  "玩玩具",
  "东张西望",
  "离座",
  "睡觉",
  "其他",
  "遮挡",
];
const eyeToBookEnum = [
  "眼睛距离书本0-10cm",
  "眼睛距离书本10-25cm",
  "眼睛距离书本25cm以上",
  "视线不在书本上",
  "在座但视线不可见",
  "离座",
];
const sitStatusEnum = ["坐姿正常", "坐姿异常", "离座", "遮挡"];
const sitSmallEnum = [
  "正常",
  "斜肩",
  "低头",
  "仰头",
  "歪头",
  "仰躺",
  "托腮",
  "趴桌",
  "离座",
  "其他",
  "遮挡",
];
const sightDistEnum = [
  "视距正常",
  "视距过近",
  "视线不在书本上",
  "视线不可见",
  "离座",
];
const sightDistSmanllEnum = [
  "0-10cm",
  "10-25cm",
  "25cm以上",
  "视线不在书本上",
  "视线不可见",
  "离座",
];
const checkResultEnum = ["已人工审核", "未审核", "存疑"];
const placementPositionEnum = ["正前方", "左侧<60°", "右侧<60°"];
const placementAngleEnum = [
  "人物在图片正中间",
  "人物在图片偏左位置",
  "人物在图片偏右位置",
];
const placementDistanceEnum = ["30-50cm", "50cm之外"];
const genderEnum = ["男", "女"];
const bodySizeEnum = ["消瘦", "匀称", "肥胖"];
const wearingEnum = ["夏装", "春秋装", "冬装"];
const childHeightEnum = [
  "5岁男童105.7-116.9cm",
  "5岁女童104.8-115.6cm",
  "6岁男童111.9-123.5cm",
  "6岁女童110.9-122.3cm",
  "7岁男童117.9-130.1cm",
  "7岁女童116.5-128.5cm",
  "8岁男童123.5-136.3cm",
  "8岁女童122.2-134.8cm",
  "9岁男童128.6-142.2cm",
  "9岁女童127.1-141.1cm",
  "10岁男童133.0-147.4cm",
  "10岁女童132.1-147.1cm",
];
const lightingConditionEnum = ["明亮", "昏暗"];
const backgroundSceneEnum = [
  "专属学习区",
  "客厅休闲区",
  "餐厨功能区",
  "卧室休息区",
  "居家功能角落",
];
const desktopItemsEnum = [
  "学习文具类",
  "课件资料类",
  "护眼工具类",
  "饮水饮食类",
  "桌面收纳类",
  "个人随身类",
  "无桌面元素",
];
const occlusionTypeEnum = [
  "动态遮挡（突发）",
  "桌面物品遮挡",
  "儿童自身遮挡",
  "无遮挡",
];
const peopleCountEnum = ["1人", "超过1人"];
const seatStatusEnum = ["在座状态", "离座状态", "画面遮挡"];

// 属性名与枚举映射
const propertyEnumMap = {
  // 眼部状态: eyesStatusEnum,
  // 嘴部状态: mouthStatusEnum,
  // 手部状态: handsStatusEnum,
  // 头部状态: headStatusEnum,
  // 肩部状态: shoulderStatusEnum,
  // 躯干状态: bodyStatusEnum,
  // 腿部状态: legsStatusEnum,
  // 人物正前方是否存在电子设备: hasElectricStatusEnum,
  // 头桌距离: eyeTableStatusEnum,
  // 图片角度: imgAngleStatusEnum,
  // 人物类别: ageTypeEnum,
  // 镜头近景画面中人数: humanCntEnum,
  图片来源: sourceEnum,
  注意力大类: focusStatusEnum,
  注意力小类: focusSmallEnum,
  眼书距离: eyeToBookEnum,
  坐姿大类: sitStatusEnum,
  坐姿小类: sitSmallEnum,
  视距大类: sightDistEnum,
  视距小类: sightDistSmanllEnum,
  check结果: checkResultEnum,
  设备摆放位置: placementPositionEnum,
  设备摆放角度: placementAngleEnum,
  设备摆放距离: placementDistanceEnum,
  检测对象性别: genderEnum,
  检测对象体型: bodySizeEnum,
  检测对象穿着: wearingEnum,
  检测对象身高: childHeightEnum,
  光照: lightingConditionEnum,
  图片背景: backgroundSceneEnum,
  桌面元素: desktopItemsEnum,
  遮挡: occlusionTypeEnum,
  镜头中人数: peopleCountEnum,
  离座检测: seatStatusEnum,
};

const notDisplayEnum = [
  "眼部状态",
  "嘴部状态",
  "手部状态",
  "头部状态",
  "肩部状态",
  "躯干状态",
  "腿部状态",
  "人物正前方是否存在电子设备",
  "头桌距离",
  "图片角度",
  "人物类别",
  "镜头近景画面中人数",
  "imageData",
  "达成一致的项",
  "已知儿童年龄",
  "性别",
];

const propertyInput = ["分辨率", "图片路径"];

const multiSelect = [
  // "嘴部状态",
  // "手部状态",
  // "头部状态",
  // "肩部状态",
  // "躯干状态",
  // "腿部状态",
  // "头桌距离",
  "注意力大类",
  "注意力小类",
  "坐姿大类",
  "坐姿小类",
  "视距大类",
  "视距小类",
  // "眼部状态",
  "图片背景",
  "桌面元素",
  "离座检测",
];

// 枚举转换函数
const enumToOptions = (enumData) => {
  return enumData.map((item) => ({ label: item, value: item }));
};

// 判断是否需要渲染下拉框
const shouldRenderSelect = (key) => {
  return Object.keys(propertyEnumMap).includes(key);
};

const shouldRenderInput = (key) => {
  //   return propertyInput.includes(key);
  return !shouldRenderSelect(key) && !shouldMultiSelect(key);
};

const shouldMultiSelect = (key) => {
  return multiSelect.includes(key);
};

const multiSelectValues = ref({});

// 初始化多选框值（从字符串转为数组）
const initMultiSelectValues = (tableData) => {
  tableData.forEach((row) => {
    if (shouldMultiSelect(row.key)) {
      multiSelectValues.value[row.key] = row.value
        ? row.value.split(",").filter((item) => item.trim() !== "")
        : [];
    }
  });
};

watch(
  () => currentData.value[0],
  (newData) => {
    initMultiSelectValues(formatTableData(newData));
  },
  { deep: true, immediate: true }
);

// 获取对应属性的选项
const getOptions = (key) => {
  const enumData = propertyEnumMap[key];
  return enumData ? enumToOptions(enumData) : [];
};

const handleSelectChange = (key, value, type) => {
  // console.log("currentPairIndex");
  //   const index = type === "left" ? 0 : 1;
  //   console.log(currentPairIndex.value * 2 + index);
  //   const realIndex = currentPairIndex.value * 2 + index;
  const realIndex = currentPairIndex.value;
  //   console.log(value);

  excelData.value[realIndex][key] = value;
};

const handleMultiSelectChange = (row, selectedArray) => {
  console.log("handleMultiSelectChange");
  // 将数组转为逗号分隔字符串
  const newValue = selectedArray.join(",");
  // 更新行数据
  row.value = newValue;
  // 调用原始变更处理（保持原有逻辑）
  handleSelectChange(row.key, newValue, "left");
};

const loadImgData = () => {
  console.log("imagesFullPath");
  console.log(imagesFullPath.value);

  imagesFullPath.value.forEach((path) => {
    uploadPaths.value.push(path.split("/")[0].split("\\")[0]);
  });
  //   console.log("uploadPaths");
  //   console.log(uploadPaths.value);
  loadImagesForCurrentPair();
};

const loadExcelData = async () => {
  console.log("excelTempPath");
  console.log(excelTempPath.value);
  const response = await retrieve_files({ uuid_val: excelTempPath.value });
  //   console.log("response");
  //   console.log(response);

  const processedData = await processExcelFromBase64(
    response.data.fileList[0]?.data
  );

  excelData.value = processedData;
  console.log("处理后的表格数据:", processedData);
};

const deleteTempFolders = () => {
  const deletePaths = [...uploadPaths.value, excelTempPath.value];
  deletePaths.forEach((path) => {
    delete_folder({ uuid_val: path });
  });
  uploadPaths.value = []; // 清空路径数组
  imagesFullPath.value = []; // 清空路径数组
  excelTempPath.value = "";
  localStorage.setItem("excelTempPath", `${excelTempPath.value}`);
  localStorage.setItem("uploadImgPaths", `${imagesFullPath.value}`);

  location.reload(true);
};

onMounted(async () => {
  // 添加页面刷新/关闭事件监听
  //   window.addEventListener("beforeunload", handleBeforeUnload);

  excelTempPath.value = localStorage.getItem("excelTempPath");
  // 从 localStorage 获取字符串
  const pathsString = localStorage.getItem("uploadImgPaths");

  // 安全解析：处理 null 或无效 JSON 的情况
  if (pathsString) {
    try {
      imagesFullPath.value = JSON.parse(pathsString); // 解析为数组
    } catch (error) {
      console.error("解析失败，使用空数组", error);
      imagesFullPath.value = []; // 解析失败时赋空数组
    }
  } else {
    imagesFullPath.value = []; // 无数据时赋空数组
  }

  await loadExcelData();
  loadImgData();
});

onBeforeUnmount(() => {
  // 移除事件监听
  //   window.removeEventListener("beforeunload", handleBeforeUnload);
  //   deleteTempFolders();
});
</script>
  
  <style scoped>
.tableBox {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  padding: 20px 20px 0px 20px;
  margin-top: 20px;
  height: 95%;
}

.buttonRow {
  height: 40px;
  display: flex;
  align-items: center;
  margin-bottom: 25px;
  gap: 15px;
}

.fileUploadBtn {
  background-color: #409eff;
  color: white;
  border: none;
  box-shadow: none;
  height: 100%;
  padding: 0 20px;
  font-size: 15px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.3s;
}

.fileUploadBtn:hover {
  background-color: #0056b3;
  /* transform: translateY(-1px); */
  box-shadow: 0 4px 8px rgba(0, 103, 209, 0.2);
}

.resultArea {
  margin-top: 20px;
  height: 90%;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  /* margin-bottom: 15px; */
}

.result-header h3 {
  margin: 0;
  color: #1f2d3d;
  font-size: 18px;
}

.image-upload-result,
.excel-upload-result {
  /* background: white; */
  border-radius: 8px;
  /* padding: 20px; */
  /* margin-bottom: 25px; */
  /* box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05); */
  /* border: 1px solid #ebeef5; */
}

.image-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 15px;
  margin-top: 15px;
}

.preview-item {
  width: 120px;
  text-align: center;
}

.preview-item img {
  width: 100%;
  height: 90px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #eee;
}

.image-name {
  display: block;
  font-size: 12px;
  color: #666;
  margin-top: 5px;
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
}

.more-images {
  width: 120px;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  border: 1px dashed #dcdfe6;
  border-radius: 4px;
  color: #909399;
  font-size: 14px;
}

.table-container {
  /* margin-top: 20px; */
  border: 1px solid #ebeef5;
  border-radius: 4px;
  overflow: hidden;
  width: 60%;
  max-height: 100%;
}

.excelDataTable {
  width: 100%;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.empty-state {
  text-align: center;
  padding: 50px 20px;
  color: #909399;
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  background-color: #fafafa;
}

.empty-state p {
  margin-top: 15px;
  font-size: 16px;
}

.cell-image {
  max-width: 80px;
  max-height: 60px;
  border-radius: 4px;
}

.no-image {
  color: #909399;
  font-size: 13px;
}

.upload-result {
  margin-left: 20px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 4px;
}

.success {
  /* background-color: #f0f9eb; */
  color: #67c23a;
}

.error {
  /* background-color: #fef0f0; */
  color: #f56c6c;
}

.error-details {
  margin-top: 10px;
  padding: 10px;
  background: #fef0f0;
  border-radius: 4px;
  max-height: 50px;
  overflow-y: auto;
}

.error-details ul {
  padding-left: 20px;
  margin: 5px 0;
}

.pair-info {
  margin-left: 15px;
  font-size: 14px;
  color: #606266;
}

.image-loading {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #909399;
  font-size: 12px;
}

.pair-container {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  height: 100%;
}

.single-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: row;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  overflow: hidden;
}

.image-area {
  /* height: 300px; */
  width: 40%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  padding: 10px;
}

.item-image {
  display: block;
  max-width: 100%; /* 限制最大宽度 */
  max-height: 100%; /* 限制最大高度 */
  margin: 0 auto; /* 水平居中 */
  object-fit: contain; /* 确保图片比例不变 */
}

.item-image :deep(.el-image__inner) {
  max-height: 300px;
}

.image-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #999;
}

.no-image {
  color: #ccc;
  font-style: italic;
}

:deep(.el-table__cell) {
  padding: 5px;
}

.table-container :deep(.el-table) {
  height: 100% !important;
}

.table-footer {
  display: flex;
  margin-top: 15px;
  text-align: center;
  align-items: center;
  justify-content: center;
}

.pagination-btn {
  width: 100px;
  margin: 0 10px;
}

/* 属性值列单元格 */
.propertyTable :deep(.el-table__body td.el-table__cell:last-child) {
  padding: 0 5px 0 0 !important;
}

.propertyTable :deep(.el-table__body td.el-table__cell:last-child .cell) {
  padding: 0 !important;
}

/* 输入框 */
.propertyTable
  :deep(.el-table__body td.el-table__cell:last-child .el-input__inner) {
  padding: 0 !important;
  height: 28px;
  border: none;
  border-radius: 0;
}

/* 多选框标签 */
.propertyTable :deep(.el-table__body td.el-table__cell:last-child .el-tag) {
  height: 24px;
}

/* 下拉框 */
.propertyTable :deep(.el-table__body td.el-table__cell:last-child .el-select) {
  /* line-height: 28px; */
}

/* 下拉框输入区域 */
.propertyTable
  :deep(
    .el-table__body td.el-table__cell:last-child .el-select .el-select__wrapper
  ) {
  height: 28px;
}
</style>