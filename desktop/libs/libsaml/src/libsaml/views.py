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
from djangosaml2.views import AssertionConsumerServiceView, EchoAttributesView, LoginView, LogoutView, MetadataView

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
