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

import logging
from functools import wraps

import boto3
from botocore import UNSIGNED
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from aws import conf as aws_conf
from aws.s3.exception import BotoClientError, S3ResponseError
from desktop.conf import RAZ
from desktop.lib.raz.clients import S3RazClient

LOG = logging.getLogger()

def translate_boto3_error(fn):
  """
  Decorator for the new boto3-backed methods we're about to add to this file (Key/Bucket/S3Connection).

  Wraps a function that talks to boto3, and converts botocore's own exceptions into the boto2-shaped
  S3ResponseError/BotoClientError (aws.s3.exception) that the rest of `aws` already catches -- so callers like
  s3fs.py's `except S3ResponseError as e: if e.status == 404` keep working without any changes.
  """
  @wraps(fn)
  def wrapped(*args, **kwargs):
    try:
      return fn(*args, **kwargs)
    except ClientError as e:
      raise S3ResponseError.from_client_error(e)
    except BotoCoreError as e:
      raise BotoClientError(str(e))
  return wrapped

class Location(object):
  """Excluded other location constants since only DEFAULT is being used."""
  DEFAULT = ''  # US Classic Region

class Prefix(object):
  def __init__(self, bucket=None, name=None):
    self.bucket = bucket
    self.name = name

class Key(object):
  """boto2 shaped boto.s3.key.Key replacement, backed by a boto3 Object."""

  def __init__(self, bucket, name):
    self.bucket = bucket
    self.name = name
    self.size = None
    self.last_modified = None
    self._object = bucket._connection._resource.Object(bucket.name, name)

  @translate_boto3_error
  def delete(self):
    self._object.delete()
    return self

  @translate_boto3_error
  def exists(self):
    try:
      self._load()
      return True
    except S3ResponseError as e:
      if e.status == 404:
        return False
      raise

  @translate_boto3_error
  def copy(self, dst_bucket, dst_name):
    copy_source = {'Bucket': self.bucket.name, 'Key': self.name}
    dst_bucket._boto_bucket.copy(copy_source, dst_name)
    return dst_bucket.get_key(dst_name, validate=False)

  @translate_boto3_error
  def set_contents_from_string(self, data, replace=True):
    if isinstance(data, str):
      data = data.encode('utf-8')
    self._object.put(Body=data)

  @translate_boto3_error
  def set_contents_from_file(self, fp):
    self._object.upload_fileobj(fp)

  @translate_boto3_error
  def get_contents_as_string(self):
    return self._object.get()['Body'].read()

  def generate_url(self, expires_in):
    return self.bucket._connection._client.generate_presigned_url(
      'get_object', Params={'Bucket': self.bucket.name, 'Key': self.name}, ExpiresIn=expires_in)

  @translate_boto3_error
  def _load(self):
    self._object.load()
    self.size = self._object.content_length
    self.last_modified = self._object.last_modified

  @classmethod
  def from_s3_object(cls, bucket, obj):
    """`obj` is a dict entry from list_objects_v2's `Contents`."""
    key = cls(bucket, obj['Key'])
    key.size = obj.get('Size')
    key.last_modified = obj.get('LastModified')
    return key

class MultipartUpload(object):
  """boto2 shaped multipart upload handle, backed by botocore's low-level multipart upload APIs."""

  def __init__(self, bucket, key_name):
    self.bucket = bucket
    self.key_name = key_name
    self._client = bucket._connection._client
    self._parts = []
    self._upload_id = None

  @translate_boto3_error
  def _ensure_started(self):
    if self._upload_id is None:
      self._upload_id = self._client.create_multipart_upload(Bucket=self.bucket.name, Key=self.key_name)['UploadId']

  @translate_boto3_error
  def upload_part_from_file(self, fp, part_num):
    self._ensure_started()
    data = fp.read()
    resp = self._client.upload_part(
      Bucket=self.bucket.name, Key=self.key_name, PartNumber=part_num, UploadId=self._upload_id, Body=data)
    self._parts.append({'ETag': resp['ETag'], 'PartNumber': part_num})

  @translate_boto3_error
  def complete_upload(self):
    self._ensure_started()
    parts = sorted(self._parts, key=lambda p: p['PartNumber'])
    self._client.complete_multipart_upload(
      Bucket=self.bucket.name, Key=self.key_name, UploadId=self._upload_id, MultipartUpload={'Parts': parts})

  @translate_boto3_error
  def cancel_upload(self):
    if self._upload_id is not None:
      self._client.abort_multipart_upload(Bucket=self.bucket.name, Key=self.key_name, UploadId=self._upload_id)

class _HeaderResponse(object):
  """Minimal stand-in for the httplib response boto2's make_request() returned."""

  def __init__(self, headers):
    self._headers = headers or {}

  def getheader(self, name, default=None):
    return self._headers.get(name, default)

class _DeleteError(object):
  def __init__(self, key, message):
    self.key = key
    self.message = message

class _DeleteResult(object):
  def __init__(self):
    self.errors = []

