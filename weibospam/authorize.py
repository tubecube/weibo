#!/usr/bin/env python
#--*coding=utf-8*--

'''
模拟用户授权app，app获取access_token
将获取的access_token保存在access_token文件中
'''

__author__ = 'lblbxuxu@126.com'

import urllib2
import urllib
import weibo
import weiboconfig
import base64
import time
import re
import json
import rsa
import binascii
from bs4 import BeautifulSoup

class SmartRedirectHandler(urllib2.HTTPRedirectHandler):
    def http_error_301(self,req,fp,code,msg,headers):
        #location=headers.getheader('location')
        #print location
        return fp
    def http_error_302(self,req,fp,code,msg,headers):
        #location=headers.getheader('location')
        #print location
        return fp

def redirect_handler(func):
    def wrapper(*args):
        opener = urllib2.build_opener(SmartRedirectHandler())
        urllib2.install_opener(opener)
        # print 'using redirect'
        r = func(*args)
        return r
    return wrapper

class SomeBadError(StandardError):
    '''
    raise SomeBadError if error occurred while authorizing.
    '''
    def __init__(self, error_msg):
        self.error_msg = error_msg
        StandardError.__init__(self, error_msg)

    def __str__(self):
        return "%s" % error_msg

class MyClient(weibo.APIClient):
    """
    Usage:
    MyClient(app_info, [account_info], [token_file])
    app_info: (app_key, app_secret, callback_uri).
    account_info: (weibo account, password).
    token_file: file that saves tokens.
    """

    _tokens = [] 
    # {'app_key': appkey, 'waccount': 1234,
    # 'access_token': xxx, 'expires': 123}

    def __init__(self, app_info, account_info=()):
        assert isinstance(app_info, tuple) and len(app_info)==3, self.__doc__
        super(MyClient, self).__init__(*app_info)
        
        self.set_account_info(account_info)
        
        self.my_token = self.search_token()
        if self.my_token:
            self.set_access_token(self.my_token['access_token'], self.my_token['expires'])
        else:
            self.my_token = {'app_key': self.client_id, 'waccount': self.waccount,
            'access_token': '', 'expires': ''}
            self.__class__._tokens.append(self.my_token)

    def set_account_info(self, account_info):
        if len(account_info)==2:
            self.waccount = account_info[0]
            self.wpasswd = account_info[1]
        else:
            self.waccount = self.wpasswd = ""

    def search_token(self):
        for token_d in MyClient._tokens:
            if token_d['app_key'] == self.client_id and token_d['waccount']==self.waccount:
                return token_d
        return {}

    @classmethod
    def load_tokens(cls, filename="tokens.txt"):
        try:
            fp = open(filename, 'r')
        except IOError:
            return
        for each_token in fp:
            cls._tokens.append(json.loads(each_token))
        fp.close()
    
    @classmethod
    def save_tokens(cls, filename="tokens.txt"):
        fp = open(filename, 'w')
        string = ""
        for token_d in cls._tokens:
            string += json.dumps(token_d)
            string += '\n'
        fp.write(string.strip())
        fp.close()
    
    def do_authorize(self):
        if self.is_expires():
            code = self._get_code()
            d = self.request_access_token(code) 
            self.set_access_token(d['access_token'], d['expires_in'])
            print "access token get!\n" + str(d)
            self.my_token['access_token'] = d['access_token']
            self.my_token['expires'] = d['expires_in']
        else:
            print "authorize success!"

    def _get_code(self):
        if not self.account:
            raise SomeBadError("We need a weibo account before authorization.")
        _data1 = self._request_before_login()
        ticket = self._get_ticket(_data1['appkey62'])
        _data1['ticket'] = ticket
        # print "ticket: %s" % ticket
        code = self._request_post_login(_data1)
        return code
    
    def _get_ticket(self, appkey):
        su = base64.b64encode(self.waccount)
        prelogin_url = "https://login.sina.com.cn/sso/prelogin.php" + '?' +\
                urllib.urlencode({'entry':'openapi',\
               'callback':'sinaSSOController.preloginCallBack',\
               'su':su,'rsakt':'mod',\
               'checkpin':1,'client':'ssologin.js(v1.4.15)',\
               '_':str(time.time()).replace('.', '')[:13]})
        
        # get nonce, pubkey, rsakv, servertime
        data = urllib2.urlopen(prelogin_url).read()

        p = re.compile('\{.*\}')
        js = p.search(data).group(0)
        d = json.loads(js)
        nonce = d['nonce']
        pubkey = d['pubkey']
        rsakv = d['rsakv']
        servertime = d['servertime']

        # encrypt password using rsa
        pubkey = int(pubkey, 16)
        key = rsa.PublicKey(pubkey, 65537)
        mes = str(servertime) + '\t' + str(nonce) + '\n' + str(self.wpasswd)
        sp = binascii.b2a_hex(rsa.encrypt(mes, key))

        # login
        postdata = urllib.urlencode({'entry':'openapi',\
                'gateway':1,\
                'from':'',\
                'savestate':0,\
                'useticket':1,\
                'pagerefer':'',\
                'ct':1800,\
                's':1,\
                'vsnf':1,\
                'vsnval':'',\
                'door':'',\
                'appkey':appkey,\
                'su':su,\
                'service':'miniblog',\
                'servertime':servertime,\
                'nonce':nonce,\
                'pwencode':'rsa2',\
                'rsakv':rsakv,\
                'sp':sp,\
                'sr':'1310*731',\
                'encoding':'UTF-8',\
                'cdult':2,\
                'domain':'weibo.com',\
                'prelt':158,\
                'returntype':'TEXT'})
        login_url = 'https://login.sina.com.cn/sso/login.php' + '?' + urllib.urlencode({'client':'ssologin.js(v1.4.15)','_':str(time.time()).replace('.','')[:13]})
        headers = {'Referer':self.get_authorize_url(), 'Content_Type':'application/x-www-form-urlencoded'}
        req = urllib2.Request(login_url, postdata, headers)
        res = urllib2.urlopen(req)
        data = res.read()
        # print data
        d = json.loads(data)
        if d['retcode'] == '0':
            ticket = d['ticket']
        else:
            ticket = None        
        return ticket

    def _request_before_login(self):
        r = urllib2.urlopen(self.get_authorize_url())
        soup = BeautifulSoup(r.read(), 'lxml')
        data = {}
        for tag in soup.find_all('input', type='hidden'):
            try:
                name = tag['name']
                value = tag['value']
                data[name] = value
            except:
                continue
        return data
        
    @redirect_handler
    def _request_post_login(self, postdata):
        code = None
        authorize_url = "https://api.weibo.com/oauth2/authorize"
        headers = {'Referer':self.auth_url, 'Content_Type':'application/x-www-form-urlencoded'}
        req = urllib2.Request(authorize_url, urllib.urlencode(postdata), headers)
        res = urllib2.urlopen(req)
        if res.code == 200:
            soup = BeautifulSoup(res.read(), 'lxml')
            data = {}
            for tag in soup.find_all('input', type='hidden'):
                try:
                    name = tag['name']
                    value = tag['value']
                    data[name] = value
                except:
                    continue
            req = urllib2.Request(authorize_url, urllib.urlencode(data),
            headers)
            res = urllib2.urlopen(req)
            
        if res.code == 302:
            location = res.headers.getheader('location')
            data = location.split('?')[1]
            k, v = data.split('=')
            code = v
        return code


if __name__ == '__main__':
    KEYS_SECRETS = weiboconfig.APP_KEYS_SECRETS
    waccount = weiboconfig.ACCOUNT1
    wpasswd = weiboconfig.PASSWORD1
    callback = weiboconfig.CALLBACK_URI
    MyClient.load_tokens("tokens.txt")
    for key, secret in KEYS_SECRETS:
        client = MyClient((key, secret, callback), account_info=(waccount, wpasswd))
        client.do_authorize()
    MyClient.save_tokens("tokens.txt")
