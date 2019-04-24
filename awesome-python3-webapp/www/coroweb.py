#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web

from apis import APIError

#这个函数是个自定义装饰器，给浏览器输入赋予属性“get”和“path”，和下面的post函数一样
def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

#自定义装饰器，给func赋予了method和route属性。实际上是个处理url的函数，赋予了其url的属性“post”和“path”（分析输入浏览器请求的属性）
def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

#RequestHandler目的就是从URL函数中分析其需要接收的参数，从request中获取必要的参数，调用URL函数，然后把结果转换为web.Response对象，这样，就完全符合aiohttp框架的要求
class RequestHandler(object):

#为处理函数的子类赋予属性
#这个__init__应该自动赋予了一个对象属性
    def __init__(self,app,fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    async def __call__(self, request):
        kw = None
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        # check required kw:
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

# 添加静态资源路径
def add_static(app):
    # os.path.abspath()返回绝对路径, os.path.dirname()返回path的目录名, os.path.join()将多个路径组合
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
     # add_static(处理的静态资源的URL路径前缀, 文件系统中包含处理的静态资源的文件夹路径)
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))

#这个函数是为请求添加响应的路由
# 注册URL处理函数
def add_route(app, fn):
    #提取请求的属性
    #这里的fn应该是前边定义的class RequestHandler(object)，所以自动有下面的属性
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
     # inspect.signature(fn)将返回一个inspect.Signature类型的对象, 值为fn这个函数的所有参数
    #inspect.Signature对象的paramerters属性是一个mappingproxy(映射)类型的对象，值为一个有序字典(Orderdict)。
# 这个字典里的key即为参数名，str类型;value是一个inspect.Parameter类型的对象，包含的一个参数的各种信息
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))#把处理函数的名和参数信息以及路径打印出来
    #这里的RequestHandler(app, fn)是个web.Response对象
    #把path路径下的method处理函数添加到app响应函数中为一个web.Response对象
    #这个RequestHandler(app, fn)直接把函数变为app的一个__func属性，且包含了参数信息
    app.router.add_route(method, path, RequestHandler(app, fn))

#这个函数应该是根据加载的模板名获取模板对象的属性及方法，然后将其方法和路径添加到app的url处理函数里
def add_routes(app, module_name):
    # rfind(字符串)返回字符串最后一次出现的位置, 如果没有匹配项则返回-1
    n = module_name.rfind('.')
    if n == (-1):
         # __import__(name[, globals[, locals[, fromlist[, level]]]])函数用于动态加载类和函数
        # globals()返回全局变量的字典, locals()返回当前局部变量的深拷贝(新建对象，不改变原值)
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    # dir()函数可以查看对象内所有属性及方法
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)