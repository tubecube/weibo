#!/usr/bin/env python
#---*coding=utf-8*---

__author__='Gao Siyuan (lblbxuxu@126.com)'
import sys
import threading
import re
import time
from weibo import APIError

class Status(threading.Thread):
    def __init__(self,client,collection,users,locker,start='',end=''):
        threading.Thread.__init__(self)
        self.client=client
        self.collection=collection
        self.users=users
        self.locker=locker

        #parse and test time
        if start:
            self.startTime=time.mktime(time.strptime(start,'%Y-%m-%d-%H'))
        else:
            self.startTime=int(time.time()-2*24*60*60)
        if end:
            self.endTime=time.mktime(time.strptime(end,'%Y-%m-%d-%H'))
        else:
            self.endTime=int(time.time())
        if self.startTime>self.endTime:
            raise ValueError('start time must precede end time!')

    def run(self):
        while True:
            with self.locker:
                uid=self.users.next()['id']
            try:
                wbData=self.get_user_status(uid,self.startTime,self.endTime)
                if wbData:
                    wbData=map(self._mapper,wbData)
                    for i in wbData:
                        print i['text']
                    #self.collection.insert(wbData)
                    #print 'count:%s\r' % self.collection.count(),
                    sys.stdout.flush()
            except APIError,e:
                if e.error_code==10023:
                    #APIError->code=10023(User request out of rate limit!)
                    #需要更换client
                    break
                elif e.error_code==20003:
                    #APIError->code=20003(User does not exist!)
                    #从用户表中删去此用户
                    #self.db.user.remove({'id':uid})
                    print '20003'
                else:
                    print '%s:%s' % (time.ctime(),e)
    def get_user_status(self,uid,start,end):
        userWbLst=[]
        page=1
        flag=True
        while flag:
            tmp=self.client.statuses.user_timeline.get(page=page,uid=uid,trim_user=1)['statuses']
            if tmp:
                for each in tmp:
                    sign=self._test_time(each['created_at'],start,end)
                    if sign==1:
                        userWbLst.append(each)
                    elif sign==2:
                        continue
                    else:
                        flag=False
                        break
                page=page+1
            else:
                break
        return userWbLst

    def _mapper(self,_dict):
        #选择需要的字段
        d={'created_at':_dict['created_at'],\
            'ordinary':_dict['text'],\
            'uid':_dict['uid'],\
            'mid':_dict['idstr'],\
            'reposts':_dict['reposts_count'],\
            'comments':_dict['comments_count'],\
            'attitudes':_dict['attitudes_count'],\
            'retweeted':self._simplify(_dict['retweeted_status']['text']) if _dict.has_key('retweeted_status') else None,\
            'add_time':time.ctime()
            }
        d['text']=self._simplify(d['ordinary'])
        return d

    def _test_time(self,create,start,end):
        #检查微博发布时间
        #返回0：于设定起始时间之前；返回1：于设定起始时间与结束时间之间；返回2：于结束时间之后
        create=create[:19]+create[25:]
        with self.locker:
            createTime=time.mktime(time.strptime(create,'%a %b %d %H:%M:%S %Y'))
        if createTime<start:
            return 0
        elif start<createTime<end:
            return 1
        else:
            return 2

    def _simplify(self,text):
        #对微博内容做如下简单处理：
        #a. "abcd//abcd"去掉包括"//"之后的内容("//"表示转发)
        #b. "abcd@张三"去掉"@张三"
        #c. "abcd[笑]"去掉"[笑]"(格式表示表情)
        #d. "http://"(网址)
        text=re.sub('//.*$','',text)
        text=re.sub(u'(回复)?@\S+:?','',text)
        text=re.sub('\[.+\]','',text)
        text=re.sub(u'^(转发微博|轉發微博|[rR]epost|发表图片)$','',text)
        text=re.sub(u'我(发表|分享)了.*http:','',text)
        text=re.sub('http:','',text)
        return text
