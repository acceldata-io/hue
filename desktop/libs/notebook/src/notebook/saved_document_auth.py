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

"""
Resolve existing documents for notebook/pipeline save operations with write permission.

Used by save API decorators and by ``_save_notebook`` / ``_save_pipeline`` so authorization
cannot be bypassed when a view decorator is missing or incomplete.
"""

from django.utils.translation import gettext as _

from desktop.lib.exceptions_renderable import PopupException
from desktop.models import Document2, FilesystemException


def get_writable_document_for_update(document_payload, user):
  """
  Resolve a Document2 the caller may update when saving notebook or pipeline state.

  Resolution order matches _save_notebook and _save_pipeline:

  1. parentSavedQueryUuid — save into the parent saved query.
  2. id — update an existing document by primary key.

  Returns the document when updating, or None when creating a new one.
  Raises PopupException when the document is missing or the user cannot write it.
  """
  if document_payload.get('parentSavedQueryUuid'):
    try:
      return Document2.objects.get_by_uuid(
        user=user,
        uuid=document_payload['parentSavedQueryUuid'],
        perm_type='write',
      )
    except FilesystemException as ex:
      raise PopupException(str(ex))

  if document_payload.get('id'):
    try:
      document = Document2.objects.get(id=document_payload['id'])
    except Document2.DoesNotExist:
      # Same message as a denied write so callers cannot probe which document ids exist.
      raise PopupException(_("Document does not exist or you don't have the permission to access it."))
    document.can_write_or_exception(user)
    return document

  return None
