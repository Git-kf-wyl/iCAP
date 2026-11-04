import { ref, watch, computed } from "vue";
import { ElMessage, ElLoading } from "element-plus";
import { getResult, getList } from "@/api/runService.js";
import { useTaskStore } from "@/stores/taskStore";
import { useRoute } from "vue-router";

export function useTaskSelection(props, emit, options = {}) {
  const { onDataReady } = options;
  const taskStore = useTaskStore();
  const route = useRoute();

  const tasks = ref([]);
  const filteredTasks = ref([]);
  const selectedTaskIds = ref<string[]>([]);
  const selectedTasks = ref<any[]>([]);
  const preSelectedTasks = ref<any[]>([]);

  const taskSubSet = ref("准确率");
  const sheet_scene = ref("normal");
  const Result = ref<any[]>([]);
  const resultCache = ref<Record<string, any>>({});

  const taskSelectRef = ref(null);
  const dropdownVisible = ref(false);
  const isConfirmAction = ref(false);

  const canCompare = ref(true)

  const isSelected = (taskId: string) => {
    return selectedTaskIds.value.includes(taskId);
  };

  /** Extract the special subset type from a task, or null if normal */
  const getTaskSubsetType = (task) => {
    const list = task?.taskConfig?.dataset_args?.[0]?.subset_list;
    if (!list) return null;
    if (list.includes("稳定性")) return "稳定性";
    if (list.includes("时延分布")) return "时延分布";
    return null;
  };

  const toggleTask = (task) => {
    const taskIndex = selectedTasks.value.findIndex((t) => t.ID === task.ID);

    if (taskIndex > -1) {
      selectedTasks.value.splice(taskIndex, 1);
    } else {
      // Check subset type compatibility
      const currentType = getTaskSubsetType(task);
      // Find any already-selected tasks with a special subset type
      const existingType = selectedTasks.value.reduce((type, t) => {
        const tType = getTaskSubsetType(t);
        return tType ? tType : type;
      }, null);
      if (currentType && existingType && currentType !== existingType) {
        ElMessage.warning(`已选任务为"${existingType}"类型，不能混选"${currentType}"类型的任务`);
        return;
      }
      if (existingType && !currentType) {
        ElMessage.warning(`已选任务为"${existingType}"类型，不能混选普通任务`);
        return;
      }
      if (currentType && !existingType && selectedTasks.value.length > 0) {
        ElMessage.warning(`已选任务包含普通任务，不能混选"${currentType}"类型任务`);
        return;
      }
      selectedTasks.value.push(task);
    }

    selectedTasks.value.sort((a, b) => {
      return new Date(a.createTime) - new Date(b.createTime);
    });

    selectedTaskIds.value = selectedTasks.value.map((task) => task.ID);
    console.log('selectedTaskIds')
    console.log(selectedTaskIds.value)
  };

  const toggleSelection = (row) => {
    if (props.task_id !== row.ID) {
      toggleTask(row);
    }
  };

  const handleConfirm = (customCallback) => {
    console.log('handleConfirm!')
    isConfirmAction.value = true;
    preSelectedTasks.value = [...selectedTasks.value];
    if (taskSelectRef.value) {
      taskSelectRef.value.blur();
    }

    const loading = ElLoading.service({
      lock: true,
      text: "统计中...",
    });

    if (props.task_id && props.result) {
      resultCache.value[props.task_id] = props.result;
    }

    if (selectedTaskIds.value.length === 0) {
      loading.close();
      return Promise.resolve([]);
    }

    if (selectedTasks.value[0]) {
      const promises = selectedTasks.value.map((task) => {
        if (task.taskConfig.dataset_args[0].subset_list.includes("时延分布")) {
          taskSubSet.value = "时延分布";
          sheet_scene.value = "timeDelay";
        } else if (
          task.taskConfig.dataset_args[0].subset_list.includes("稳定性")
        ) {
          taskSubSet.value = "稳定性";
          sheet_scene.value = "stability";
        }
        const taskId = task.ID;

        if (resultCache.value[taskId]) {
          return Promise.resolve(resultCache.value[taskId]);
        }

        return getResult({
          task_id: taskId,
          model_id: task.model_id,
          page: `${1},${50}`,
          dataset: task.datasets[0],
          assessmentType: task.assessmentType,
        })
          .then((res) => {
            if (res.data.result.length < 1) {
              ElMessage({ type: "error", message: "暂无数据" });
              resultCache.value[taskId] = null;
              return null;
            }
            resultCache.value[taskId] = res.data.result;
            return res.data.result;
          })
          .catch((error) => {
            console.error("获取任务列表失败:", error);
            resultCache.value[taskId] = null;
            return null;
          });
      });

      return Promise.allSettled(promises).then((results) => {
        const validResults = results
          .filter(
            (result) => result.status === "fulfilled" && result.value !== null
          )
          .map((result) => result.value);
        Result.value = validResults;
        if (typeof customCallback === "function") {
          customCallback(validResults);
        }
        loading.close();
        return validResults;
      });
    } else {
      return []
    }
  };

  const handelCancel = () => {
    selectedTasks.value = [...preSelectedTasks.value];
    selectedTaskIds.value = selectedTasks.value.map((task) => task.ID);
    taskSelectRef.value.blur();
  };

  watch(dropdownVisible, (newVal) => {
    if (!newVal) {
      if (!isConfirmAction.value) {
        selectedTasks.value = [...preSelectedTasks.value];
        selectedTaskIds.value = selectedTasks.value.map((task) => task.ID);
      }
      isConfirmAction.value = false;
    }
  });

  const fetchTasks = async () => {
    const loading = ElLoading.service({
      lock: true,
      text: "加载任务信息...",
    });

    if (taskStore.getTasks.length > 0) {
      tasks.value = taskStore.getTasks;
      loading.close();
    } else {
      try {
        const res = await getList();
        tasks.value = res.data;
        taskStore.setTasks(res.data);
        loading.close();
      } catch (error) {
        loading.close();
        console.error("获取任务列表失败:", error);
      }
    }

    filteredTasks.value = tasks.value.filter((task) => {
      return (
        task.datasets.length === 1 &&
        task.status === "completed" &&
        (task.taskConfig?.dataset_args?.[0]?.testcase_tags || []).some(
          (arg) => arg === "儿童伴读"
        )
      );
    });

    loading.close();

    if (props.task_id) {
      selectedTaskIds.value.push(props.task_id);
      selectedTasks.value.push(
        tasks.value.filter((task) => {
          return task.ID === props.task_id;
        })[0]
      );
      if (!selectedTasks.value[0]) {
        canCompare.value = false
      }
    }
  };

  /** Check if a row should be disabled based on subset type conflict with current selection */
  const isRowDisabled = (row) => {
    if (row.ID === props.task_id) return true;
    const rowType = getTaskSubsetType(row);
    // Find the subset type among already selected tasks
    const selectedType = selectedTasks.value.reduce((type, t) => {
      const tType = getTaskSubsetType(t);
      return tType ? tType : type;
    }, null);
    if (!selectedType) return false; // no existing constraint
    return rowType !== selectedType;
  };

  return {
    tasks,
    filteredTasks,
    selectedTaskIds,
    selectedTasks,
    preSelectedTasks,
    taskSubSet,
    sheet_scene,
    Result,
    resultCache,
    taskSelectRef,
    dropdownVisible,
    isConfirmAction,
    isSelected,
    toggleTask,
    toggleSelection,
    handleConfirm,
    handelCancel,
    fetchTasks,
    isRowDisabled,
    canCompare
  };
}