# logparser_nginx
# 
# email: wnfmq@126.com 
# nginx 日志分析的脚本，有如下功能
# 不同的域名对应不同的日志文件
# 日志文件格式，见nginx.conf
# 动态获取不同的nginx配置文件
# 多线程加载不同的配置文件，并按着周期计算分析，发送到rabbitmq
# 随着配置文件销毁线程也一并回收该域名的动态分析计算
# 
