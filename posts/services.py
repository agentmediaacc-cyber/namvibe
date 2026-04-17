from collections import Counter
from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from accounts.models import Follow, FriendRequest, Mute
from communities.models import Community, CommunityMembership
from .models import Comment, Like, Post, PostView, Report, Save, Share


def notification_hook(event_type, *, actor=None, recipient=None, post=None, comment=None):
    # TODO(notifications): connect this to the notifications app trigger layer in Phase 8.
    return {
        "event_type": event_type,
        "actor": actor,
        "recipient": recipient,
        "post": post,
        "comment": comment,
    }


def base_visible_posts(user):
    return (
        Post.objects.visible_to(user)
        .select_related("author", "author__profile", "community", "target_user")
        .prefetch_related(
            "media",
            "poll__options",
            "comments__author__profile",
            "comments__replies__author__profile",
        )
    )


def can_interact_with_post(user, post):
    if not user.is_authenticated:
        return False
    return Post.objects.visible_to(user).filter(pk=post.pk).exists()


def threaded_comments_for_post(post):
    return (
        Comment.objects.filter(post=post, parent__isnull=True, is_deleted=False)
        .select_related("author", "author__profile")
        .prefetch_related("replies__author__profile")
        .order_by("-is_pinned", "created_at")
    )


def toggle_like(user, post, reaction_type=Like.ReactionType.LIKE):
    if not can_interact_with_post(user, post):
        return None, False
    like, created = Like.objects.get_or_create(
        user=user,
        post=post,
        defaults={"reaction_type": reaction_type},
    )
    if created:
        post.like_count = Like.objects.filter(post=post).count()
        post.save(update_fields=["like_count"])
        notification_hook("like", actor=user, recipient=post.author, post=post)
        return like, True
    if like.reaction_type != reaction_type:
        like.reaction_type = reaction_type
        like.save(update_fields=["reaction_type"])
        return like, True
    like.delete()
    post.like_count = Like.objects.filter(post=post).count()
    post.save(update_fields=["like_count"])
    return None, False


def toggle_save(user, post):
    if not can_interact_with_post(user, post):
        return None, False
    save, created = Save.objects.get_or_create(user=user, post=post)
    if created:
        post.save_count = Save.objects.filter(post=post).count()
        post.save(update_fields=["save_count"])
        return save, True
    save.delete()
    post.save_count = Save.objects.filter(post=post).count()
    post.save(update_fields=["save_count"])
    return None, False


def add_comment(user, post, body, parent=None):
    if not post.allow_comments or not can_interact_with_post(user, post):
        return None
    comment = Comment.objects.create(post=post, author=user, parent=parent, body=body.strip())
    post.comment_count = Comment.objects.filter(post=post, is_deleted=False).count()
    post.save(update_fields=["comment_count"])
    notification_hook("comment", actor=user, recipient=post.author, post=post, comment=comment)
    return comment


def delete_comment(user, comment):
    if comment.author != user and comment.post.author != user:
        return False
    comment.is_deleted = True
    comment.body = ""
    comment.save(update_fields=["is_deleted", "body", "updated_at"])
    comment.post.comment_count = Comment.objects.filter(post=comment.post, is_deleted=False).count()
    comment.post.save(update_fields=["comment_count"])
    return True


def toggle_pin_comment(user, comment):
    if comment.post.author != user:
        return False
    comment.is_pinned = not comment.is_pinned
    comment.save(update_fields=["is_pinned", "updated_at"])
    return True


def create_share(user, post, target=Share.Target.FEED, message=""):
    if not post.allow_sharing or not can_interact_with_post(user, post):
        return None
    share = Share.objects.create(post=post, user=user, target=target, message=message.strip())
    post.share_count = Share.objects.filter(post=post).count()
    post.save(update_fields=["share_count"])
    notification_hook("share", actor=user, recipient=post.author, post=post)
    return share


def track_view(user, post, session_key="", duration_seconds=0, completed=False):
    if user.is_authenticated and not can_interact_with_post(user, post):
        return None
    view = PostView.objects.create(
        post=post,
        user=user if user.is_authenticated else None,
        session_key=session_key or "",
        duration_seconds=max(int(duration_seconds or 0), 0),
        completed=completed,
    )
    post.view_count = PostView.objects.filter(post=post).count()
    post.save(update_fields=["view_count"])
    return view


def create_report(reporter, *, post=None, reported_user=None, reason=Report.Reason.OTHER, details=""):
    if post and not can_interact_with_post(reporter, post):
        return None
    report = Report.objects.create(
        reporter=reporter,
        post=post,
        reported_user=reported_user,
        reason=reason,
        details=details.strip(),
    )
    notification_hook("report", actor=reporter, recipient=getattr(post, "author", reported_user), post=post)
    return report


