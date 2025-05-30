## Licensed to Cloudera, Inc. under one
## or more contributor license agreements.  See the NOTICE file
## distributed with this work for additional information
## regarding copyright ownership.  Cloudera, Inc. licenses this file
## to you under the Apache License, Version 2.0 (the
## "License"); you may not use this file except in compliance
## with the License.  You may obtain a copy of the License at
##
##     http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.
<%!
import sys

from desktop.conf import ENABLE_ORGANIZATIONS
from desktop.lib.django_util import extract_field_data
from desktop.views import commonheader, commonfooter

if sys.version_info[0] > 2:
  from urllib.parse import quote as urllib_quote
  unicode = str
  from django.utils.translation import gettext as _
else:
  from urllib import quote as urllib_quote
  from django.utils.translation import ugettext as _
%>

<%namespace name="layout" file="layout.mako" />

% if not is_embeddable:
  ${ commonheader(_('Groups'), "useradmin", user, request) | n,unicode }
% endif

${ layout.menubar(section='groups') }

<%def name="render_field(field)">
  % if not field.is_hidden:
    <% group_class = len(field.errors) and "error" or "" %>
    <div class="control-group ${group_class}">
      <label class="control-label" for="id_${field.html_name}">${field.label}</label>
    <div class="controls">
    ${unicode(field) | n}
    % if len(field.errors):
      <span class="help-inline">${unicode(field.errors) | n}</span>
    % endif
    </div>
    </div>
  % endif
</%def>

<div id="editGroupComponents" class="useradmin container-fluid">
  <div class="card card-small">
    % if name:
        <h1 class="card-heading simple">
          ${ _('Edit %(name)s') % {'name': name} }
          % if ENABLE_ORGANIZATIONS.get():
            @ ${ user.organization }
          % endif
        </h1>
    % else:
      % if ldap:
          <h1 class="card-heading simple">${_('Add/Sync LDAP group')}</h1>
      % else:
          <h1 class="card-heading simple">${_('Create group')}</h1>
      % endif
    % endif

    <br/>

    <form id="editForm" action="${urllib_quote(action)}" method="POST" class="form form-horizontal" autocomplete="off">
      ${ csrf_token(request) | n,unicode }
      <fieldset>
        % for field in form:
          ${ render_field(field) }
        % endfor
      </fieldset>
      <br/>

      <div class="form-actions">
        % if name:
            <input type="submit" class="btn btn-primary disable-feedback" value="${_('Update group')}"/>
        % else:
          % if ldap:
              <input type="submit" class="btn btn-primary disable-feedback" value="${_('Add/Sync group')}"/>
          % else:
              <input type="submit" class="btn btn-primary disable-feedback" value="${_('Add group')}"/>
          % endif
        % endif
        % if is_embeddable:
          <input type="hidden" value="true" name="is_embeddable" />
        % endif
        <a href="/useradmin/groups" class="btn">${_('Cancel')}</a>
      </div>
    </form>
  </div>
</div>

<script src="${ static('desktop/js/edit_group-inline.js') }" type="text/javascript"></script>
${ layout.commons() }

% if not is_embeddable:
  ${ commonfooter(request, messages) | n,unicode }
% endif
