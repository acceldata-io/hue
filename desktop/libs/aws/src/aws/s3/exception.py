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


class BotoClientError(Exception):
  """
  General Boto Client error (error accessing AWS)
  """
  def __init__(self, reason, *args):
      super(BotoClientError, self).__init__(reason, *args)
      self.reason = reason
      self.message = reason

  def __repr__(self):
      return 'BotoClientError: %s' % self.reason

  def __str__(self):
      return 'BotoClientError: %s' % self.reason

class S3ResponseError(Exception):
  """
  boto2 shaped wrapper around botocore.exceptions.ClientError.

  Exposes the same `.status`, `.reason`, `.message`, `.body` attributes that callers throughout `aws` already
  match on, so call sites do not need to be rewritten against botocore's `e.response['Error']['Code']` shape.
  """

  def __init__(self, status, reason, body=None, message=None):
      super(S3ResponseError, self).__init__('%s %s: %s' % (status, reason, message or ''))
      self.status = status
      self.reason = reason
      self.body = body or ''
      self.message = message or reason

  @classmethod
  def from_client_error(cls, client_error):
      error = client_error.response.get('Error', {}) or {}
      status = client_error.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 400)
      return cls(status=status, reason=error.get('Code', 'Unknown'), body=str(client_error), message=error.get('Message'))

