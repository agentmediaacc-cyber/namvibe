from collections import defaultdict

from django.db.models import Q

from accounts.models import Follow
from .models import StoryComment, StoryItem, StoryReaction, StoryShare, StoryView


def visible_stories_for(user):
    return StoryItem.objects.visible_to(user).select_related("author", "author__profile").prefetch_related("views", "reactions")


def story_rail_for(user, limit=24):
    stories = list(visible_stories_for(user)[:200])
    followed_ids = set()
    seen_ids = set()
    if user.is_authenticated:
        followed_ids = set(Follow.objects.filter(follower=user).values_list("following_id", flat=True))
        seen_ids = set(StoryView.objects.filter(viewer=user).values_list("story_id", flat=True))

    grouped = defaultdict(list)
    for story in stories:
        grouped[story.author_id].append(story)

    rails = []
    for author_id, items in grouped.items():
        ordered = sorted(items, key=lambda item: item.created_at)
        first = ordered[0]
        rails.append(
            {
                "author": first.author,
                "first_story": first,
                "story_count": len(ordered),
                "is_followed": author_id in followed_ids,
                "is_seen": all(item.id in seen_ids for item in ordered) if user.is_authenticated else False,
            }
        )
    rails.sort(key=lambda item: (not item["is_followed"], item["is_seen"], -item["first_story"].created_at.timestamp()))
    return rails[:limit]


def can_view_story(user, story):
    return StoryItem.objects.visible_to(user).filter(pk=story.pk).exists()


def mark_story_viewed(user, story, session_key=""):
    if not can_view_story(user, story):
        return None
    view = StoryView.objects.create(
        story=story,
        viewer=user if user.is_authenticated else None,
        session_key=session_key or "",
    )
    story.view_count = StoryView.objects.filter(story=story).count()
    story.save(update_fields=["view_count"])
    return view


def toggle_story_like(user, story, reaction_type=StoryReaction.ReactionType.LIKE):
    if not user.is_authenticated or not can_view_story(user, story):
        return None, False
    reaction, created = StoryReaction.objects.get_or_create(
        story=story,
        user=user,
        defaults={"reaction_type": reaction_type},
    )
    if created:
        story.like_count = StoryReaction.objects.filter(story=story).count()
        story.save(update_fields=["like_count"])
        return reaction, True
    if reaction.reaction_type != reaction_type:
        reaction.reaction_type = reaction_type
        reaction.save(update_fields=["reaction_type"])
        return reaction, True
    reaction.delete()
    story.like_count = StoryReaction.objects.filter(story=story).count()
    story.save(update_fields=["like_count"])
    return None, False


def add_story_comment(user, story, body):
    if not user.is_authenticated or not can_view_story(user, story):
        return None
    comment = StoryComment.objects.create(story=story, author=user, body=body.strip())
    story.comment_count = StoryComment.objects.filter(story=story).count()
    story.save(update_fields=["comment_count"])
    return comment


def share_story(user, story, target="forward"):
    if not user.is_authenticated or not can_view_story(user, story):
        return None
    share = StoryShare.objects.create(story=story, user=user, target=target or "forward")
    story.share_count = StoryShare.objects.filter(story=story).count()
    story.save(update_fields=["share_count"])
    return share
