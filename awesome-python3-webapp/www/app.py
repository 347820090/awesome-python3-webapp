#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
async web application.
'''

import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes,add_static

#这个函数应该是配置响应模板的环境。
def init_jinja2(app, **kw):
    logging.info('init jinja2...')
     # 字典的get()方法返回指定键的值, 如果值不在字典中返回默认值
    options = dict(
        autoescape = kw.get('autoescape', True),# 自动转义
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string = kw.get('variable_end_string', '}}'),
        auto_reload = kw.get('auto_reload', True)# 自动重新加载模板
    )
    path = kw.get('path', None)
    if path is None:
     # __file__获取当前执行脚本的路径
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
     # Environment(loader=PackageLoader('path'), 其他高级参数...)
    # 创建一个默认设定下的模板环境和一个在path目录下寻找模板的加载器
    #将当前目录下的templates文件夹作为加载模板的路径文件夹
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env

    #我们可以将 WSGI Middleware 了理解为 Server 和 Application 交互的一层包装，经过不同的 Middleware ，便拥有了不同的功能，EG. URL 路由转发、权限认证。因为Middleware能过处理所有通过的 request 和 response，所以要做什么都可以，没有限制。比如可以检查 request 是否有非法内容，检查 response 是否有非法内容，为 request 加上特定的 HTTP header
    #下面的factroy函数都属于Middleware的处理函数

# middlewar把通用的功能从每个URL处理函数中拿出来, 集中放到一个地方
# 接受一个app实例, 一个handler(URL处理函数, 如index), 并返回一个新的handler
async def logger_factory(app, handler):
    async def logger(request):
        #将用户的请求信息在命令行打印出来
        logging.info('Request: %s %s' % (request.method, request.path))
        # await asyncio.sleep(0.3)
        return (await handler(request))
    return logger

async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form: %s' % str(request.__data__))
        return (await handler(request))
    return parse_data

#这里的handler参数是个函数参数
async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        #handler是个函数参数
        r = await handler(request)
        # web.StreamResponse是HTTP响应处理的基类
        # 包含用于设置HTTP响应头，Cookie，响应状态码，写入HTTP响应BODY等的方法
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):#二进制流
            # 转换为web.Response对象
            resp = web.Response(body=r)
            # .*（ 二进制流，不知道下载文件类型）
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                #应该是返回Found类型的响应（404）
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                 # 序列化后的JSON字符串
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
            # 调用get_template()方法环境中加载模板，调用render()方法用若干变量来渲染它
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        # HTTP状态码和响应头部
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))
        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response

def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

async def init(loop):
    await orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='guixingniu', password='Woshishen112358', db='awesome')
    #我们可以将 WSGI Middleware 了理解为 Server 和 Application 交互的一层包装，经过不同的 Middleware ，便拥有了不同的功能，EG. URL 路由转发、权限认证。因为Middleware能过处理所有通过的 request 和 response，所以要做什么都可以，没有限制。比如可以检查 request 是否有非法内容，检查 response 是否有非法内容，为 request 加上特定的 HTTP header 等
    app = web.Application(middlewares=[
        logger_factory, response_factory
    ])
    #响应模板的环境（在哪加载模板等等）,这个datetime应该是python里的玩意，还有一种写法  init_jinja2(app,filters=dict(datetime=datetime_filter),path = r"E:\python\workspace\awesome-python3-webapp\www\templates")#初始化Jinja2，这里值得注意是设置文件路径的path参数
    init_jinja2(app, filters=dict(datetime=datetime_filter))#这个filters参数不知道是啥。删了也可以运行
    #（将‘handlers’模板中的对象添加到app的url处理函数中）
    add_routes(app, 'handlers')
    #添加静态文件
    add_static(app)
    srv = await loop.create_server(app, '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()