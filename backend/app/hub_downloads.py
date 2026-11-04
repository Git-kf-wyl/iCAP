"""Public model/dataset downloads in each iCAP account's private resource library."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import threading
import uuid
from datetime import datetime,timezone
from urllib.parse import urlsplit
from fastapi import HTTPException
from .yellow_runtime import write_json

class HubDownloads:
    def __init__(self,runtime,store):
        self.runtime=runtime;self.store=store;self.lock=threading.RLock()
        for path in (runtime.base/'users').glob('*/downloads/tasks.json'):
            tasks=json.loads(path.read_text('utf-8'))
            for row in tasks.values():
                if row.get('task_status')=='running':row.update(task_status='failed',error='服务重启中断了下载，请重新提交')
            write_json(path,tasks)

    @staticmethod
    def parse(url,provider):
        parsed=urlsplit(url)
        hosts={'hg':'huggingface.co','ms':'modelscope.cn'}
        if parsed.scheme!='https' or parsed.hostname!=hosts[provider] or parsed.username or parsed.password:
            raise HTTPException(422,'请输入所选站点的 HTTPS 仓库链接')
        parts=[v for v in parsed.path.split('/') if v]
        repo_type='model'
        if parts and parts[0] in ('models','datasets'):
            repo_type='dataset' if parts.pop(0)=='datasets' else 'model'
        if len(parts)<2 or any(v in ('.','..') for v in parts[:2]):raise HTTPException(422,'仓库链接应包含组织和仓库名称')
        return '/'.join(parts[:2]),repo_type

    def info(self,url,provider):
        repo,kind=self.parse(url,provider)
        try:
            if provider=='hg':
                from huggingface_hub import HfApi
                rows=HfApi(token=False).list_repo_tree(repo,repo_type=kind,recursive=True)
            else:
                from modelscope_hub.api import HubApi
                rows=HubApi().list_repo_files(repo,repo_type=kind,recursive=True)
            files=[];sizes=[];truncated=False
            for row in rows:
                name=getattr(row,'path',None) or getattr(row,'file_path',None)
                size=getattr(row,'size',None)
                if not name or size is None:continue
                if '..' in PurePosixPath(name).parts or name.startswith('/'):continue
                files.append(name);sizes.append(int(size))
                if len(files)>=5000:truncated=True;break
            return {'status':'success','repo_name':repo,'repo_type':kind,'files_list':files,'files_len_list':sizes,
                    'total_count':len(files),'truncated':truncated}
        except HTTPException:raise
        except Exception:raise HTTPException(502,'无法获取公开仓库文件，请检查仓库地址、访问权限或网络')

    def paths(self,actor):
        root=self.runtime.initialize(actor)/'downloads';root.mkdir(exist_ok=True)
        path=root/'tasks.json'
        if not path.exists():write_json(path,{})
        return root,path

    def start(self,actor,provider,body):
        info=self.info(body.get('url',''),provider)
        files=body.get('files_list') or []
        known=dict(zip(info['files_list'],info['files_len_list']))
        if not files or len(files)>1000 or len(set(files))!=len(files) or any(name not in known for name in files):raise HTTPException(422,'请选择仓库列表中的 1 至 1000 个文件')
        total=sum(known[name] for name in files)
        if total>int(os.getenv('YELLOW_DOWNLOAD_MAX_BYTES',str(2*1024**3))):raise HTTPException(422,'单次下载超过 2 GiB，请缩小文件范围')
        root,path=self.paths(actor)
        with self.lock:
            tasks=json.loads(path.read_text('utf-8'))
            if sum(row.get('task_status')=='running' for row in tasks.values())>=2:raise HTTPException(429,'当前账号已有两个下载任务正在运行')
            if shutil.disk_usage(root).free<total+5*1024**3:raise HTTPException(503,'资源库可用空间不足')
            task_id=uuid.uuid4().hex
            row={'status':'success','task_id':task_id,'task_status':'running','repo_name':info['repo_name'],'repo_type':info['repo_type'],
                 'provider':provider,'total':len(files),'downloaded_files':[],'failed_files':[],
                 'download_path':'downloads/'+task_id,'backup_folder_path':'downloads/'+task_id,'bytes':total}
            tasks[task_id]=row;write_json(path,tasks)
        def download():
            folder=root/task_id;folder.mkdir()
            try:
                for name in files:
                    try:
                        if provider=='hg':
                            from huggingface_hub import hf_hub_download
                            hf_hub_download(info['repo_name'],name,repo_type=info['repo_type'],local_dir=folder,token=False)
                        else:
                            from modelscope.hub.file_download import model_file_download,dataset_file_download
                            function=dataset_file_download if info['repo_type']=='dataset' else model_file_download
                            function(info['repo_name'],name,local_dir=str(folder),token='')
                        row['downloaded_files'].append(name)
                    except Exception:row['failed_files'].append(name)
                    with self.lock:
                        tasks=json.loads(path.read_text('utf-8'));tasks[task_id]=row;write_json(path,tasks)
                row['task_status']='completed' if row['downloaded_files'] else 'failed'
                if row['task_status']=='failed':row['error']='文件下载失败，请检查仓库权限或网络'
            except Exception:row.update(task_status='failed',error='下载任务执行失败')
            finally:
                with self.lock:
                    tasks=json.loads(path.read_text('utf-8'));tasks[task_id]=row;write_json(path,tasks)
        threading.Thread(target=download,daemon=True,name='hub-'+task_id).start()
        return row

    def status(self,actor,identifier):
        root,path=self.paths(actor);row=json.loads(path.read_text('utf-8')).get(identifier)
        if not row:raise HTTPException(404,'下载任务不存在')
        return row

    def register(self,actor,body):
        relative=body.get('backup_folder_path','')
        parts=PurePosixPath(relative).parts
        if len(parts)!=2 or parts[0]!='downloads':raise HTTPException(422,'无效的下载记录')
        row=self.status(actor,parts[1])
        if row['task_status']!='completed':raise HTTPException(409,'下载尚未完成')
        if row.get('dataset_id'):return {'status':'success','success_count':len(row['downloaded_files']),'fail_count':len(row['failed_files']),'dataset_id':row['dataset_id']}
        root,path=self.paths(actor);entries=[]
        for name in row['downloaded_files']:
            source=(root/parts[1]/name).resolve()
            if not source.is_relative_to(root.resolve()) or not source.is_file():continue
            file_id='file-'+uuid.uuid4().hex[:12];storage=file_id+source.suffix[:12];target=self.store.uploads/storage
            try:os.link(source,target)
            except OSError:shutil.copy2(source,target)
            entries.append({'id':file_id,'name':name,'storage_name':storage,'bytes':source.stat().st_size})
        identifier='ds-'+uuid.uuid4().hex[:12]
        record={'id':identifier,'name':row['repo_name'],'category':'训练集','version':'main','description':'从公开仓库下载的资源',
                'owner_user_id':actor['id'],'owner_name':actor['username'],'created_at':datetime.now(timezone.utc).isoformat(),
                'visibility':'public' if body.get('visibility')=='public' else 'private','files':entries,'size':len(entries)}
        self.store.update(lambda data:data['datasets'].append(record))
        row['dataset_id']=identifier
        with self.lock:
            tasks=json.loads(path.read_text('utf-8'));tasks[parts[1]]=row;write_json(path,tasks)
        return {'status':'success','success_count':len(entries),'fail_count':len(row['failed_files']),'dataset_id':identifier,'bucket_path':identifier}
