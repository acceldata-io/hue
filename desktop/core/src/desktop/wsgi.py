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

import os
import tempfile

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

    This middleware drains wsgi.input into a spooled buffer, hands Django a
    stream with a proper CONTENT_LENGTH, and removes the chunked marker.

    Requests larger than MAX_BODY are rejected with HTTP 413 instead of being
    silently truncated. The buffer spills from RAM to disk once it exceeds
    SPOOL_THRESHOLD so many small concurrent requests don't exhaust memory.
    """

    MAX_BODY = 100 * 1024 * 1024        # 100 MB — anything larger returns 413
    SPOOL_THRESHOLD = 1 * 1024 * 1024   # 1 MB in RAM before spilling to disk
    READ_CHUNK = 64 * 1024

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        te = environ.get("HTTP_TRANSFER_ENCODING", "").lower()
        cl = environ.get("CONTENT_LENGTH", "")
        # Only rewrite when chunked AND Content-Length is absent/empty.
        if "chunked" not in te or cl:
            return self.app(environ, start_response)

        stream = environ.get("wsgi.input")
        if stream is None:
            return self.app(environ, start_response)

        # Small bodies stay in RAM; larger ones spill to a tmpfile so 50
        # concurrent uploads don't pin 5 GB of heap.
        buf = tempfile.SpooledTemporaryFile(max_size=self.SPOOL_THRESHOLD)
        size = 0
        try:
            while True:
                chunk = stream.read(self.READ_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > self.MAX_BODY:
                    buf.close()
                    body = b"Payload Too Large\n"
                    start_response(
                        "413 Payload Too Large",
                        [("Content-Type", "text/plain"),
                         ("Content-Length", str(len(body)))],
                    )
                    return [body]
                buf.write(chunk)
        except (OSError, IOError):
            buf.close()
            raise
        buf.seek(0)

        environ["wsgi.input"] = buf
        environ["CONTENT_LENGTH"] = str(size)
        environ.pop("HTTP_TRANSFER_ENCODING", None)
        return self.app(environ, start_response)


# This application object is used by the development server
# as well as any WSGI server configured to use this file.
application = DechunkMiddleware(get_wsgi_application())
