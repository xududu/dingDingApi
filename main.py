from fastapi import FastAPI, Form, Path
import json
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import multiprocessing
from starlette.templating import Jinja2Templates
from starlette.requests import Request
import time

from service import api

rancher_api = api.Api(rancher_ip='192.168.0.100',
                      rancher_token='token-d4vbt:84qzrlrctrmxscwg4g2h996hzkxb25xzlwpvwkbk477897qm8pl4ls')
ding_ding_api = api.dingding_api(webhook='https://oapi.dingtalk.com/robot/send?access_token'
                                         '=8b52730c7c397e7dd424874564ae35fbdd58ffcd27b4d4064e1da5e3a6bb6504')
app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:8080",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# post format
class PublishConfirmParameter(BaseModel):
    project_id: str
    namespace: str
    servername: str
    publish_image_version: str


class ConsoleLogParameter(BaseModel):
    group_name: str
    namespace: str
    servername: str
    line: Optional[str] = '100'


# 发布验证接口
@app.post('/confirm')
async def publish_confirm(confirm_parameter: PublishConfirmParameter):
    confirm_parameter_dict = confirm_parameter.dict()
    project_id = confirm_parameter_dict['project_id']
    namespace = confirm_parameter_dict['namespace']
    servername = confirm_parameter_dict['servername']
    publish_image_version = confirm_parameter_dict['publish_image_version']
    cluster_name = ''

    # 提取组名
    cluster_list = rancher_api.cluster_info()
    for cluster_dict in cluster_list:
        try:
            cluster_name = cluster_dict[project_id]
        except KeyError:
            pass
    # 多进程调用
    semaphore_obj = multiprocessing.Semaphore(10)
    process = multiprocessing.Process(target=rancher_api.get_server_state,
                                      args=(semaphore_obj, project_id, namespace, servername,
                                            publish_image_version, ding_ding_api,
                                            cluster_name))
    process.start()
    # state_res = rancher_api.get_server_state(project_id=project_id, namespace=namespace,
    #                                          servername=servername, publish_image_version=publish_image_version,
    #                                          dingding_obj=ding_ding_api, cluster_name=cluster_name)


@app.post('/consolelog')
async def console_log(log_parameter: ConsoleLogParameter):
    log_parameter_dict = log_parameter.dict()
    group_name = log_parameter_dict['group_name']
    namespace = log_parameter_dict['namespace']
    servername = log_parameter_dict['servername']
    line = log_parameter_dict['line']
    project_id = ''
    # 提取项目id
    cluster_list = rancher_api.cluster_info(optional_key='cluster_name')
    for cluster_dict in cluster_list:
        try:
            project_id = cluster_dict[group_name]
        except KeyError:
            pass
    # 集群id
    cluster_id = project_id.split(':')[0]
    # 获取pod名
    pod_name_list = rancher_api.get_pod_name(project_id=project_id, namespace=namespace, servername=servername)
    # 如果有这个pod
    if pod_name_list:
        for pod_name in pod_name_list:
            # 获取log
            container_log = rancher_api.get_container_log(cluster_id=cluster_id, namespace=namespace,
                                                          pod_name=pod_name, servername=servername, line=line)
            # TODO 发送消息给钉钉
            ding_ding_api.send_message(cluster_name=project_id, servername=servername,
                                       runing_image_version=pod_name,
                                       namespace=namespace, verify_status=container_log)
    else:
        return False
    return True
