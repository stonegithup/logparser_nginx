# logparser_nginx
# 不同的域名对应不同的日志文件
# 日志文件格式，见nginx.conf
# 动态获取不同的nginx配置文件
# 多线程加载不同的配置文件，并计算分析，发送到mq
# 随着日志文件销毁线程也一并回收
#

