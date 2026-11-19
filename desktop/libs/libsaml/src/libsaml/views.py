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
from django.urls import reverse
from django.utils.html import escape
from djangosaml2.views import AssertionConsumerServiceView, EchoAttributesView, LoginView, LogoutView, MetadataView

from desktop.lib.django_util import render

# Hue middleware checks view_func.login_notrequired. Django as_view() copies
# attributes from dispatch onto the view function. Set the flag on both the
# class and dispatch so SAML login/ACS/logout stay reachable without a session.
for _view_cls in (LoginView, EchoAttributesView, MetadataView, LogoutView, AssertionConsumerServiceView):
  _view_cls.login_notrequired = True
  _view_cls.dispatch.login_notrequired = True

try:
  from djangosaml2.views import LogoutServicePostView

  LogoutServicePostView.login_notrequired = True
  LogoutServicePostView.dispatch.login_notrequired = True
except ImportError:
  # We are on an older version of djangosaml2
  pass


def local_logout(request, next_page=None):
  """
  Local logout page. The Hue session is already cleared. This only offers a
  link back to SAML login and does not end the identity-provider session.
  """
  next_path = request.GET.get("next", "/")
  login_url = "%s?next=%s" % (reverse('saml2_login'), escape(next_path))

  return render('logged_out.mako', request, {
    'login_url': login_url,
  })


setattr(local_logout, 'login_notrequired', True)