@dataclass
class FeedRankingService:
    viewer: object
    location: str = ""

    def __post_init__(self):
        self.now = timezone.now()
        self.followed_ids = set()
        self.friend_ids = set()
        self.muted_ids = set()
        self.interest_post_types = Counter()
        self.interest_tags = Counter()
        self.viewer_location = self.location
        if self.viewer.is_authenticated:
            self.followed_ids = set(Follow.objects.filter(follower=self.viewer).values_list("following_id", flat=True))
            friend_pairs = FriendRequest.objects.filter(
                Q(from_user=self.viewer) | Q(to_user=self.viewer),
                status=FriendRequest.Status.ACCEPTED,
            ).values_list("from_user_id", "to_user_id")
            self.friend_ids = {item for pair in friend_pairs for item in pair if item != self.viewer.id}
            self.muted_ids = set(Mute.objects.filter(muter=self.viewer).values_list("muted_id", flat=True))
            profile = getattr(self.viewer, "profile", None)
            self.viewer_location = self.viewer_location or getattr(profile, "location", "")
            self._load_interest_hints()

    def _load_interest_hints(self):
        liked_posts = Post.objects.filter(likes__user=self.viewer).values_list("post_type", "hashtags")[:100]
        saved_posts = Post.objects.filter(saves__user=self.viewer).values_list("post_type", "hashtags")[:100]
        viewed_posts = Post.objects.filter(views__user=self.viewer).values_list("post_type", "hashtags")[:100]
        for post_type, hashtags in list(liked_posts) + list(saved_posts) + list(viewed_posts):
            self.interest_post_types[post_type] += 1
            for tag in hashtags or []:
                self.interest_tags[tag.lower()] += 1

    def with_annotations(self, queryset: QuerySet):
        recent_window = self.now - timedelta(hours=24)
        return queryset.annotate(
            recent_likes=Count("likes", filter=Q(likes__created_at__gte=recent_window), distinct=True),
            recent_comments=Count("comments", filter=Q(comments__created_at__gte=recent_window, comments__is_deleted=False), distinct=True),
            recent_saves=Count("saves", filter=Q(saves__created_at__gte=recent_window), distinct=True),
            recent_shares=Count("shares", filter=Q(shares__created_at__gte=recent_window), distinct=True),
        )

    def score(self, post):
        age_hours = max((self.now - (post.published_at or post.created_at)).total_seconds() / 3600, 0)
        recency = max(0, 48 - age_hours) * 2
        follow_score = 35 if post.author_id in self.followed_ids else 0
        friend_score = 45 if post.author_id in self.friend_ids else 0
        velocity = (
            getattr(post, "recent_likes", 0) * 4
            + getattr(post, "recent_comments", 0) * 6
            + getattr(post, "recent_saves", 0) * 5
            + getattr(post, "recent_shares", 0) * 7
        )
        total_engagement = post.like_count + (post.comment_count * 2) + (post.save_count * 2) + (post.share_count * 3) + post.view_count * 0.2
        interest = self.interest_post_types[post.post_type] * 3
        interest += sum(self.interest_tags[tag.lower()] for tag in post.hashtags or [])
        author_location = getattr(getattr(post.author, "profile", None), "location", "")
        location_score = 12 if self.viewer_location and author_location and self.viewer_location.lower() == author_location.lower() else 0
        type_weight = {
            Post.PostType.REEL: 12,
            Post.PostType.VIDEO: 8,
            Post.PostType.PHOTO: 6,
            Post.PostType.POLL: 5,
            Post.PostType.FLYER: 4,
            Post.PostType.TEXT: 2,
            Post.PostType.STORY: 2,
            Post.PostType.LIVE: 8,
        }.get(post.post_type, 1)
        mute_penalty = -80 if post.author_id in self.muted_ids else 0
        return recency + follow_score + friend_score + velocity + total_engagement + interest + location_score + type_weight + mute_penalty

    def rank(self, queryset, limit=100):
        posts = list(self.with_annotations(queryset)[:limit])
        return sorted(posts, key=self.score, reverse=True)


def trending_hashtags(limit=20):
    counter = Counter()
    for tags in Post.objects.published().values_list("hashtags", flat=True)[:500]:
        for tag in tags or []:
            counter[tag.lower()] += 1
    return counter.most_common(limit)


def suggested_users_for(user, limit=8):
    qs = Post.objects.published().values("author").annotate(score=Count("id")).order_by("-score")
    author_ids = [item["author"] for item in qs]
    if user.is_authenticated:
        followed = set(Follow.objects.filter(follower=user).values_list("following_id", flat=True))
        author_ids = [author_id for author_id in author_ids if author_id != user.id and author_id not in followed]
    from accounts.models import Profile

    return Profile.objects.select_related("user").filter(user_id__in=author_ids)[:limit]


def suggested_communities_for(user, limit=8):
    communities = Community.objects.annotate(active_members=Count("memberships", filter=Q(memberships__status=CommunityMembership.Status.ACTIVE)))
    if user.is_authenticated:
        joined_ids = CommunityMembership.objects.filter(user=user, status=CommunityMembership.Status.ACTIVE).values_list("community_id", flat=True)
        communities = communities.exclude(id__in=joined_ids)
    return communities.select_related("owner").order_by("-active_members", "-created_at")[:limit]
