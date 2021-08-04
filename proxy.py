import argparse
import asyncio
import websockets
import json
import ssl
import pathlib

import tokens
alice_oauth_token = tokens.alice_oauth_token

global connected
connected = False

async def hello(websocket, path):
    '''Called whenever a new connection is made to the server'''

    url = 'wss://uniproxy.alice.yandex.net/uni.ws'
    print('alice connected')
    global connected
    connected = True
    async with websockets.connect(url) as ws:
        print('ws conn')
        taskA = asyncio.create_task(fromYa(ws, websocket))
        taskB = asyncio.create_task(fromAlice(ws, websocket))
        #taskC = asyncio.create_task(pingServer(ws))

        await taskA
        await taskB
        #await taskC

async def pingServer(ws):
    err = False
    while not err:
        try:
            await ws.ping()
            print('ping')
            await asyncio.sleep(5)
        except:
            err = True
            print('ping err')

async def fromYa(ws, websocket):
    print('ya connected')
    disc = False
    while not disc:
        try:
            async for message in ws:
                if type(message) is str:
                    print(f'< {message}')
                else:
                    print('< *binary*')
                await websocket.send(message)
        except websockets.exceptions.ConnectionClosedError:
            disc = True
    global connected
    connected = False
    print('no more alice')


async def fromAlice(ws, websocket):
    print('ready to proxy')
    while connected:
        async for message in websocket:
            try:
                data = json.loads(message)
                #print('data')
                # token = data['event']['payload']['oauth_token']
                # if token == "":
                #     data['event']['payload']['oauth_token'] = "1.203622525.163361.1638166786.1606630786173.33085.QjEnzHeZhVILOti0.ii9C7443RtsFGcOmCBGlkz_Zyxc9jPw8G5qY6N_fQHz9js4X5aIyspPiuzZTfCK7qqufRnydbAfc5g_cWsHYfHlP-XKG2Xp-ezTGFxOMO-o8G38D.YWAysVsNa-quC3u7xkMFVA"
                # message = json.dumps(data)
                name = data['event']['header']['name']
                if name == 'SynchronizeState' or name == 'TextInput':
                    data['event']['payload']['oauth_token'] = alice_oauth_token
                #elif name == 'VoiceInput':
                #    data = mobile_ua
                message = json.dumps(data)
            except:
                await ws.send(message)
                print('> *binary*')
            else:
                print(f'> {message}')
                await ws.send(message)


if __name__ == '__main__':
    # parser = argparse.ArgumentParser(description='websocket proxy.')
    # parser.add_argument('--host', help='Host to bind to.',
    #                     default='localhost')
    # parser.add_argument('--port', help='Port to bind to.',
    #                     default=8765)
    # parser.add_argument('--remote_url', help='Remote websocket url',
    #                     default='ws://localhost:8767')
    # args = parser.parse_args()

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    localhost_pem = pathlib.Path(__file__).with_name("cert.pem")
    ssl_context.load_cert_chain(localhost_pem)

    start_server = websockets.serve(hello, '127.0.0.1', 443, ssl=ssl_context,max_queue=1)

    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()