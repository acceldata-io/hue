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
"""
boto2 -> boto3 migration note
==============================
Under boto2, non-RAZ GCS auth went through `gcs_oauth2_boto_plugin` + a custom `boto.auth_handler.AuthHandler`
(`OAuth2JsonServiceAccountClientAuth` below, removed) that turned a GCS OAuth2 service-account JSON key into a
Bearer-token `Authorization` header on every request. That relied on boto2's pluggable per-connection AuthHandler
architecture (`boto.auth_handler.AuthHandler` subclasses registered via `provider.name`/`capability`).

botocore has no equivalent extension point: its request signing is hard-wired to the AWS SigV4/SigV2 family and
expects an access-key-id/secret-access-key pair, not an OAuth2 bearer token. There is no supported way to plug a
Bearer-token AuthHandler into a boto3 client the way boto2 allowed.

The supported way to keep talking to GCS's S3-compatible XML API from boto3 is GCS's own HMAC keys ("Interoperable
Storage Access Keys", see https://cloud.google.com/storage/docs/authentication/hmackeys) -- these are AWS-SigV4
compatible access-key/secret pairs, e.g. generated with `gsutil hmac create <service-account-email>` (so an existing
service account can still be used, just with different credential material). `desktop.conf.GC_ACCOUNTS` now has
`access_key_id`/`secret_access_key` fields for this; `json_credentials` is kept only for backward-compatible config
parsing and is otherwise unused.

If IDBroker is fronting GCS credentials, it also needs to be updated server-side to vend `AccessKeyId`/
`SecretAccessKey` instead of `JsonCredentials` -- that is outside of this client's scope.
"""
import logging

from aws.s3.s3connection import S3Connection

from desktop import conf
from desktop.lib.idbroker import conf as conf_idbroker
from desktop.lib.idbroker.client import IDBroker
from desktop.lib.fs.gc.gs import GSFileSystem, GSFileSystemException
from desktop.lib.fs.gc.gsconnection import GCS_XML_API_HOST, RazGSConnection

LOG = logging.getLogger()


def get_credential_provider(config, user):
  return CredentialProviderIDBroker(IDBroker.from_core_site('gs', user)) if conf_idbroker.is_idbroker_enabled('gs') else \
      CredentialProviderConf(config)


def _make_client(identifier, user):
  if conf.is_raz_gs():
    gs_client_connection = RazGSConnection(username=user)  # Note: Remaining GS configuration is fully skipped
    gs_client_expiration = None
  else:
    config = conf.GC_ACCOUNTS[identifier] if identifier in list(conf.GC_ACCOUNTS.keys()) else None
    gs_client_builder = Client.from_config(config, get_credential_provider(config, user))

    gs_client_connection = gs_client_builder.get_gs_connection()
    gs_client_expiration = gs_client_builder.expiration

  return GSFileSystem(
    gs_client_connection,
    gs_client_expiration,
  )  # It would be nice if the connection was lazy loaded


class Client(object):

  def __init__(self, access_key_id=None, secret_access_key=None, region=None, expiration=None):
    self.access_key_id = access_key_id
    self.secret_access_key = secret_access_key
    self.region = region
    self.expiration = expiration

  @classmethod
  def from_config(cls, config, credential_provider):
    credentials = credential_provider.get_credentials()
    return Client(
      access_key_id=credentials.get('AccessKeyId'),
      secret_access_key=credentials.get('SecretAccessKey'),
      region=config.REGION.get() if config else None,
      expiration=credentials.get('Expiration'),
    )

  def get_gs_connection(self):
    """GCS is talked to as an S3-compatible endpoint, see the module docstring for why this needs HMAC credentials."""
    if not self.access_key_id or not self.secret_access_key:
      raise GSFileSystemException(
        'Failed to construct a GCS connection: no access_key_id/secret_access_key (GCS HMAC key) configured. '
        'See the desktop.lib.fs.gc.client module docstring for why OAuth2 JSON service-account credentials can no '
        'longer be used here.'
      )

    return S3Connection(
      aws_access_key_id=self.access_key_id,
      aws_secret_access_key=self.secret_access_key,
      region_name=self.region,
      host=GCS_XML_API_HOST,
      addressing_style='virtual',
    )


class CredentialProviderConf(object):

  def __init__(self, conf):
    self._conf = conf

  def validate(self):
    credentials = self.get_credentials()
    if not (credentials.get('AccessKeyId') and credentials.get('SecretAccessKey')):
      raise ValueError('Can\'t create GS client, credential is not configured')
    return True

  def get_credentials(self):
    if self._conf:
      return {
        'AccessKeyId': self._conf.ACCESS_KEY_ID.get(),
        'SecretAccessKey': self._conf.SECRET_ACCESS_KEY.get(),
      }
    else:
      return {
        'AccessKeyId': None,
        'SecretAccessKey': None,
      }


class CredentialProviderIDBroker(object):

  def __init__(self, idbroker):
    self.idbroker = idbroker
    self.credentials = None

  def validate(self):
    return True # Already been validated in config

  def get_credentials(self):
    return self.idbroker.get_cab().get('Credentials')
