#!/bin/env python
# -*- coding:utf-8 -*-

"""
The WeChat Server.

Authors: Alex Lu (flyland_lf@hotmail.com)
"""

from flask import Flask, request, abort, render_template, jsonify
from wechatpy import parse_message, create_reply
from wechatpy.utils import check_signature
from wechatpy.exceptions import (
    InvalidSignatureException,
    InvalidAppIdException,
)
from wechatpy.crypto import WeChatCrypto
from wechatpy import WeChatClient
from wechatpy.client.api import WeChatMedia

import sys
import os
import logging
import urllib
import tempfile
import json
import argparse
import re

import cv2
import numpy as np
from aip import AipOcr
from aip import AipSpeech
from zhon import hanzi

from precogs import algorithms

import aai
            
__author__ = u'lufei@baidu.com'

WECHAT_TOKEN = os.getenv('WECHAT_TOKEN', 'wechat_token')
WECHAT_AES_KEY = os.getenv('WECHAT_AES_KEY', '')
WECHAT_APPID = os.getenv('WECHAT_APPID', '')
WECHAT_SECRET_KEY = os.getenv('WECHAT_SECRET_KEY', '')

OCR_APPID = os.getenv('OCR_APPID', '')
OCR_API_KEY = os.getenv('OCR_API_KEY', '')
OCR_SECRET_KEY = os.getenv('OCR_SECRET_KEY', '')

SPEECH_APPID = os.getenv('SPEECH_APPID', '')
SPEECH_API_KEY = os.getenv('SPEECH_API_KEY', '')
SPEECH_SECRET_KEY = os.getenv('SPEECH_SECRET_KEY', '')

app = Flask(__name__)

FLAGS = None
RANKER = None

AAI_CACHE = []

@app.route('/aai_callback', methods=['POST'])
def aai_callback():
    logging.info(request.form)
    AAI_CACHE.append(u'TencentAAI: ' + request.form['text'])
    return jsonify({ "code" : 0, "message" : u"成功" })
    

@app.route('/wechat', methods=['GET', 'POST'])
def wechat():
    try:
        signature = request.args.get('signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        encrypt_type = request.args.get('encrypt_type', 'raw')
        msg_signature = request.args.get('msg_signature', '')
        try:
            check_signature(WECHAT_TOKEN, signature, timestamp, nonce)
        except InvalidSignatureException:
            abort(403)
        if request.method == 'GET':
            echo_str = request.args.get('echostr', '')
            return echo_str
        
        # POST
        if encrypt_type != 'raw':
            crypto = WeChatCrypto(WECHAT_TOKEN, WECHAT_AES_KEY, WECHAT_APPID)
            try:
                msg = crypto.decrypt_message(
                    request.data,
                    msg_signature,
                    timestamp,
                    nonce
                )
            except (InvalidSignatureException, InvalidAppIdException):
                abort(403)
        else:
            msg = request.data
            
        # BIZ
        msg = parse_message(msg)
        if msg.type == 'image':
            problem = process_image(msg.image)
            logging.info(problem['question'])
            
            result_arthur, reverse = RANKER.do_rank_answers(problem)
            
            message = ' | '.join(['%d-%s' % (r['count'], r['ans']) for r in result_arthur])
            logging.info(message)
            reply = create_reply(message, msg)
        elif msg.type == 'voice':
            logging.info(msg)
            media_id = msg.media_id
            client = WeChatClient(WECHAT_APPID, WECHAT_SECRET_KEY)
            wechat_media = WeChatMedia(client)
            url = wechat_media.get_url(media_id)
            # Call baidu's asr
            baidu_message = process_voice(url)
            
            # Call xf's asr
            xunfei_message = process_voice_xf(url)
            
            message = '\n'.join([baidu_message, xunfei_message])

            reply = create_reply(message, msg)
            
#            # Call tencent's aai
#            aai.call(url)
        elif msg.type == 'text' and msg.content == 'qq':
            global AAI_CACHE
            reply = create_reply('\n'.join(AAI_CACHE), msg)
            AAI_CACHE = []
        else:
            reply = create_reply('Sorry, can not handle this for now', msg)
        
        

        # Render
        if encrypt_type != 'raw':
            return crypto.encrypt_message(reply.render(), nonce, timestamp)
        else:
            return reply.render()
    
    except Exception as e:
        import traceback
        traceback.print_exc()


def process_voice(voice_url):
    logging.info("voice_url:%s" % voice_url)
    voice = bytearray(urllib.urlopen(voice_url).read())
    asr_client = AipSpeech(SPEECH_APPID, SPEECH_API_KEY, SPEECH_SECRET_KEY)
    response_zh = asr_client.asr(voice, 'amr', 8000)
    response_en = asr_client.asr(voice, 'amr', 8000, { 'lan': 'en' })
    return 'BaiduASR: ' + '\n'.join(response_zh['result'])  + '\n' + 'BaiduASR_en: ' +'\n'.join(response_en['result'])
    
def process_voice_xf(voice_url):
    import xfasr
    response = xfasr.call(voice_url)
    logging.info(response)
    return 'Xunfei: ' + response[u'data'][u'result']

    
def process_image(image_url):
    logging.info("image_url:%s" % (image_url))
    
    img = cv2.imdecode(np.asarray(bytearray(urllib.urlopen(image_url).read()), dtype='uint8'), cv2.IMREAD_GRAYSCALE)
    ret, img =cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)
    
    ocr_client = AipOcr(OCR_APPID, OCR_API_KEY, OCR_SECRET_KEY)
    import time
    with open('img/%f.jpg' % time.time(), 'w') as abc:
        abc.write(cv2.imencode('.jpg', img)[1].tostring())
    result = ocr_client.general(cv2.imencode('.jpg', img)[1].tostring(), { 'probability': 'true' })
    
    print >> sys.stderr, result
    words_result = filter(lambda x: x['location']['top'] > 300 and x['location']['top'] < 1400 and x['location']['height'] > 40, result['words_result'])
    
#    print >> sys.stderr, words_result

    question = ''.join([word['words'] for word in words_result[:-3]]).split('.')[-1]
    answers = [word['words'].split('.')[-1] for word in words_result[-3:]]
    
    problem = {
        'question': question.encode('utf-8'),
        'ans_1': re.sub(ur"[%s]" % hanzi.punctuation, "", answers[0]).encode('utf-8'),
        'ans_2': re.sub(ur"[%s]" % hanzi.punctuation, "", answers[1]).encode('utf-8'),
        'ans_3': re.sub(ur"[%s]" % hanzi.punctuation, "", answers[2]).encode('utf-8')
    }
    
    return problem    
    

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,  
                        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',  
                        datefmt='%a, %d %b %Y %H:%M:%S')
    parser = argparse.ArgumentParser()
    parser.register("type", "bool", lambda v: v.lower() == "true")
    parser.add_argument("--precog", type=str, default="Dash2",
                        help="Agatha | Arthur | Dash | Dash2 for different precogs(SearchEngine for now.).")
    parser.add_argument("--debug", type="bool", default=False,
                        help="Whether to enable debug mode.")
    FLAGS, unparsed = parser.parse_known_args()

    RANKER = algorithms.BasicRanker(FLAGS)
    app.run(host="0.0.0.0", port=80, debug=True)
