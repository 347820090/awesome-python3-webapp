#logging相当于print，将交互信息打印出来
import logging; logging.basicConfig(level=logging.INFO)
#asyncio是一个异步io的模块
import asyncio, os, json, time
from datetime import datetime
#aiohttp是服务端和客户端的库，web是个a服务端组件（模板？？）
from aiohttp import web

#响应页面
def index(request):
    return web.Response(body=b'<h1>Awesome</h1>')

@asyncio.coroutine
#这里的loop是asyncio模块装饰器自带的一个参数，用来创建异步io服务，init应该是他创建异步io函数的名
def init(loop):
    app = web.Application()
    app.router.add_route('GET','/',index)
    #教程里本来是app.make_handler()，我改为app了。
    srv = yield from loop.create_server(app, '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

#loop是asyncio模块的，实现异步io
loop = asyncio.get_event_loop()
#用loop异步io启动init函数
loop.run_until_complete(init(loop))
loop.run_forever()