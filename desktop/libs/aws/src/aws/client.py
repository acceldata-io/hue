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

from builtins import str, object
import logging

from aws import conf as aws_conf
from aws.s3.s3connection import RazS3Connection, S3Connection
from aws.s3.s3fs import S3FileSystem, S3FileSystemException

from desktop.lib.idbroker import conf as conf_idbroker
from desktop.lib.idbroker.client import IDBroker

from hadoop.core_site import get_raz_s3_default_bucket

LOG = logging.getLogger()


HTTP_SOCKET_TIMEOUT_S = 60

# Maps the legacy boto2 hue.ini `calling_format` class paths to the boto3/botocore `addressing_style` equivalent.
CALLING_FORMAT_TO_ADDRESSING_STYLE = {
  'boto.s3.connection.OrdinaryCallingFormat': 'path',
  'boto.s3.connection.ProtocolIndependentOrdinaryCallingFormat': 'path',
  'boto.s3.connection.SubdomainCallingFormat': 'virtual',
  'boto.s3.connection.VHostCallingFormat': 'virtual',
}


def get_credential_provider(identifier, user):
  client_conf = aws_conf.AWS_ACCOUNTS[identifier] if identifier in aws_conf.AWS_ACCOUNTS else None
  return CredentialProviderIDBroker(IDBroker.from_core_site('s3a', user)) if conf_idbroker.is_idbroker_enabled('s3a') \
      else CredentialProviderConf(client_conf)


def _make_client(identifier, user):
  client_conf = aws_conf.AWS_ACCOUNTS[identifier] if identifier in aws_conf.AWS_ACCOUNTS else None

  if aws_conf.is_raz_s3():
    host = client_conf.HOST.get()
    s3_client = RazS3Connection(username=user, host=host)  # Note: Remaining AWS configuration is fully skipped
    s3_client_expiration = None
  else:
    s3_client_builder = Client.from_config(client_conf, get_credential_provider(identifier, user))
    s3_client = s3_client_builder.get_s3_connection()
    s3_client_expiration = s3_client_builder.expiration

  return S3FileSystem(s3_client, s3_client_expiration)


class CredentialProviderConf(object):
  def __init__(self, conf):
    self._conf = conf

  def validate(self):
    credentials = self.get_credentials()
    if None in (credentials.get('AccessKeyId'), credentials.get('SecretAccessKey')) and not credentials.get('AllowEnvironmentCredentials') \
        and not aws_conf.has_iam_metadata():
      raise ValueError('Can\'t create AWS client, credential is not configured')
    return True

  def get_credentials(self):
    if self._conf:
      return {
         'AccessKeyId': self._conf.ACCESS_KEY_ID.get(),
         'SecretAccessKey': self._conf.SECRET_ACCESS_KEY.get(),
         'SessionToken': self._conf.SECURITY_TOKEN.get(),
         'AllowEnvironmentCredentials': self._conf.ALLOW_ENVIRONMENT_CREDENTIALS.get()
      }
    else:
      return {
        'AccessKeyId': self._conf.ACCESS_KEY_ID.get(),
        'SecretAccessKey': self._conf.get_default_secret_key(),
        'SessionToken': self._conf.get_default_session_token(),
        'AllowEnvironmentCredentials': True
      }


class CredentialProviderIDBroker(object):
  def __init__(self, idbroker):
    self.idbroker = idbroker
    self.credentials = None

  def validate(self):
    return True # Already been validated in config

  def get_credentials(self):
    return self.idbroker.get_cab().get('Credentials')


