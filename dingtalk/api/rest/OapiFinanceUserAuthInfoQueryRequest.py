'''
Created by auto_sdk on 2021.02.03
'''
from dingtalk.api.base import RestApi
class OapiFinanceUserAuthInfoQueryRequest(RestApi):
	def __init__(self,url=None):
		RestApi.__init__(self,url)

	def getHttpMethod(self):
		return 'POST'

	def getapiname(self):
		return 'dingtalk.oapi.finance.userAuthInfo.query'
