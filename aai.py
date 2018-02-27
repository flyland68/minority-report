#!/bin/env python
# -*- coding:utf-8 -*-

"""
The tencent aai client.

Authors: Alex Lu(flyland_lf@hotmail.com)
"""

import os
import time
import random
import requests
import urllib
import hmac
import base64
import hashlib
import logging
import json

AAI_APPID = os.getenv('AAI_APPID', '')
AAI_SECRETID = os.getenv('AAI_SECRETID', '')
AAI_SECRETKEY = os.getenv('AAI_SECRETKEY', '')

AAI_URL = 'aai.qcloud.com/asr/v1/'

def call(voice_url):
    params_map = {
        'channel_num': 1,
        'secretid': AAI_SECRETID,
        'engine_model_type': '8k_0',
        'sub_service_type': 0,
        'projectid': 0,
        'callback_url': 'http://180.76.51.59/aai_callback?',
        'res_text_format': 0,
        'res_type': 1,
        'source_type': 0,
        'url': voice_url,
        'timestamp': int(time.time()),
        'expired': int(time.time()) + 3600,
        'nonce': random.randint(100000, 200000)
    }
    
    sorted_keys = sorted(params_map.keys())
    key_value_list = [(key, params_map[key]) for key in sorted_keys]
    
    sig_str = 'POST' + AAI_URL + AAI_APPID + '?' + '&'.join(['%s=%s' % (key, value) for (key, value) in key_value_list])
    sig = base64.b64encode(hmac.new(AAI_SECRETKEY, sig_str, hashlib.sha1).digest())
    
    params = urllib.urlencode(key_value_list)
    base_url = AAI_URL + AAI_APPID + '?' + params
    url = 'http://' + base_url
    
    headers = {
        'Content-Type': 'application/octet-stream',
        'Authorization': sig
    }
    
    logging.info(sig_str)
    logging.info(url)
    
    response = requests.post(url, data='', headers=headers)
    return json.loads(response.content)
    

