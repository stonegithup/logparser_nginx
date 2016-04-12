#!/usr/bin/python
# -*- coding: utf-8 -*-
# write by bit_stone
# wnfmq@126.com
# qq:1030700432
import ConfigParser
import string,os,sys
import socket
import subprocess
import time
import threading
import pika
import json

sys.setrecursionlimit(1000000) # '设置递归深度'


#程序的主路径
abspath=os.path.abspath(sys.argv[0]) 
work_path=os.path.dirname(abspath)+"/"

#读取配置文件
tmp_config=work_path+"conf/logparser.conf"
cf=ConfigParser.ConfigParser()
#print tmp_config
if os.path.exists(tmp_config):
    cf.read(tmp_config)
else:
    print "config file %s , not exists!!" % (tmp_config)
    print "Now the progress exit!!"
    sys.exit()

log_root_directory=cf.get("config","log_root_directory")
nginx_enable_directory=cf.get("config","nginx_enable_directory")
pidfile = cf.get("config","pidfile")

"所有的当前的域名记录"
#global g_domain
g_domain=[]
"新增的域名记录"
a_domain=[]
"减少的域名记录"
n_domain=[]
"运行的域名记录"
r_domain=[]
"获取系统主机名称"
def get_hostname():
        hopen = subprocess.Popen('hostname -f', shell=True, stdout=subprocess.PIPE)
        hopen.wait()
        return hopen.stdout.read().strip("\n")
hostname=get_hostname()
"遍历文件获取 all domainname"
def get_all_domain():
        global g_domain
        g_domain=[]
        tmp_domain=[]
        for i in os.listdir(nginx_enable_directory):
            z = os.path.join(nginx_enable_directory,i)
            if os.path.isfile(z):
                _fd=open(z,"r")
                _buf=_fd.readlines()
                _fd.close()
                for _t in _buf:
                    _f,_,_g=_t.partition('server_name')
                    if _g != "":
                        if _f.find("#")>-1:
                            continue
                        _g=_g.strip("\n").strip(" ").strip(';').strip(" ")
                        #print _g,
                        #print 
                        tmp_domain.append(_g)
        g_domain=list(set(tmp_domain))
"得到域名已经不存在（删除）的记录"
def get_del_domain():
        global n_domain
        global r_domain
        n_domain=[]
        for i in r_domain:
            for z in g_domain:
                if z == i:
                    mark=0;
                    break;
                else:
                    mark=1
            if mark==1:
                n_domain.append(i)
        #print n_domain
"获取新增的域名记录"
def get_add_domain():
        global a_domain
        global r_domain
        a_domain=[]
        mark=1
        for i in g_domain:
            for z in r_domain:
                if z == i:
                    mark=0;
                    break;
                else:
                    mark=1
                    continue
            if mark==1:
                a_domain.append(i)
        #print "new add:",a_domain

