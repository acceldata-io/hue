# Licensed to Cloudera, Inc. under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  Cloudera, Inc. licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import

import errno
import os

from aws.conf import get_key_expiry
from aws.s3 import translate_s3_error
from aws.s3.s3connection import translate_boto3_error


DEFAULT_READ_SIZE = 1024 * 1024  # 1MB


def open(key, mode='r'):
  if mode == 'r':
    return _ReadableS3File(key)
  else:
    raise IOError(errno.EINVAL, 'Unavailable mode "%s"' % mode)


class _ReadableS3File(object):
  """
  File-like, seekable reader over an S3 object.

  Replaces boto2's boto.s3.keyfile.KeyFile, which streamed the Key's HTTP response body directly and re-opened it
  with a Range header whenever seek() moved the read position. botocore's StreamingBody (returned by get_object())
  has no seek support of its own, so the same re-open-on-seek approach is reproduced here.
  """

  def __init__(self, key):
    self._key = key.bucket.get_key(key.name, validate=False)
    self._pos = 0
    self._size = None
    self._body = None

  def getkey(self):
    return self._key

  def read_url(self):
    return self.getkey().generate_url(get_key_expiry())

  @translate_boto3_error
  def _open_stream(self):
    if self._body is None:
      resp = self._key._object.get(Range='bytes=%d-' % self._pos)
      self._body = resp['Body']
      content_range = resp.get('ContentRange', '')  # e.g. "bytes 0-9/10"
      if '/' in content_range:
        self._size = int(content_range.rsplit('/', 1)[1])
      elif self._size is None:
        self._size = resp.get('ContentLength')

  @translate_s3_error
  def read(self, length=DEFAULT_READ_SIZE):
    self._open_stream()
    data = self._body.read(length)
    self._pos += len(data)
    return data

  def seek(self, offset, whence=os.SEEK_SET):
    if whence == os.SEEK_SET:
      new_pos = offset
    elif whence == os.SEEK_CUR:
      new_pos = self._pos + offset
    elif whence == os.SEEK_END:
      if self._size is None:
        self._key._load()
        self._size = self._key.size
      new_pos = self._size + offset
    else:
      raise IOError(errno.EINVAL, 'Unsupported whence value "%s"' % whence)

    if new_pos < 0:
      raise IOError(errno.EINVAL, 'Negative seek position "%s"' % new_pos)

    if new_pos != self._pos:
      if self._body is not None:
        self._body.close()
      self._pos = new_pos
      self._body = None  # Force a re-open with an updated Range on the next read()
    return self._pos

  def tell(self):
    return self._pos

  def close(self):
    if self._body is not None:
      self._body.close()
      self._body = None
