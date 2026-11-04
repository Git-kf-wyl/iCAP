export function pageSizeForDataset(ds: string): number {
  return ds === "live_code_bench" ? 10 : 52;
}

export function checkAllDatasetsTag(
  task: any,
  datasets: any,
  tag: string
): boolean {
  if (!task || !task.datasets || task.datasets.length === 0) {
    return false;
  }
  for (const datasetId of task.datasets) {
    const dataset = datasets?.[datasetId];
    if (
      !dataset ||
      !Array.isArray(dataset.testcase_tags) ||
      !dataset.testcase_tags.includes(tag)
    ) {
      return false;
    }
  }
  return true;
}

export function computeIsChildStudy(task: any, datasets: any): boolean {
  return checkAllDatasetsTag(task, datasets, "儿童伴读");
}

export function computeIsRuler2(task: any, datasets: any): boolean {
  return [
    "意图",
    "记忆",
    "改写",
    "skill提参",
    "GUI提参",
    "伴学提参",
    "Coordinator",
  ].some((tag) => checkAllDatasetsTag(task, datasets, tag));
}

export function computeIsInterpretation(assessmentType: string): boolean {
  return (
    assessmentType === "ASR" ||
    assessmentType === "MT" ||
    assessmentType === "TTS" ||
    assessmentType === "ASR+MT" ||
    assessmentType === "ASR+MT+TTS"
  );
}
