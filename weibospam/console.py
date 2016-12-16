#--*coding:utf-8*--
import time
import os
import signal
import sys
from multiprocessing import Process

def status(file_mode=False,file_name='temp',addr='10.103.14.185',port=27017,dtbs='WEIBOTOPIC',coll='status'):
    import authorize
    import threading
    import pymongo
    from account import account
    from status import Status

    def Myhandler(signum,frame):
        with open(file_name,'w') as f:
            f.write('%s&%s' % (cursor,users.next()['id']))
        print '%s:Ready to kill myself.' % time.ctime()
        os._exit(0)
    signal.signal(signal.SIGTERM,Myhandler)

    conn=pymongo.Connection(addr,port)
    database=conn['%s' % dtbs]
    collection = database['%s' % coll]
    collection.ensure_index("mid",unique=True)
    if file_mode:
        with open(file_name) as f:
            a,b=f.read().strip().split('&')
            cursor=int(a)
            uid=int(b)
        users=database.user.find({'id':{'$gte':uid}}).sort('id',1).batch_size(1000)
    else:
        cursor=0
        users=database.user.find().sort('id',1).batch_size(1000)
    locker=threading.Lock()
    while True:
        client=authorize.APIClient(*account[cursor]).get_authorize()
        threads=list()

        start=int(time.time())
        for i in range(4):
            t=Status(client,collection,users,locker,start="2016-03-25-00",end="2016-03-26-00")
            threads.append(t)
            t.start()
        for t in threads:
            while t.is_alive():
                time.sleep(1)
            #t.join()
        end=int(time.time())
        if (end-start) < 10:
            print '%s:Request out of rate limit!' % time.ctime()
            break

        cursor=(cursor+1)%len(account)


if __name__=='__main__':
    if '-file' in sys.argv:
        print 'file mode'
        status(file_mode=True)
    else:
        status()
