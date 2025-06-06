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

import math
import time
import urllib
import logging
import posixpath
from builtins import object

from django.utils.encoding import iri_to_uri
from django.utils.http import urlencode

from desktop import conf
from desktop.lib.apputil import INFO_LEVEL_CALL_DURATION_MS, WARN_LEVEL_CALL_DURATION_MS
from desktop.lib.i18n import smart_str

LOG = logging.getLogger()


class Resource(object):
  """
  Encapsulates a resource, and provides actions to invoke on it.
  """
  def __init__(self, client, relpath="", urlencode=True):
    """
    @param client: A Client object.
    @param relpath: The relative path of the resource.
    @param urlencode: percent encode paths.
    """
    self._client = client
    self._path = relpath.strip('/')
    self._urlencode = urlencode

  @property
  def base_url(self):
    return self._client.base_url

  def _join_uri(self, relpath):
    if relpath is None:
      return self._path
    return self._path + posixpath.normpath('/' + relpath)

  def _format_response(self, resp):
    """
    Decide whether the body should be a json dict or string
    """

    if resp.headers.get('location') and resp.headers.get('location').startswith('http://localhost:8080/'):
      return resp.headers.get('location').split('sessions/')[1]

    if len(resp.content) != 0 and resp.headers.get('content-type') and 'application/json' in resp.headers.get('content-type'):
      try:
        return resp.json()
      except Exception as ex:
        self._client.logger.exception('JSON decode error: %s' % resp.content)
        raise ex
    else:
      return resp.content

  def invoke(self, method, relpath=None, params=None, data=None, headers=None, files=None, allow_redirects=False, clear_cookies=False,
      log_response=True
    ):
    resp = self._invoke(
        method=method,
        relpath=relpath,
        params=params,
        data=data,
        headers=headers,
        files=files,
        allow_redirects=allow_redirects,
        clear_cookies=clear_cookies,
        log_response=log_response
    )

    return self._format_response(resp)

  def _invoke(self, method, relpath=None, params=None, data=None, headers=None, files=None, allow_redirects=False, clear_cookies=False,
      log_response=True
    ):
    """
    Invoke an API method.
    Print trace even when there is an exception.
    @return: Raw body or JSON dictionary (if response content type is JSON).
    """
    path = self._join_uri(relpath)
    start_time = time.time()
    resp = None

    try:
      resp = self._client.execute(
          method,
          path,
          params=params,
          data=data,
          headers=headers,
          files=files,
          allow_redirects=allow_redirects,
          urlencode=self._urlencode,
          clear_cookies=clear_cookies
      )
    finally:
      # Output duration without content
      log_length = conf.REST_RESPONSE_SIZE.get() != -1 and conf.REST_RESPONSE_SIZE.get() if log_response else 0
      duration = time.time() - start_time
      try:
        req_data = smart_str(data, errors='replace')
        resp_content = smart_str(resp.content, errors='replace') if resp and resp.content else ''
        message = u'%s %s %s%s%s %s%s returned in %dms %s %s %s%s' % (
          method,
          type(self._client._session.auth) if self._client._session and self._client._session.auth else None,
          self._client._base_url,
          smart_str(path, errors='replace'),
          iri_to_uri('?' + urlencode(params)) if params else '',
          req_data[:log_length] if data else '',
          log_length and len(req_data) > log_length and '...' or '' if data else '',
          (duration * 1000),
          resp.status_code if resp else 0,
          len(resp_content) if resp else 0,
          resp_content[:log_length] if resp else '',
          log_length and len(resp_content) > log_length and '...' or '' if resp else ''
        )
      except Exception:
        short_call_name = '%s %s' % (method, self._client._base_url)
        LOG.exception('Error logging return call %s' % short_call_name)
        message = '%s returned in %dms' % (short_call_name, duration)
      self._client.logger.disabled = 0

      log_if_slow_call(duration=duration, message=message, logger=self._client.logger)

    return resp

  def get(self, relpath=None, params=None, headers=None, clear_cookies=False):
    """
    Invoke the GET method on a resource.
    @param relpath: Optional. A relative path to this resource's path.
    @param params: Key-value data.
    @param clear_cookies: Optional. A flag to force any session cookies to be reset on the request.

    @return: A dictionary of the JSON result.
    """
    return self.invoke("GET", relpath, params, headers=headers, allow_redirects=True, clear_cookies=clear_cookies)

  def delete(self, relpath=None, params=None, headers=None, clear_cookies=False):
    """
    Invoke the DELETE method on a resource.
    @param relpath: Optional. A relative path to this resource's path.
    @param params: Key-value data.
    @param headers: Optional. Base set of headers.
    @param clear_cookies: Optional. A flag to force any session cookies to be reset on the request.

    @return: A dictionary of the JSON result.
    """
    return self.invoke("DELETE", relpath, params, headers=headers, clear_cookies=clear_cookies)

  def post(self, relpath=None, params=None, data=None, contenttype=None, headers=None, files=None, allow_redirects=False,
      clear_cookies=False, log_response=True
    ):
    """
    Invoke the POST method on a resource.
    @param relpath: Optional. A relative path to this resource's path.
    @param params: Key-value data.
    @param data: Optional. Body of the request.
    @param contenttype: Optional.
    @param headers: Optional. Base set of headers.
    @param allow_redirects: Optional. Allow request to automatically resolve redirects.
    @param clear_cookies: Optional. A flag to force any session cookies to be reset on the request.

    @return: A dictionary of the JSON result.
    """
    return self.invoke(
      "POST", relpath, params, data, headers=self._make_headers(contenttype, headers), files=files,
      allow_redirects=allow_redirects, clear_cookies=clear_cookies, log_response=log_response
    )

  def put(self, relpath=None, params=None, data=None, contenttype=None, allow_redirects=False, clear_cookies=False, headers=None):
    """
    Invoke the PUT method on a resource.
    @param relpath: Optional. A relative path to this resource's path.
    @param params: Key-value data.
    @param data: Optional. Body of the request.
    @param contenttype: Optional.
    @param allow_redirects: Optional. Allow request to automatically resolve redirects.
    @param clear_cookies: Optional. A flag to force any session cookies to be reset on the request.

    @return: A dictionary of the JSON result.
    """
    return self.invoke("PUT", relpath, params, data, headers=self._make_headers(contenttype, headers),
      allow_redirects=allow_redirects, clear_cookies=clear_cookies
    )

  def _make_headers(self, contenttype=None, headers=None):
    if headers is None:
      headers = {}

    if contenttype:
      headers.update({'Content-Type': contenttype})

    return headers

  def resolve_redirect_url(self, method="GET", relpath=None, params=None, data=None, headers=None, files=None, allow_redirects=True,
      clear_cookies=False, log_response=True
    ):

    resp = self._invoke(
        method=method,
        relpath=relpath,
        params=params,
        data=data,
        headers=headers,
        files=files,
        allow_redirects=allow_redirects,
        clear_cookies=clear_cookies,
        log_response=log_response
    )
    return resp.url.encode("utf-8")


# Same in thrift_util.py for not losing the trace class
def log_if_slow_call(duration, message, logger):
  if duration >= math.floor(WARN_LEVEL_CALL_DURATION_MS / 1000):
    logger.warn('SLOW: %.2f - %s' % (duration, message))
  elif duration >= math.floor(INFO_LEVEL_CALL_DURATION_MS / 1000):
    logger.info('SLOW: %.2f - %s' % (duration, message))
  else:
    # Leave this as logging.debug and not logger.
    # Otherwise we never get these logging messages even with debug enabled.
    # Review this in the future to find out why.
    logging.debug(message)
