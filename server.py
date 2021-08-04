import asyncio
import aiohttp
import random
import string
from aiohttp import web
import sqlite3
import logging
import json
import time

#cfc6bca8db016fd94445a97452d5a179
#36abc0e7cbc66de2f88cb355d40c41a4

logging.basicConfig(level=logging.DEBUG)

import tokens
app_id = tokens.ya_app_id
app_secret = tokens.ya_app_secret
redirect_to = tokens.ya_app_redirect

conn = sqlite3.connect('data.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
has_users = cur.fetchone()
if has_users is None:
    cur.execute("CREATE TABLE users (token TEXT NOT NULL PRIMARY KEY, mail TEXT NOT NULL);")

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices';")
has_devices = cur.fetchone()
if has_devices is None:
    cur.execute("CREATE TABLE devices (token TEXT NOT NULL PRIMARY KEY, mail TEXT NOT NULL, data TEXT NOT NULL);")

device_template = {
          "id": None,
          "name": None,
          "description": 'Windows - ПК',
          "type": 'devices.types.media_device.receiver',
          "capabilities": [
                {
                    "type": "devices.capabilities.range",
                    "retrievable": True,
                    "parameters": {
                        "instance": "channel",
                        "random_access": False,
                        "range": {
                            "max": 3,
                            "min": 1,
                            "precision": 1
                        }
                    }
                },
                {
                    "type": "devices.capabilities.range",
                    "retrievable": True,
                    "parameters": {
                        "instance": "volume",
                        "random_access": True,
                        "range": {
                            "max": 100,
                            "min": 0,
                            "precision": 5
                        },
                        "unit": "unit.percent"
                    }
                },
                {
                    "type": "devices.capabilities.toggle",
                    "retrievable": True,
                    "parameters": {
                        "instance": "mute"
                    }
                },
                {
                    "type": "devices.capabilities.toggle",
                    "retrievable": False,
                    "parameters": {
                        "instance": "pause"
                    }
                }
          ],
          "device_info": {
            "manufacturer": 'Abyr',
            "model": 'Zalg',
            "hw_version": '1',
            "sw_version": None
          }
        }

commands_db = {
    "devices.capabilities.range":{
        "volume":"volume",
        "channel":"song"
    },
    "devices.capabilities.toggle":{
        "mute":"mute",
        "pause":"playback"
    }
}

devices = {}
queue = {}

routes = web.RouteTableDef()

def dbg(var,varname=None,compact=False):
    if compact:
        if varname is None:
            varname = ""
        print(f'{varname} ({type(var)},{len(var)}): {var}')
    else:
        print('vvvvv')
        if varname is not None:
            print(varname)
        else:
            print('no name')
        print(f'type: {type(var)}')
        print(f'len: {len(var)}')
        try:
            var_json = json.dumps(var)
            print(json.dumps(var, indent=4, sort_keys=True))
        except:
            print(var)
        print('^^^^^')

@routes.get('/media/')
async def ya_receiver(req):
    reauth_json = {'start_account_linking':'meow','version':1.0}
    token = req.headers.get('Authorization')
    if token is None:
        print('lolnope')
        return web.json_response(reauth_json)
    #t = (token.replace('Bearer ',''),)
    #cur.execute(f'SELECT token FROM users WHERE token = ?;',t)
    #line = cur.fetchone()
    #if line is None:
    #    return web.json_response(reauth_json)
    print('account linking')
    return web.Response(text='meow')

@routes.get('/media/v1.0/user/devices')
async def get_devices(req):
    reauth_json = {'start_account_linking':'meow','version':1.0}
    token = req.headers.get('Authorization')
    if token is None:
        print('lolnope')
        return web.json_response(reauth_json)
    else:
        token = token.replace('Bearer ','')
        user_id = await get_ya_user(token)
        request_id = req.headers.get('X-Request-Id')
        devices_arr = []
        for dev in devices.get(user_id,[]):
            devices_arr.append(dev[0])
        print('get')
        payload = {'request_id':request_id,'payload':{'user_id':user_id,'devices':devices_arr}}
        print(payload)
        return web.json_response(payload)

@routes.post('/media/v1.0/user/devices/query')
async def query_devices(req):
    reauth_json = {'start_account_linking':'meow','version':1.0}
    token = req.headers.get('Authorization')
    if token is None:
        print('lolnope')
        return web.json_response(reauth_json)
    else:
        token = token.replace('Bearer ','')
        user_id = await get_ya_user(token)
        request_id = req.headers.get('X-Request-Id')
        devices_arr = []
        for dev_ws in devices.get(user_id,[]):
            dev = dev_ws[0]
            ws = dev_ws[1]
            new_dev = {}
            new_dev['id'] = dev['id']
            new_dev['capabilities'] = []
            fail = False
            for cap in dev['capabilities']:
                if cap['retrievable']:
                    new_cap = {}
                    cap_type = cap['type']
                    cap_subtype = cap['parameters']['instance']
                    new_cap['type'] = cap_type
                    new_cap['state'] = {}
                    new_cap['state']['instance'] = cap_subtype
                    state = await ws_poke_device(ws,(cap_type,cap_subtype))
                    if state['status'] == 'OK':
                        new_cap['state']['value'] = state['result']
                    elif state['error_code'] == 'DEVICE_UNREACHABLE':
                        fail = True
                    new_dev['capabilities'].append(new_cap)
            if fail:
                continue
            devices_arr.append(new_dev)
        print('query')
        payload = {'request_id':request_id,'payload':{'user_id':user_id,'devices':devices_arr}}
        print(payload)
        return web.json_response(payload)

@routes.post('/media/v1.0/user/devices/action')
async def action_devices(req):
    reauth_json = {'start_account_linking':'meow','version':1.0}
    token = req.headers.get('Authorization')
    if token is None:
        print('lolnope')
        return web.json_response(reauth_json)
    else:
        token = token.replace('Bearer ','')
        user_id = await get_ya_user(token)
        request_id = req.headers.get('X-Request-Id')
        data = await req.json()
        requested_changes = data['payload']['devices']
        my_devices_arr = []
        final_dev_arr = []
        for dev_ws in devices.get(user_id,[]):
            dev = dev_ws[0]
            ws = dev_ws[1]
            new_dev = {}
            new_dev['id'] = dev['id']
            new_dev['capabilities'] = []
            for cap in dev['capabilities']:
                new_cap = {}
                new_cap['type'] = cap['type']
                new_cap['state'] = {}
                new_cap['state']['instance'] = cap['parameters']['instance']
                new_dev['capabilities'].append(new_cap)
            my_devices_arr.append([new_dev,ws])
        dbg(requested_changes,'requested_chagnges')
        dbg(my_devices_arr,'my_devices_arr')
        for change in requested_changes:
            ya_dev_id = change['id']
            found_dev = False
            for mydev in my_devices_arr:
                if mydev[0]['id'] == ya_dev_id:
                    found_dev = True
                    for cap in change['capabilities']:
                        cap_type = cap['type']
                        cap_subtype = cap['state']['instance']
                        found_cap = False
                        for my_cap in mydev[0]['capabilities']:
                            if my_cap['type'] == cap_type and my_cap['state']['instance'] == cap_subtype:
                                found_cap = True
                                data = cap['state']
                                result = await ws_poke_device(mydev[1],(cap_type,cap_subtype),data)
                                if result['status'] == 'OK':
                                    my_cap['state']['action_result'] = {"status": "DONE"}
                                else:
                                    my_cap['state']['action_result'] = {"status": "ERROR","error_code":result['error_code'],'error_message':result['error_message']}
                                break
                        if not found_cap:
                            newcap = {'type':cap_type,'state':{'instance':cap_subtype,'action_result':{"status": "ERROR","error_code":'INVALID_ACTION','error_message':'Это устройство так не умеет. Попробуйте что-нибудь другое.'}}}
                            mydev[0]['capabilities'].append(newcap)
                    break
            if not found_dev:
                newdev = {'id':ya_dev_id,'action_result':{"status": "ERROR","error_code":'DEVICE_UNREACHABLE','error_message':'Устройство не отвечает. Проверьте, вдруг оно выключено или пропал интернет.'}}
                final_dev_arr.append(newdev)
        for dev in my_devices_arr:
            final_dev_arr.append(dev[0])
        print('action')
        payload = {'request_id':request_id,'payload':{'user_id':user_id,'devices':final_dev_arr}}
        print(payload)
        return web.json_response(payload)

@routes.get('/media/ws/')
async def ws_handler(req):
    ws = web.WebSocketResponse()
    await ws.prepare(req)

    dev,user_id = await register_ws(ws)

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                if msg.data == 'close':
                    await ws.close()
                else:
                    await handle_device(msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                print(f'ws connection closed with exception {ws.exception()}')
    except:
        pass

    await unregister_ws(ws,dev,user_id)
    print('websocket connection closed')
    return ws

async def get_queue(cmd_id):
    start = time.time()
    while True:
        resp = queue.get(cmd_id,None)
        if resp is not None:
            queue.pop(cmd_id)
            return resp
        else:
            if time.time() - start > 10:
                return
            else:
                await asyncio.sleep(0.2)

async def ws_poke_device(ws,parameter,data=None):
    if data is not None:
        value = data['value']
        if data.get('relative',False):
            relative = True
        else:
            relative = False
    else:
        value = None
        relative = None
    cmd_id = ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=32))
    command = commands_db[parameter[0]][parameter[1]]
    if data is None:
        command += '_get'
    else:
        command += '_set'
    try:
        await ws.send_str(json.dumps({'command':command,'id':cmd_id,'data':value,'relative':relative}))
    except:
        return {'status':'ERROR','error_code':'DEVICE_UNREACHABLE','error_message':'Устройство не отвечает. Проверьте, вдруг оно выключено или пропал интернет.'}
    print('sent')
    result = await get_queue(cmd_id)
    print(result)
    return result

async def get_ya_user(token):
    mail_resp = await aiohttp.ClientSession().get('https://login.yandex.ru/info',headers={'Authorization':f'OAuth {token}'})
    resp_json = await mail_resp.json()
    user_id = resp_json['id'] 
    return user_id

async def register_ws(ws):
    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
                dev = dict(device_template)
                dev['id'] = data['id']
                dev['name'] = data['name']
                dev['device_info']['sw_version'] = data['version']
                user_id = await get_ya_user(data['token'])
                if devices.get(user_id,None) is None:
                    devices[user_id] = [[dev,ws]]
                else:
                    devices[user_id].append([dev,ws])
                return dev,user_id
            except:
                ws.close()

async def unregister_ws(ws,dev,user_id):
    devices[user_id].remove([dev,ws])

async def handle_device(msg):
    msg = json.loads(msg)
    queue[msg['id']] = msg

app = web.Application()
app.add_routes(routes)
web.run_app(app,host='127.0.0.1')