class Bucket(object):
  """boto2 shaped boto.s3.bucket.Bucket replacement, backed by a boto3 Bucket resource."""

  def __init__(self, connection, name):
    self._connection = connection
    self.name = name
    self._boto_bucket = connection._resource.Bucket(name)

  @translate_boto3_error
  def get_key(self, key_name, validate=True, headers=None):
    key = Key(self, key_name)
    if validate:
      try:
        key._load()
      except S3ResponseError as e:
        if e.status == 404:
          return None
        raise
    return key

  @translate_boto3_error
  def get_all_keys(self, prefix='', max_keys=None, headers=None):
    kwargs = {'Bucket': self.name, 'Prefix': prefix}
    if max_keys:
      kwargs['MaxKeys'] = max_keys
    resp = self._connection._client.list_objects_v2(**kwargs)
    return [Key.from_s3_object(self, obj) for obj in resp.get('Contents', [])]

  @translate_boto3_error
  def delete(self):
    self._boto_bucket.delete()

  @translate_boto3_error
  def delete_keys(self, keys):
    objects = [{'Key': key.name if isinstance(key, Key) else key} for key in keys]
    result = _DeleteResult()
    for i in range(0, len(objects), 1000):  # delete_objects allows at most 1000 keys per call
      batch = objects[i:i + 1000]
      resp = self._connection._client.delete_objects(Bucket=self.name, Delete={'Objects': batch, 'Quiet': True})
      for error in resp.get('Errors', []):
        result.errors.append(_DeleteError(error.get('Key'), error.get('Message')))
    return result

  def new_key(self, key_name):
    return Key(self, key_name)

  @translate_boto3_error
  def list(self, prefix='', delimiter='', headers=None):
    paginator = self._connection._client.get_paginator('list_objects_v2')
    kwargs = {'Bucket': self.name, 'Prefix': prefix}
    if delimiter:
      kwargs['Delimiter'] = delimiter

    results = []
    for page in paginator.paginate(**kwargs):
      for common_prefix in page.get('CommonPrefixes', []):
        results.append(Prefix(self, common_prefix['Prefix']))
      for obj in page.get('Contents', []):
        results.append(Key.from_s3_object(self, obj))
    return results

  def initiate_multipart_upload(self, key_name, headers=None):
    return MultipartUpload(self, key_name)

class S3Connection(object):
  """boto2 shaped boto.s3._connection.S3Connection replacement, backed by a boto3 session/client/resource."""

  def __init__(self, aws_access_key_id=None, aws_secret_access_key=None, security_token=None,
               is_secure=True, host=None, region_name=None, addressing_style='path',
               proxies=None, timeout=60, anon=False):
    self.anon = anon

    botocore_config = Config(
      signature_version=UNSIGNED if anon else 's3v4',
      s3={'addressing_style': addressing_style},
      proxies=proxies or None,
      connect_timeout=timeout,
      read_timeout=timeout,
    )

    endpoint_url = None
    if host:
      endpoint_url = '%s://%s' % ('https' if is_secure else 'http', host)

    session_kwargs = {'region_name': region_name or aws_conf.AWS_ACCOUNT_REGION_DEFAULT}
    if not anon:
      session_kwargs['aws_access_key_id'] = aws_access_key_id
      session_kwargs['aws_secret_access_key'] = aws_secret_access_key
      if security_token:
        session_kwargs['aws_session_token'] = security_token

    self._session = boto3.session.Session(**session_kwargs)
    self._client = self._session.client('s3', endpoint_url=endpoint_url, config=botocore_config)
    self._resource = self._session.resource('s3', endpoint_url=endpoint_url, config=botocore_config)

  @translate_boto3_error
  def get_bucket(self, name, headers=None, validate=True):
    if validate:
      self._client.head_bucket(Bucket=name)
    return Bucket(self, name)

  @translate_boto3_error
  def get_all_buckets(self, headers=None):
    return [Bucket(self, b['Name']) for b in self._client.list_buckets().get('Buckets', [])]

  @translate_boto3_error
  def create_bucket(self, name, location=None, headers=None):
    kwargs = {'Bucket': name}
    if location:
      kwargs['CreateBucketConfiguration'] = {'LocationConstraint': location}
    self._client.create_bucket(**kwargs)
    return Bucket(self, name)

  @translate_boto3_error
  def delete_bucket(self, name, headers=None):
    self._client.delete_bucket(Bucket=name)

  @translate_boto3_error
  def make_request(self, method, bucket='', key='', headers=None, **kwargs):
    if method == 'HEAD' and not key:
      resp = self._client.head_bucket(Bucket=bucket)
      return _HeaderResponse(resp.get('ResponseMetadata', {}).get('HTTPHeaders', {}))
    raise NotImplementedError('S3Connection.make_request() only supports HEAD bucket requests in the boto3 shim')

  @translate_boto3_error
  def get_canonical_user_id(self):
    return self._client.list_buckets().get('Owner', {}).get('ID')

class RazS3Connection(S3Connection):
  """
  TODO(boto3-migration): RAZ presigned-URL injection is not implemented yet, this is a structural stub only.

  boto2 could intercept a request right before sending it and swap in a RAZ presigned URL; botocore has no
  equivalent hook exposed by its client methods, so this needs a real design pass later (likely via botocore's
  `choose-signer`/`before-send` events). Until then, RAZ-enabled S3 access will not work end-to-end: requests go
  out unsigned and get rejected with 403.
  """

  def __init__(self, username, host=None, **kwargs):
    self.username = username

    # No auth handler is used with RAZ, calls are meant to be made anonymously and rely on presigned URLs instead.
    # See the TODO above: presigned URL injection itself is not wired up yet.
    kwargs.setdefault('anon', RAZ.IS_ENABLED.get())

    super(RazS3Connection, self).__init__(host=host, **kwargs)

  def get_signed_url(self, action='GET', url=None, headers=None, data=None):
    raz_client = S3RazClient(username=self.username)
    return raz_client.get_url(action, url, headers, data)
