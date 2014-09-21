#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json
import random
import hashlib

import requests
from heartbeat import Challenge, Heartbeat

from .utils import urlify
from .exc import DownstreamError


class DownstreamClient(object):
    def __init__(self, server_url):
        self.server = server_url.strip('/')
        self.challenges = []
        self.heartbeat = None

    def connect(self, url):
        raise NotImplementedError

    def store_path(self, path):
        raise NotImplementedError

    def get_chunk(self, hash):
        raise NotImplementedError

    def challenge(self, hash, challenge):
        raise NotImplementedError

    def answer(self, hash, hash_answer):
        raise NotImplementedError

    def _enc_fname(self, filename):
        return urlify(os.path.split(filename)[1])

    def get_challenges(self, filename):
        enc_fname = urlify(os.path.split(filename)[1])
        url = '%s/api/downstream/challenges/%s' % (self.server, enc_fname)
        resp = requests.get(url)
        try:
            resp.raise_for_status()
        except Exception as e:
            raise DownstreamError("Error connecting to downstream"
                                  "-node: %s" % e.message)

        try:
            response_json = resp.json()
        except ValueError:
            raise DownstreamError('Invalid response from Downstream node.')
        for challenge in response_json['challenges']:
            chal = Challenge(
                int(challenge.get('block')), challenge.get('seed')
            )
            self.challenges.append(chal)

    def answer_challenge(self, filename):
        try:
            assert os.path.isfile(filename)
        except AssertionError:
            raise DownstreamError('%s is not a valid file' % filename)

        enc_fname = self._enc_fname(filename)
        self.heartbeat = Heartbeat(
            filename, hashlib.sha256(os.urandom(32)).hexdigest()
        )
        self.heartbeat.challenges = self.challenges
        select_chal = self.heartbeat.random_challenge()
        answer = self.heartbeat.meet_challenge(select_chal)
        data = {
            'block': select_chal.block,
            'seed': select_chal.seed,
            'response': answer
        }
        headers = {
            'Content-Type': 'application/json'
        }
        url = ('%s/api/downstream/challenges/answer/%s'
               % (self.server, enc_fname))
        r = requests.post(url, data=json.dumps(data), headers=headers)

        try:
            response_json = r.json()
        except ValueError:
            response_json = {}

        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            raise DownstreamError('Error reponse from Downstream node: %s %s'
                                  % (r.status_code, response_json.get('msg')))
        return response_json

    def random_challenge(self):
        return random.choice(self.challenges)