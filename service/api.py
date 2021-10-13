import requests
import json
import dingtalk.api
import time


class Api(object):
    def __init__(self, rancher_ip, rancher_token):
        self.rancher_ip = rancher_ip
        self.rancher_token = "Bearer %s" % rancher_token
        self.header = {"Authorization": self.rancher_token,
                       "Content-Type": "application/json"}

    def cluster_info(self, optional_key='project_id') -> list:
        """
        获取rancher中所有集群的集群名和集群id
        optional_key 选择返回的字典的key
        :return: 包含集群id和集群名的字典的列表
        """
        cluster_url = 'https://%s/v3/clusters' % self.rancher_ip
        clusters_res = requests.get(cluster_url, headers=self.header, verify=False)
        dic_clusters_res = json.loads(clusters_res.text)
        # project
        project_url = 'https://%s/v3/project/' % self.rancher_ip
        project_res = requests.get(project_url, headers=self.header, verify=False)
        dic_project_res = json.loads(project_res.text)

        cluster_info = []
        # 提取集群信息
        for clusters_actions in dic_clusters_res['data']:
            cluster_name = clusters_actions['name']
            cluster_id = clusters_actions['id']
            if cluster_name != 'local':
                # 提取项目信息
                for project_actions in dic_project_res['data']:
                    project_name = project_actions['name']
                    project_id = project_actions['id']
                    project_cluster_id = project_actions['clusterId']
                    # 获取rancher中default项目的id
                    if project_name == 'Default':
                        if project_cluster_id == cluster_id:
                            # 选择返回project_id为key还是cluster_name为key
                            # project_id:项目id cluster_name:组名 cluster_id:组id
                            if optional_key == 'project_id':
                                cluster_info.append({project_id: cluster_name})
                            elif optional_key == 'cluster_name':
                                cluster_info.append({cluster_name: project_id})

        # print(cluster_info)
        return cluster_info

    def get_server_state(self, semaphore_obj, project_id, namespace, servername, publish_image_version, dingding_obj,
                         cluster_name):
        """
        获取服务状态 active or notactive 如果是active返回镜像版本号
        :param semaphore_obj:    进程对象
        :param project_id:    rancher 项目（组）id
        :param namespace:   k8s命名空间
        :param servername:  具体的服务名
        :param publish_image_version:  发布的版本号
        :param dingding_obj:  钉钉对象
        :param cluster_name:  组名
        :return: server_state 如果是active返回镜像版本号,如果不是active 返回False
        """

        # 判断状态如果成功发送成功消息，如果失败等一分钟
        for _ in range(5):
            url = 'https://%s/v3/project/%s/workloads/deployment:%s:%s' \
                  % (self.rancher_ip, project_id, namespace, servername)
            server_info = requests.get(url, headers=self.header, verify=False)
            server_info_dict = json.loads(server_info.text)
            semaphore_obj.acquire()
            # 服务状态
            server_state = server_info_dict['state']

            if server_state == 'active':
                # print(server_info_dict['containers'], '123')
                for container in server_info_dict['containers']:
                    image = container['image']
                    image_version = image.split(':')[1]
                    if publish_image_version == image_version:
                        dingding_obj.send_message(cluster_name=cluster_name, servername=servername,
                                                  runing_image_version=publish_image_version,
                                                  namespace=namespace, verify_status='success!')
                        return True
            time.sleep(10)
        dingding_obj.send_message(cluster_name=cluster_name, servername=servername,
                                  runing_image_version=publish_image_version,
                                  namespace=namespace, verify_status='failed!')
        semaphore_obj.release()
        return False

    def get_pod_name(self, project_id, namespace, servername):
        """
        获取pod名
        :param project_id: 项目id
        :param namespace: 命名空间
        :param servername: 服务名
        :return: 包含pod名的列表 没找到返回false
        """
        url = 'https://192.168.0.100/v3/project/%s/pods' % project_id
        runing_server_name = ''  # 运行的服务名
        pod_name_list = []  # pod名列表
        pod_name = ''  # pod名
        pod_info = requests.get(url, headers=self.header, verify=False)
        pod_info_dict = json.loads(pod_info.text)
        pod_data_info = pod_info_dict['data']
        for server_data in pod_data_info:
            # 获取命名空间名字
            namespace_id = server_data['namespaceId']
            if namespace_id != namespace:
                continue
            # 获取服务名
            for container in server_data['containers']:
                runing_server_name = container['name']
                if runing_server_name == servername:
                    continue
            # pod名
            pod_name = server_data['name']
            # 如果是要的服务加到列表
            if runing_server_name == servername:
                pod_name_list.append(pod_name)
                continue

        if pod_name_list:
            return pod_name_list
        else:
            return False

    def get_container_log(self, cluster_id, namespace, pod_name, servername, line):
        """
        获取容器日志
        :param cluster_id: 集群id
        :param namespace: 命名空间
        :param pod_name: pod 名
        :param servername: 服务名
        :param line: 查看多少行
        :return: container_log log日志文本
        """
        url = 'https://%s/k8s/clusters/%s/api/v1/namespaces/%s/pods/%s/log?container=%s&tailLines=%s&timestamps=true&previous=false' \
              % (self.rancher_ip, cluster_id, namespace, pod_name, servername, line)
        container_log_text = requests.get(url, headers=self.header, verify=False)
        container_log_text.encoding = 'utf8'
        container_log = container_log_text.text
        return container_log


class dingding_api(object):
    def __init__(self, webhook):
        self.webhook = webhook

    def send_message(self, cluster_name, servername, runing_image_version, namespace, verify_status):
        # 请求参数
        request = dingtalk.api.OapiRobotSendRequest(self.webhook)
        request.msgtype = 'text'
        # 向钉钉机器人发送发布校验消息
        message = '%s %s组的%s:%s %s 服务发布校验%s' % (
            verify_status, cluster_name, servername, runing_image_version, namespace, verify_status)
        # 如果失败会@我
        if verify_status == 'failed!':
            # 引入需要发送的内容
            request.text = {
                "content": message
            }
            # atMobiles:钉钉群中所对应的成员手机号
            # isAtAll：当设置为True时，发送消息时@所有人
            request.at = {
                "atMobiles": ["18811170582"],
                "isAtAll": False
            }
        else:
            # 引入需要发送的内容
            request.text = {
                "content": message
            }
        response = request.getResponse()
        print(response)

# a = Api(rancher_ip='xxxx')
# b = a.get_server_state(project_group_id='c-2p52k:p-42dhh',namespace='domain', servername='authority')
# print(b)

# a = dingding_api(webhook='https://oapi.dingtalk.com/robot/send?access_token=8b52730c7c397e7dd424874564ae35fbdd58ffcd27b4d4064e1da5e3a6bb6504')
# b = a.send_message(cluster_name='zw6',servername='hte',verify_status='success')
# print(b)
# rancher_api = Api(rancher_ip='192.168.0.100',
#                   rancher_token='token-d4vbt:84qzrlrctrmxscwg4g2h996hzkxb25xzlwpvwkbk477897qm8pl4ls')
# rancher_api.get_pod_name(project_id='c-2p52k:p-42dhh',namespace='domain',servername='authority')
# rancher_api.get_container_log(cluster_id='c-2p52k', namespace='domain',
#                               pod_name='authority-b45bd4cd4-5xbf7', servername='authority', line='100')
