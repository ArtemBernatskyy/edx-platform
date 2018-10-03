"""
Views to support bulk email functionalities like opt-out.
"""

from __future__ import division

import logging

from six import text_type

from django.contrib.auth.models import User
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET

from bulk_email.models import Optout
from lms.djangoapps.notification_prefs.views import (
    UsernameCipher,
    UsernameDecryptionException
)

from opaque_keys.edx.keys import CourseKey


log = logging.getLogger("lms.bulkemail")


@require_GET
def opt_out_email_updates(request, token, course_id):   # pylint: disable=unused-variable
    """
    A view that let users opt out of any email updates.

    This meant is meant to be the target of an opt-out link or button.
    The request must be a GET, and the `token` parameter must decrypt
    to a valid username. The `course_id` is the course id of any course.

    A 405 will be returned if the request method is not GET. A 404 will be
    returned if the token parameter does not decrypt to a valid username.
    It returns status 204 (no content) or an error.
    """
    try:
        username = UsernameCipher().decrypt(token.encode())
        user = User.objects.get(username=username)
    except UnicodeDecodeError:
        raise Http404("base64url")
    except UsernameDecryptionException as exn:
        raise Http404(text_type(exn))
    except User.DoesNotExist:
        raise Http404("username")

    course_key = CourseKey.from_string(course_id)
    Optout.objects.get_or_create(user=user, course_id=course_key)
    log.info(
        u"User %s (%s) opted out of receiving emails from course %s",
        user.username,
        user.email,
        course_id,
    )

    return HttpResponse(status=204)