class LogParser(threading.Thread):
    def __init__(self,lock,threadName):
        #threading.Thread.__init__(self);
        super(LogParser, self).__init__(name = threadName) 
        self.lock = lock
        '轮询周期'
        self.cycle=300
        'mq初始化'
        self.domain_name=threadName
        self.mq_name="traffic_data"       
        self.mq_address="mq.y7tech.cn"     
        self.mq_init()
    "打印当前运行的域名"
    def print_running_domain(self):
        global r_domain
        for i in r_domain:
            print i
    
    "------------------------------------------------------------"
    "读取存取的配置文件的起始时间,和上次的最后一次传输时间一致，保证数据不丢失,从发送保存记录里面找"
    def get_start_time(self):
        global work_path
        _trf_filename=work_path + "/data/" + self.domain_name + ".trf"
        if os.path.exists(_trf_filename):
            _fd=open(_trf_filename,'r+')
            _buf=_fd.readlines()
            _fd.close()
            _len_count=len(_buf)
            if _len_count ==0:
                return 0
            i=_buf[_len_count-1]
            _data=json.loads(i)
            _data=json.loads(_data)
            return  _data["endtime"]
        else:
            return 0
        '''
        只在当前第一次运行的时候运行
        读取当前domain的发送记录.
        当文件不存在,发送0,并创建文件
        读取第一列排序.
        返回最大的时间 bigint
        '''
        pass
    "获取日志切割的时间有无在这次读取的时间列表里面，有的话需要从多个配置文件里面读取"
    def get_log_file(self,_start_time=None):
        global log_root_directory
        _domain_name_str=self.domain_name+'.access.log'
        _tmp_file_list=[]
        for i in os.listdir(log_root_directory):
            if i.find(_domain_name_str)>-1:
                _i_abs_path=os.path.join(log_root_directory,i)
                #print _i_abs_path
                _statinfo=os.stat(_i_abs_path)
                if _statinfo.st_mtime >= _start_time:
                    _tmp_file_list.append(_i_abs_path)
        return _tmp_file_list
        '''
        读取当前目录下面的所有文件名称
        找到domain_name开头的所有文件
        获得domain_name的modifytime > _start_time,记录当前文件名称.
        得到要初始化的文件列表
        '''
    "日志分析"
    def log_parser(self,_start_time=0,_file_list=[]):
        global log_root_directory
        global hostname
        t2 = t3 = t4 = t5 = to = sum_traffic = 0
        _cur_time=int(time.time())
        _end_time=0
        #print self.domain_name,_file_list,_start_time,_cur_time
        if _start_time!=0:
            _end_time=_start_time+self.cycle
        if _end_time > _cur_time:
            return _start_time 
        
        for _log_filename in _file_list:
            _fd=open(_log_filename,'r')
            _readline=_fd.readline()
            if _readline:
                new_line=_readline.split(' ')
                _log_time=int(new_line[0].split('.')[0])
            else:
                if _start_time == 0:
                    _end_time = _cur_time
                break
            if _start_time == 0:
                _start_time = int(_log_time)
                _end_time = _start_time
            while _end_time%self.cycle != 0:
                'first to run !'
                _end_time += 1 
            if _end_time > _cur_time:
                _fd.close()
                continue
            #print _start_time
            #print _end_time
            while _readline:
                new_line=_readline.split(' ')
                #print new_line
                #new_line[0],new_line[5],new_line[7]
                _log_time=int(new_line[0].split('.')[0])
                if _start_time==0:
                    _start_time=_log_time
                if _log_time >= _start_time and _log_time <= _end_time:
                    new_time=int(new_line[0].split('.')[0])
                    new_status=new_line[4] # 2xx 3xx 4xx 5xx 6xx status
                    new_band = int(new_line[6]) # band
                    sum_traffic += new_band
                    if new_status.startswith("20"):
                        t2 += new_band
                    elif new_status.startswith("30"):
                        t3 += new_band
                    elif new_status.startswith("40"):
                        t4 += new_band
                    elif new_status.startswith("50"):
                        t5 += new_band
                    else:
                        to += new_band
                #elif _log_time > _end_time:
                #    contine
                _readline=_fd.readline()
            _fd.close()
                #if _end_time + self.cycle < _cur_time:
                #    print " _end_time ,  _cur_time ",_end_time , _cur_time 
                #    _tmp_file_list=self.get_log_file(_end_time)
                #    self.log_parser(_end_time,_tmp_file_list,self.domain_name)
        print hostname,self.domain_name,_start_time,_end_time,sum_traffic,t2,t3,t4,t5,to
        _send_data={}
        _send_data.update({"hostname":hostname})
        _send_data.update({"domainname":self.domain_name})
        _send_data.update({"starttime":_start_time})
        _send_data.update({"endtime":_end_time})
        _send_data.update({"traffic":sum_traffic})
        _send_data.update({"t2":t2})
        _send_data.update({"t3":t3})
        _send_data.update({"t4":t4})
        _send_data.update({"t5":t5})
        _send_data.update({"to":to})
        self.traflog_sender()
        self.mq_send(_send_data)
        return _end_time
        '''
        文件循环
        读取文件列表的文件----行
        文件内容循环
        判断当前时间 是否大于 _start_time && < _start_time+self.cycle
        否 判断是否大于_start_time+self.cycle 退出循环
        否 判断<_start_time && continue
        是 
            traffic+=traffic
            if status == 2xx :
            t2+=t2
        调用log发送模块送出当前分析的log
        '''
    "日志发送模块"
    def traflog_sender(self):
        '''
        读取有无异常的记录
        try 
            mqsend
            mqwrite(0)
        exception
            mqwrite(1)
        '''
    "mq不存在则初始化模块,放在程序运行的时候调度一次即可"
    def mq_init(self):
        credentials = pika.PlainCredentials('zyp_mq', 'zyp_mq_mq')
        connection = pika.BlockingConnection(pika.ConnectionParameters(self.mq_address,5672,'/',credentials))
        channel = connection.channel()
        channel.queue_declare(queue=self.mq_name)
        connection.close()
    "发送mq信息"
    def mq_send(self,_traffic_data={}):
      try:
        credentials = pika.PlainCredentials('zyp_mq', 'zyp_mq_mq')
        connection = pika.BlockingConnection(pika.ConnectionParameters(self.mq_address,5672,'/',credentials))
        channel = connection.channel()
        channel.queue_declare(queue=self.mq_name)
        _traf_data=json.JSONEncoder().encode(_traffic_data)
        channel.basic_publish(exchange='', properties=pika.BasicProperties(\
                delivery_mode = 1, \
                content_encoding = "UTF-8" ,\
                content_type = "application/json"),
                routing_key=self.mq_name,body=_traf_data)
        connection.close()
        self.mq_write(0,_traffic_data)
      except :
        self.mq_write(1,_traffic_data)
    "mq信息保存"
    def mq_write(self,status=0,_traffic_data={}):
        _trf_filename=work_path + "/data/" + self.domain_name + ".trf"
        _sendfail_log=work_path + "/data/" + self.domain_name + ".fail"
        _traf_data=json.JSONEncoder().encode(_traffic_data)
        if status == 0:
            #_readed = json.load(open('jsonsource.dat', 'r'))
            _fd=open(_trf_filename,'a+')
            if _fd.tell!=0:
                _fd.write('\n')
            _fd.close()
            json.dump(_traf_data, open(_trf_filename, 'a+'))
        else:
            _fd=open(_trf_filename,'a+')
            if _fd.tell!=0:
                _fd.write('\n')
            _fd.close()
            json.dump(_sendfail_log, open(_sendfail_log, 'a+'))
    "---------------------------------------------------------"
    "发送失败信息重新发送模块,这个可以放在mqsend里面"
    def rewrite_mq(self):
        pass
    '单个域名调度进入接口'
    def domain_start(self):
        global  n_domain
        global r_domain
        _tmp_start=self.get_start_time()
        print "tmp_start:",self.domain_name,_tmp_start
        while True:
            _tmp_log_file=self.get_log_file(_tmp_start)
            #print _tmp_log_file
            _end_time=self.log_parser(int(_tmp_start),_tmp_log_file)
            #print _tmp_start,_end_time
            if _end_time == _tmp_start:
                time.sleep(self.cycle)
            _tmp_start=_end_time
            sig = 1
            for i in n_domain:
                if i==self.domain_name:
                    sig=0;
                    break
                else:
                    sig=1
            if sig==0:
                n_domain.remove(i)
                r_domain.remove(i)
                print "domain:%s to stopping ....\n"
                break
            #print "tmp_2start:",self.domain_name,_tmp_start
            

    def run(self):
        self.domain_start()
        pass

pid=os.getpid()

open(pidfile,'w').write(str(pid))

lock = threading.Lock()
while True:
    get_all_domain()
    get_del_domain()
    get_add_domain()
    for i in a_domain:
        print "domain:%s to running.... \n" %(i)
        LogParser(lock,i).start()
        r_domain.append(i)
    time.sleep(60)

