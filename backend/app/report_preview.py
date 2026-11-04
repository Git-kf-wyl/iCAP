"""Free, local PDF conversion for authenticated report previews."""
import asyncio
import shutil
import tempfile
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse

_slots=asyncio.Semaphore(2)

async def preview_pdf(root:Path,relative:str):
    source=(root/relative).resolve()
    if not source.is_relative_to(root.resolve()) or not source.is_file():raise HTTPException(404,'报告文件不存在')
    if source.suffix.lower()=='.pdf':return FileResponse(source,media_type='application/pdf')
    if source.suffix.lower() not in ('.ppt','.pptx'):raise HTTPException(422,'仅支持 PPT、PPTX 或 PDF 报告')
    target=source.with_suffix('.pdf')
    if not target.exists() or target.stat().st_mtime<source.stat().st_mtime:
        executable=shutil.which('libreoffice') or shutil.which('soffice')
        if not executable:raise HTTPException(503,'报告预览转换器尚未安装，仍可下载原始报告')
        async with _slots:
            with tempfile.TemporaryDirectory(prefix='preview-',dir=root) as folder:
                temp=Path(folder)
                # A separate clean profile disables shared GUI state and document macros.
                process=await asyncio.create_subprocess_exec(executable,'--headless','--nologo','--nodefault','--nofirststartwizard',
                    '-env:UserInstallation='+(temp/'profile').as_uri(),'--convert-to','pdf','--outdir',str(temp),str(source),
                    stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
                try:await asyncio.wait_for(process.wait(),90)
                except asyncio.TimeoutError:
                    process.kill();await process.wait();raise HTTPException(504,'报告转换超时，请下载原文件查看')
                result=temp/(source.stem+'.pdf')
                if process.returncode or not result.is_file():raise HTTPException(422,'报告转换失败，请检查文件格式')
                await asyncio.to_thread(shutil.copy2,result,target)
    return FileResponse(target,media_type='application/pdf',headers={'Cache-Control':'private, no-store'})