class Client(object):
  def __init__(self, aws_access_key_id=None, aws_secret_access_key=None, aws_security_token=None, region=None,
               timeout=HTTP_SOCKET_TIMEOUT_S, host=None, proxy_address=None, proxy_port=None, proxy_user=None,
               proxy_pass=None, calling_format=None, is_secure=True, expiration=None):
    self._access_key_id = aws_access_key_id
    self._secret_access_key = aws_secret_access_key
    self._security_token = aws_security_token
    self._region = region.lower() if region else region
    self._timeout = timeout
    self._host = host
    self._proxy_address = proxy_address
    self._proxy_port = proxy_port
    self._proxy_user = proxy_user
    self._proxy_pass = proxy_pass
    self._calling_format = aws_conf.DEFAULT_CALLING_FORMAT if calling_format is None else calling_format
    self._is_secure = is_secure
    self.expiration = expiration

  @classmethod
  def from_config(cls, conf, credential_provider):
    credential_provider.validate()
    credentials = credential_provider.get_credentials()

    if conf:
      return cls(
        aws_access_key_id=credentials.get('AccessKeyId'),
        aws_secret_access_key=credentials.get('SecretAccessKey'),
        aws_security_token=credentials.get('SessionToken'),
        region=aws_conf.get_region(conf=conf),
        host=conf.HOST.get(),
        proxy_address=conf.PROXY_ADDRESS.get(),
        proxy_port=conf.PROXY_PORT.get(),
        proxy_user=conf.PROXY_USER.get(),
        proxy_pass=conf.PROXY_PASS.get(),
        calling_format=conf.CALLING_FORMAT.get(),
        is_secure=conf.IS_SECURE.get(),
        expiration=credentials.get('Expiration')
      )
    else:
      return cls(
        aws_access_key_id=credentials.get('AccessKeyId'),
        aws_secret_access_key=credentials.get('SecretAccessKey'),
        aws_security_token=credentials.get('SessionToken'),
        expiration=credentials.get('Expiration'),
        region=aws_conf.get_region()
      )

  def get_s3_connection(self):
    """Builds the boto3-backed aws.s3.s3connection.S3Connection used throughout the aws.s3 package."""
    kwargs = {
      'aws_access_key_id': self._access_key_id,
      'aws_secret_access_key': self._secret_access_key,
      'security_token': self._security_token,
      'is_secure': self._is_secure,
      'addressing_style': CALLING_FORMAT_TO_ADDRESSING_STYLE.get(self._calling_format, 'path'),
      'timeout': self._timeout,
    }

    # Add proxy if configured
    if self._proxy_address is not None:
      # botocore/urllib3 require a scheme on the proxy URL (e.g. "http://host:port"); self._proxy_address is
      # usually just a bare hostname, so make sure one is always present instead of only preserving an existing one.
      scheme = 'http'
      netloc = self._proxy_address
      if '://' in netloc:
        scheme, _, netloc = netloc.partition('://')

      if self._proxy_port is not None:
        netloc = '%s:%s' % (netloc, self._proxy_port)
      if self._proxy_user is not None:
        credentials = self._proxy_user if self._proxy_pass is None else '%s:%s' % (self._proxy_user, self._proxy_pass)
        netloc = '%s@%s' % (credentials, netloc)

      proxy_url = '%s://%s' % (scheme, netloc)
      kwargs['proxies'] = {'http': proxy_url, 'https': proxy_url}

    # self._region is already resolved (falls back to aws_conf.AWS_ACCOUNT_REGION_DEFAULT) by aws_conf.get_region()
    # in Client.from_config(). Always pass it through so SigV4 signs against the right region even when a custom
    # host is set below -- otherwise S3Connection would silently sign against its own default region instead.
    if self._region:
      kwargs['region_name'] = self._region

    # Attempt to create S3 connection based on configured credentials and host or region first, then fallback to IAM
    try:
      if self._host is not None:
        kwargs['host'] = self._host
        connection = S3Connection(**kwargs)
      elif self._region:
        connection = S3Connection(**kwargs)
      else:
        kwargs['host'] = 's3.amazonaws.com'
        connection = S3Connection(**kwargs)
    except Exception as e:
      LOG.exception(e)
      raise S3FileSystemException('Failed to construct S3 Connection, check configurations for aws.')

    if connection is None:
      # If no connection, attempt to fallback to IAM instance metadata / the default credential chain
      try:
        connection = S3Connection()
      except Exception as e:
        LOG.exception(e)
        connection = None

      if connection is None:
        raise S3FileSystemException('Can not construct S3 Connection for region %s' % self._region)

    return connection
