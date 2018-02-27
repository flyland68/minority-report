#!/bin/env python
# -*- coding:utf-8 -*-

"""
The xunfei asr client.

Authors: Alex Lu(flyland_lf@hotmail.com)
"""

import base64
import sys
import time
import json
import hashlib
import requests
import urllib
import ffmpeg
import os

def save_amr(voice_url):
    amr_name = 'tmp_amr.amr'
    with open(amr_name, 'w') as f:
        f.write(urllib.urlopen(voice_url).read())
    return amr_name


def transform(amr_file):
    wav_name = 'tmp_wav.wav'
    os.remove(wav_name)
    stream = ffmpeg.input(amr_file)
    stream = ffmpeg.output(stream, wav_name)
    ffmpeg.run(stream)
    with open(wav_name) as f:
        return f.read()
    

def call(voice_url):
    amr_file = save_amr(voice_url)
    wav_content = transform(amr_file)
    
    
    x_appid = '5a6ebec2'
    requrl = 'http://api.xfyun.cn/v1/aiui/v1/iat'
    cur_time = int(time.time())
    x_param = {"auf":"8k","aue":"raw","scene":"main"}
    x_param = json.dumps(x_param)
    xparam_base64 = base64.b64encode(x_param.encode(encoding="utf-8")).decode().strip('\n')
    file_base64 = base64.b64encode(wav_content)
    body_data = "data=" + file_base64.decode("utf-8")
    api_key = '190502cdb59644999201fc63228227fb'
    token = api_key + str(cur_time) + xparam_base64 + body_data
    m = hashlib.md5()
    m.update(token.encode(encoding='utf-8'))
    x_check_sum = m.hexdigest()
    headers = {"X-Appid": x_appid,"X-CurTime": str(cur_time),"X-Param":xparam_base64,"X-CheckSum":x_check_sum,"Content-Type":"application/x-www-form-urlencoded"}
    
    response = requests.post(requrl, data=body_data, headers=headers)
    return json.loads(response.content)
