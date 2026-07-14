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
from unittest.mock import patch

from aws.s3.s3connection import RazS3Connection
from desktop.conf import RAZ

LOG = logging.getLogger()


# NOTE: RazS3Connection is currently a structural stub as part of the boto3 migration, it no longer injects RAZ
# presigned URLs into outgoing requests the way its boto2 predecessor did (see the TODO on the class itself).
# These tests only cover what the stub does today: constructing an anonymous boto3-backed connection and
# delegating get_signed_url() to S3RazClient.
class TestRazS3Connection():

  def setup_method(self):
    self.finish = [
      RAZ.IS_ENABLED.set_for_testing(True)
    ]

  def teardown_method(self):
    for f in self.finish:
      f()

  def test_is_anonymous_when_raz_enabled(self):
    client = RazS3Connection(username='test', host='s3-us-west-1.amazonaws.com')

    assert client.anon is True
    assert client.username == 'test'

  def test_get_signed_url_delegates_to_raz_client(self):
    with patch('aws.s3.s3connection.S3RazClient') as S3RazClient:
      S3RazClient.return_value.get_url.return_value = {
        'AWSAccessKeyId': 'AKIA23E77ZX2HVY76YGL',
        'Signature': '3lhK%2BwtQ9Q2u5VDIqb4MEpoY3X4%3D',
        'Expires': '1617207304'
      }

      client = RazS3Connection(username='test', host='s3-us-west-1.amazonaws.com')
      result = client.get_signed_url(action='GET', url='https://s3-us-west-1.amazonaws.com/', headers={}, data='')

      S3RazClient.assert_called_once_with(username='test')
      S3RazClient.return_value.get_url.assert_called_once_with('GET', 'https://s3-us-west-1.amazonaws.com/', {}, '')
      assert result == S3RazClient.return_value.get_url.return_value
