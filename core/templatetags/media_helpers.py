from django import template

from core.media import (
    DEFAULT_MEDIA,
    live_cover_url,
    media_file_exists,
    post_media_url,
    profile_avatar_url,
    profile_cover_url,
    safe_file_url,
)


register = template.Library()


@register.simple_tag
def avatar_url(profile):
    return profile_avatar_url(profile)


@register.simple_tag
def cover_url(profile):
    return profile_cover_url(profile)


@register.simple_tag
def media_url(media):
    return post_media_url(media)


@register.simple_tag
def live_thumbnail_url(session):
    return live_cover_url(session)


@register.simple_tag
def file_url(file_field, fallback=DEFAULT_MEDIA):
    return safe_file_url(file_field, fallback)


@register.filter
def file_exists(file_field):
    return media_file_exists(file_field)
