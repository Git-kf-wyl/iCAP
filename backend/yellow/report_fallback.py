"""Generate a real evaluation deck when upstream's PPT templates are absent."""
from datetime import datetime
import json
from pathlib import Path

def generate(module,task_id,model_names,model_ids,compare_models,parsed_types,all_types,report_name):
    from pptx import Presentation
    from pptx.util import Inches,Pt
    from pptx.dml.color import RGBColor
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    tasks=module.get_report_tasks()
    try:
        prs=Presentation();prs.slide_width=Inches(13.33);prs.slide_height=Inches(7.5)
        slide=prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text=report_name or '模型评估报告'
        slide.placeholders[1].text='InnovationCore AI Platform\n'+datetime.now().strftime('%Y-%m-%d')
        count=0
        for filename,label in [('ruler1_cheat.json','通用能力'),('ruler2_cheat.json','领域能力'),('ruler1_cheat_multi.json','多模态通用'),('ruler2_cheat_multi.json','多模态领域')]:
            source=Path('backend/config')/filename
            rows=json.loads(source.read_text('utf-8')) if source.exists() else {}
            for model in model_names:
                records=rows.get(model,[])
                if isinstance(records,dict):records=records.get('result',[])
                records=[row for row in records if isinstance(row,dict) and isinstance(row.get('score'),(float,int))]
                if not records:continue
                count+=1
                slide=prs.slides.add_slide(prs.slide_layouts[5]);slide.shapes.title.text=f'{model} · {label}'
                chart=CategoryChartData();chart.categories=[r.get('dataset_name','') for r in records]
                chart.add_series('实际评测得分',[r['score'] for r in records])
                slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,Inches(.7),Inches(1.6),Inches(7.8),Inches(4.8),chart)
                table=slide.shapes.add_table(len(records)+1,2,Inches(8.7),Inches(1.6),Inches(4),Inches(min(4.8,.4*(len(records)+1)))).table
                table.cell(0,0).text='评测集';table.cell(0,1).text='得分'
                for i,row in enumerate(records,1):
                    table.cell(i,0).text=row.get('dataset_name','')
                    table.cell(i,1).text=f"{row['score']:.4f}"
        if not count:raise ValueError('所选模型尚无已完成的真实评测结果')
        for slide in prs.slides:
            for shape in slide.shapes:
                if not shape.has_text_frame:continue
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:run.font.name='Microsoft YaHei';run.font.color.rgb=RGBColor.from_string('243B53')
        output=Path('backend/report/output')/(task_id+'.pptx');output.parent.mkdir(parents=True,exist_ok=True);prs.save(output)
        tasks=module.get_report_tasks()
        tasks[task_id].update(status='completed',filepath=str(output).replace('\\','/'),complete_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    except Exception as exc:
        tasks=module.get_report_tasks()
        tasks[task_id].update(status='failed',error=str(exc),complete_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    module.set_report_tasks(tasks)
