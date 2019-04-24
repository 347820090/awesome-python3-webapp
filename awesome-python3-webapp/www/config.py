#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
Configuration
'''

__author__ = 'Michael Liao'

#载入默认配置文件
import config_default

class Dict(dict):
    '''
    Simple dict but support access as x.y style.
    '''
    def __init__(self, names=(), values=(), **kw):
        #为字典的键和键值建立对应关系
        #super为Dict类初始化一个**kw
        super(Dict, self).__init__(**kw)
        for k, v in zip(names, values):
            self[k] = v

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

#将default和override中的配置合并，最终以override为准
def merge(defaults, override):#收集参数，参数是两个dic
    r = {}
    for k, v in defaults.items():
        # 如果覆盖文件有此参数
        if k in override:
            if isinstance(v, dict):# 判断是否其value为dict
                r[k] = merge(v, override[k])# 是的话，则创建新的字典后，调用原函数（递归）
            else:
                r[k] = override[k]# 否则把覆盖配置文件的值导入
        else:
            r[k] = v# 如果覆盖文件没有，就继续使用默认值
    return r#这个算法可以精确的覆盖配置字典里不同的项，很吊

#这个函数好像是把配置的dic对象转化为自定义的dic对象
def toDict(d):#d是一个dic
    D = Dict()
    for k, v in d.items():
        D[k] = toDict(v) if isinstance(v, dict) else v#这个递归有点吊，意思是如果键对应的键值还是个dic，n那么先把这个dic转化一下
    return D

#config是个dic对象
#首先，导入默认配置
configs = config_default.configs

try:
    import config_override
    configs = merge(configs, config_override.configs)
except ImportError:
    pass
#最后把config的dic转化一下，具体为啥后边再看
configs = toDict(configs)