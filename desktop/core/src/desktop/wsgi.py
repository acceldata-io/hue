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

import io
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "desktop.settings")

from django.core.wsgi import get_wsgi_application


class DechunkMiddleware(object):
    """Buffer Transfer-Encoding: chunked request bodies so Django can parse them.

    Some upstream proxies (notably Apache Knox, which wraps request entities
    with PartiallyRepeatableHttpEntity for SPNEGO replay) forward POSTs with
    Transfer-Encoding: chunked and no Content-Length. Django's WSGIRequest.POST
    parser cannot handle chunked bodies without Content-Length, so request.POST
    ends up empty and every form-encoded API call (create_notebook,
    create_session, autocomplete, etc.) sees no fields.

    This middleware drains wsgi.input into an in-memory buffer, hands Django a
    plain BytesIO with a proper CONTENT_LENGTH, and removes the chunked marker.
    """

    MAX_BODY = 100 * 1024 * 1024  # 100 MB safety cap

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        te = environ.get("HTTP_TRANSFER_ENCODING", "").lower()
        cl = environ.get("CONTENT_LENGTH", "")
        # Only rewrite when chunked AND Content-Length is absent/empty.
        if "chunked" in te and not cl:
            stream = environ.get("wsgi.input")
            if stream is not None:
                buf = bytearray()
                while True:
                    chunk = stream.read(65536)
                    if not chunk:
                        break
                    buf.extend(chunk)
                    if len(buf) > self.MAX_BODY:
                        break
                body = bytes(buf)
                environ["wsgi.input"] = io.BytesIO(body)
                environ["CONTENT_LENGTH"] = str(len(body))
                environ.pop("HTTP_TRANSFER_ENCODING", None)
        return self.app(environ, start_response)


# This application object is used by the development server
# as well as any WSGI server configured to use this file.
application = DechunkMiddleware(get_wsgi_application())
