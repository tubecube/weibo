#!/usr/bin/env python
# -*-coding=utf-8-*-

'''
从新浪微博api爬取用户信息
object=User()
将新浪微博用户信息存入mongodb->coll中
object(coreUser)：从coreUser开始，获取其关注用户，进行遍历(e.g coreUser:12345678)
'''

__author__='Gao Siyuan (lblbxuxu@126.com)'

import authorize
import pymongo
import re
import time
import logging
from weibo import APIError
from account import account

class User(object):
    def __init__(self,db_addr='10.103.14.185',db_port=27017,dbName='WEIBOTOPIC',coll='user'):
        self.db=pymongo.Connection(db_addr,db_port)['%s' % dbName]
        self.coll=self.db['%s' % coll]
        self.account=account
        #logging.basicConfig(format='%(asctime)s %(filename)s %(message)s',datefmt='%a, %d %b %Y %H:%M:%S',filename='user.log')

    def __call__(self,coreUser=None):
        client=self.ch_client()
        if not coreUser:
            coreUser=self.getCoreuser()
        while True:
            try:
                userLst=self.getUser(client,coreUser)
                self.db.flag.update({'id':coreUser},{'$set':{'flag':0}})
            except APIError,e:
                print e
                if e.error_code==10023:
                    client=self.ch_client()
            else:
                self.insert(userLst)
            finally:
                coreUser=self.getCoreuser()
    def ch_client(self):
        #更换下一个账户
        t=self.account.pop(10)
        obj=authorize.APIClient(*t)
        client=obj.get_authorize()
        #logging.warning('Switched to account:%s app:%s!' % (t[0],t[2])
        print 'Switched to %s' % t[0]
        return client

    def getUser(self,client,coreUser):
        #爬取coreUser的关注用户的信息
        userLst=client.friendships.friends.get(uid=coreUser)['users']
        userLst=filter(self.filt,userLst)
        userLst=map(self.mapper,userLst)
        return userLst

    def insert(self,users):
        for user in users:
            #self.coll.insert(user)
            print user['name']
        #print 'total:%s'%self.coll.count()

    def mapper(self,dic):
        #保留部分字段
        return {'id':dic['id'],\
        'name':dic['screen_name'],\
        'followers':dic['followers_count'],\
        'friends':dic['friends_count'],\
        'verified':dic['verified'],\
        'verified_type':dic['verified_type'],\
        'bi_followers':dic['bi_followers_count'],\
        'flag':1,\
        'priority':None}

    def priority(self,a):
        if 2<=a<=8:
            return 0
        else:
            return 1

    def filt(self,_dict):
        #过滤掉部分垃圾用户
        if _dict['followers_count']<50:
            return False
        nickname=_dict['name']
        if re.search(u'用户\w+',nickname):
            return False
        if re.search(u'总代|代理|代购|化妆|服饰|美容',nickname):
            return False
        return True

    def getCoreuser(self):
        #从数据库中获得尚未遍历的用户
        coreUser=self.db.flag.find_one({'flag':1})
        return coreUser['id']

if __name__=='__main__':
    t=User()
    t()
