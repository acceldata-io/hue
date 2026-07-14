#!/usr/bin/env python
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

from aws.s3.s3connection import S3Connection

from desktop.conf import RAZ
from desktop.lib.raz.clients import GSRazClient

LOG = logging.getLogger()

# GCS' XML API is S3-compatible, so it is reachable through the exact same boto3-backed S3Connection used for AWS
# S3 (see aws.s3.s3connection), just pointed at Google's endpoint with virtual-hosted-style addressing (Google's own
# default for the XML API, mirroring the SubdomainCallingFormat used by the boto2 GSConnection used to default to).
GCS_XML_API_HOST = 'storage.googleapis.com'


class RazGSConnection(S3Connection):
  """
  TODO(boto3-migration): RAZ presigned-URL injection is not implemented yet, this is a structural stub only.

  boto2 could intercept a request right before sending it and swap in a RAZ presigned URL; botocore has no
  equivalent hook exposed by its client methods, so this needs a real design pass later (likely via botocore's
  `choose-signer`/`before-send` events, same as aws.s3.s3connection.RazS3Connection). Until then, RAZ-enabled GCS
  access will not work end-to-end: requests go out unsigned and get rejected.
  """

  def __init__(self, username, **kwargs):
    self.username = username

    kwargs.setdefault('anon', RAZ.IS_ENABLED.get())
    kwargs.setdefault('host', GCS_XML_API_HOST)
    kwargs.setdefault('addressing_style', 'virtual')

    super(RazGSConnection, self).__init__(**kwargs)

  def get_signed_url(self, action='GET', url=None, headers=None, data=None):
    raz_client = GSRazClient(username=self.username)
    return raz_client.get_url(action, url, headers, data)
