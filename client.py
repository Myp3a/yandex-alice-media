import websockets
import asyncio
import json
import ssl
import time
from websockets import server

import win32api
from win32con import VK_MEDIA_PLAY_PAUSE, VK_MEDIA_NEXT_TRACK, VK_MEDIA_PREV_TRACK, KEYEVENTF_EXTENDEDKEY

from ctypes import POINTER, cast
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# import logging
# logging.basicConfig(level=logging.DEBUG)

import tokens
server_url = tokens.server_url
device_id = tokens.device_id
oauth_token = tokens.user_oauth_token

async def get_mute():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(
        IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    state = bool(volume.GetMute())
    return state

async def set_mute(val):
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(
        IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMute(val,None)
    state = await get_mute()
    return state

async def get_volume():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(
        IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    curvol = int(float(f"{volume.GetMasterVolumeLevelScalar():.2f}")*100)
    #print(curvol)
    return curvol

async def set_volume_low(target):
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(
        IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMasterVolumeLevelScalar(target,None)

async def set_volume(value):
    #curvol = await get_volume()
    await set_volume_low(float(value) / 100)
    curvol = await get_volume()
    return curvol

async def song_control(direction):
    if direction == 'next':
        key = VK_MEDIA_NEXT_TRACK
    elif direction == 'prev':
        key = VK_MEDIA_PREV_TRACK
    win32api.keybd_event(key, 0, KEYEVENTF_EXTENDEDKEY, 0)

async def playback_control():
    win32api.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_EXTENDEDKEY, 0)
     
async def execute_command(msg):
    cmd = msg
    result = {'status':None,'result':None}
    if cmd['command'] == 'volume_get':
        vol = await get_volume()
        result['status'] = 'OK'
        result['result'] = vol
    elif cmd['command'] == 'volume_set':
        if cmd['relative']:
            cur = await get_volume()
            value = cur + cmd['data']
            if value < 0:
                value = 0
            elif value > 100:
                value = 100
        else:
            value = cmd['data']
        if value > 100 or value < 0:
            result['status'] = 'ERROR'
            result['result'] = ('INVALID_VALUE','Какое-то незнакомое значение. Попробуйте другое.')
        else:
            vol = await set_volume(value)
            result['status'] = 'OK'
            result['result'] = vol
    elif cmd['command'] == 'song_get':
        result['status'] = 'OK'
        result['result'] = 2
    elif cmd['command'] == 'song_set':
        if cmd['relative']:
            value = cmd['data']
        else:
            value = cmd['data'] - 2
        if value == 1:
            await song_control('next')
            result['status'] = 'OK'
            result['result'] = 2
        elif value == -1:
            await song_control('prev')
            result['status'] = 'OK'
            result['result'] = 2
        else:
            result['status'] = 'ERROR'
            result['result'] = ('INVALID_VALUE','Какое-то незнакомое значение. Попробуйте другое.')
    elif cmd['command'] == 'mute_get':
        result['status'] = 'OK'
        result['result'] = await get_mute()
    elif cmd['command'] == 'mute_set':
        try:
            result['status'] = 'OK'
            result['result'] = await set_mute(cmd['data'])
        except:
            result['status'] = 'ERROR'
            result['result'] = ('INVALID_VALUE','Какое-то незнакомое значение. Попробуйте другое.')
    elif cmd['command'] == 'playback_get':
        result['status'] = 'OK'
        result['result'] = False
        # result['status'] = 'ERROR'
        # result['result'] = ('INVALID_ACTION','Это устройство так не умеет. Попробуйте что-нибудь другое.')
    elif cmd['command'] == 'playback_set':
        await playback_control()
        result['status'] = 'OK'
        result['result'] = False
    else:
        result['status'] = 'ERROR'
        result['result'] = ('INVALID_ACTION','Это устройство так не умеет. Попробуйте что-нибудь другое.')
    return result

async def parse_command(msg):
    cmd = json.loads(msg)
    cmd_id = cmd['id']
    return cmd_id,cmd

async def receiver(ws):
    async for msg in ws:
        cmd_id,cmd = await parse_command(msg)
        result = await execute_command(cmd)
        print(f'< {cmd}')
        if result['status'] == 'OK':
            json_result = {'status':'OK','result':result['result'],'id':cmd_id}
        else:
            json_result = {'status':'ERROR','error_code':result['result'][0],'error_message':result['result'][1],'id':cmd_id}
        print(f'> {json_result}')
        await ws.send(json.dumps(json_result))

# async def sender(ws, path):
#     while True:
#         msg = await read_queue()
#         await ws.send(msg)

async def handler(ws):
    receiver_task = asyncio.ensure_future(
        receiver(ws))
    # producer_task = asyncio.ensure_future(
    #     producer_handler(websocket, path))
    done, pending = await asyncio.wait(
        [receiver_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()

async def main():
    url = server_url
    dev_id = device_id
    login = {'token':oauth_token,'name':'Alice','id':dev_id,'version':'1'}
    async with websockets.connect(url,ssl=True) as ws:
        await ws.send(json.dumps(login))
        await handler(ws)

done = False
while not done:
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        print('bye')
        done = True
    except:
        print('connection failed, restarting')
        time.sleep(1)
#asyncio.get_event_loop().run_forever()