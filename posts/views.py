from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from accounts.models import Follow, Profile
from accounts.supabase import supabase_profile_id_for_user
from communities.models import Community
from live.models import LiveSession
from stories.models import StoryItem
from stories.services import visible_stories_for
from supportapp.models import SystemPromoCard
from wallet.services import active_boosted_post_ids, active_gifts, premium_badge_for

from .forms import POST_TYPE_FORMS
from .models import Comment, Like, Post, PostMedia, Report, Save, Share
from .services import (
    FeedRankingService,
    add_comment,
    base_visible_posts,
    can_interact_with_post,
    create_report,
    create_share,
    delete_comment,
    suggested_communities_for,
    suggested_users_for,
    threaded_comments_for_post,
    toggle_comment_reaction,
    toggle_like,
    toggle_pin_comment,
    toggle_save,
    track_view,
    trending_hashtags,
)
from .supabase_posts import create_post, get_public_posts


def _handle_feed_exception(exc):
    if not settings.DEBUG:
        raise
    return str(exc)


def _session_user(request):
    user_id = request.session.get("eharo_user_id", "")
    if not user_id:
        return None
    return {
        "user_id": user_id,
        "full_name": request.session.get("eharo_full_name", "Namvibe User"),
        "username": request.session.get("eharo_username", "user"),
        "email": request.session.get("eharo_email", ""),
    }


def _post_sync_identity(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        return {
            "user_id": str(supabase_profile_id_for_user(request.user)),
            "full_name": request.user.get_full_name() or getattr(profile, "display_name", "") or request.user.username,
            "username": getattr(profile, "username", "") or request.user.username,
            "email": request.user.email or "",
        }
    return _session_user(request)


def _post_queryset_for_user(request):
    return base_visible_posts(request.user)


def _form_for_post_type(post_type):
    return POST_TYPE_FORMS.get(post_type, POST_TYPE_FORMS[Post.PostType.TEXT])


def _post_type_from_request(request, fallback=Post.PostType.TEXT):
    value = request.POST.get("post_type") or request.GET.get("type") or fallback
    if value == "live_announcement":
        value = Post.PostType.LIVE
    return value if value in POST_TYPE_FORMS else fallback


def _paginated_feed(request, queryset, *, title, subtitle, active_feed):
    safe_mode_message = ""
    try:
        ranked_posts = FeedRankingService(request.user).rank(queryset, limit=120)
        ranked_posts = _decorate_posts_for_display(ranked_posts)
        paginator = Paginator(ranked_posts, 15)
        page_obj = paginator.get_page(request.GET.get("page"))
    except Exception as exc:
        safe_mode_message = _handle_feed_exception(exc)
        page_obj = Paginator([], 15).get_page(request.GET.get("page"))
    return render(
        request,
        "posts/feed.html",
        {
            "page_obj": page_obj,
            "posts": page_obj.object_list,
            "legacy_posts": [],
            "feed_title": title,
            "feed_subtitle": subtitle,
            "active_feed": active_feed,
            "safe_mode_message": safe_mode_message,
        },
    )


def _post_action_redirect(request, post):
    return redirect(request.POST.get("next") or reverse("post_detail", kwargs={"uuid": post.uuid}))


def _decorate_posts_for_display(posts):
    post_list = list(posts)
    boosted_ids = active_boosted_post_ids([post.id for post in post_list])
    for post in post_list:
        post.is_boosted = post.id in boosted_ids
        post.author_premium_badge = premium_badge_for(post.author)
    return post_list


@require_http_methods(["GET"])
def feed_view(request):
    safe_mode_message = ""
    legacy_posts = []
    decorated_posts = []
    try:
        queryset = base_visible_posts(request.user).published().order_by("-published_at", "-created_at")
        page_obj = Paginator(queryset, 15).get_page(request.GET.get("page"))
        decorated_posts = _decorate_posts_for_display(page_obj.object_list)
        if not page_obj.object_list:
            legacy_posts = get_public_posts(limit=50)
            if not isinstance(legacy_posts, list):
                legacy_posts = []
    except Exception as exc:
        safe_mode_message = _handle_feed_exception(exc)
        page_obj = Paginator([], 15).get_page(request.GET.get("page"))
    return render(
        request,
        "posts/feed.html",
        {
            "page_obj": page_obj,
            "posts": decorated_posts,
            "legacy_posts": legacy_posts,
            "feed_title": "For You",
            "feed_subtitle": "A ranked feed of public, followed, community, and creator posts.",
            "active_feed": "for_you",
            "safe_mode_message": safe_mode_message,
        },
    )


def following_feed_view(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")
    followed_ids = request.user.following_edges.values_list("following_id", flat=True)
    queryset = base_visible_posts(request.user).published().filter(author_id__in=followed_ids)
    return _paginated_feed(
        request,
        queryset,
        title="Following",
        subtitle="Posts from creators and people you follow.",
        active_feed="following",
    )


def friends_feed_view(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")
    friend_pairs = request.user.sent_friend_requests.filter(status="accepted").values_list("to_user_id", flat=True)
    reverse_pairs = request.user.received_friend_requests.filter(status="accepted").values_list("from_user_id", flat=True)
    queryset = base_visible_posts(request.user).published().filter(
        Q(author_id__in=friend_pairs) | Q(author_id__in=reverse_pairs)
    )
    return _paginated_feed(
        request,
        queryset,
        title="Friends",
        subtitle="Posts visible through accepted friendships.",
        active_feed="friends",
    )


def trending_feed_view(request):
    queryset = base_visible_posts(request.user).published().order_by(
        "-like_count",
        "-comment_count",
        "-share_count",
        "-published_at",
    )
    return _paginated_feed(
        request,
        queryset,
        title="Trending",
        subtitle="Posts gaining attention across Namvibe.",
        active_feed="trending",
    )


def nearby_feed_view(request):
    location = request.GET.get("location", "").strip()
    if not location and request.user.is_authenticated:
        location = getattr(getattr(request.user, "profile", None), "location", "")
    queryset = base_visible_posts(request.user).published()
    if location:
        queryset = queryset.filter(
            Q(author__profile__location__iexact=location) | Q(community__name__icontains=location)
        )
    return _paginated_feed(
        request,
        queryset,
        title="Nearby Namibia",
        subtitle=location or "Local creator posts and communities.",
        active_feed="nearby",
    )


@require_http_methods(["GET", "POST"])
def create_post_view(request):
    if request.method == "GET":
        return redirect("studio")
    if not request.user.is_authenticated:
        messages.error(request, "Login required to create a post.")
        return redirect("login")

    content = request.POST.get("content", "").strip()
    media_file = request.FILES.get("media") or request.FILES.get("media_file")
    post_type = request.POST.get("post_type") or Post.PostType.TEXT
    if media_file:
        content_type = getattr(media_file, "content_type", "") or ""
        if content_type.startswith("video/"):
            post_type = Post.PostType.VIDEO
        elif content_type.startswith("image/"):
            post_type = Post.PostType.PHOTO
    if post_type not in Post.PostType.values:
        post_type = Post.PostType.TEXT

    if content or media_file:
        try:
            with transaction.atomic():
                post = Post.objects.create(
                    author=request.user,
                    post_type=post_type,
                    title=content[:120],
                    caption=content,
                    audience=Post.Audience.PUBLIC,
                    share_target=Post.ShareTarget.MAIN_FEED,
                    status=Post.Status.PUBLISHED,
                    published_at=timezone.now(),
                    allow_comments=True,
                    allow_sharing=True,
                )
                if media_file:
                    media_type = (
                        PostMedia.MediaType.VIDEO if post_type == Post.PostType.VIDEO else PostMedia.MediaType.IMAGE
                    )
                    media = PostMedia.objects.create(post=post, media_type=media_type, file=media_file)
                    if not getattr(media.file, "name", ""):
                        raise ValueError("Uploaded media did not save correctly.")
        except Exception:
            messages.error(request, "We could not publish that post. Please try the upload again.")
            return redirect("feed")

        user = _post_sync_identity(request)
        if user:
            create_post(
                user_id=user["user_id"],
                full_name=user["full_name"],
                username=user["username"],
                email=user["email"],
                title=content[:120],
                caption=content,
                media_file=media_file,
            )
    return redirect("feed")


@require_http_methods(["POST"])
def save_post_view(request):
    user = _post_sync_identity(request)
    if not user:
        messages.error(request, "Login required to create a post.")
        return redirect("login")

    title = request.POST.get("title", "").strip()
    caption = request.POST.get("caption", "").strip()
    media_file = request.FILES.get("media_file") or request.FILES.get("media") or request.FILES.get("flyer_image")
    if title or caption or media_file or request.POST.get("flyer_title", "").strip() or request.POST.get("poll_question", "").strip():
        create_post(
            user_id=user["user_id"],
            full_name=user["full_name"],
            username=user["username"],
            email=user["email"],
            post_type=request.POST.get("post_type", request.POST.get("media_type", "text")),
            title=title,
            caption=caption,
            hashtags=request.POST.get("hashtags", ""),
            tagged_users=request.POST.get("tagged_users", ""),
            audience=request.POST.get("audience", "Public"),
            share_to=request.POST.get("share_to", "Main Feed"),
            group_name=request.POST.get("group_name", ""),
            single_user=request.POST.get("single_user", ""),
            specific_user=request.POST.get("specific_user", ""),
            community_name=request.POST.get("community_name", ""),
            background_theme=request.POST.get("background_theme", "theme-purple"),
            font_theme=request.POST.get("font_theme", "font-modern"),
            crop_style=request.POST.get("crop_style", "cover"),
            image_effect=request.POST.get("image_effect", "none"),
            video_mode=request.POST.get("video_mode", "normal"),
            display_mode=request.POST.get("display_mode", "cover"),
            overlay_text=request.POST.get("overlay_text", ""),
            flyer_background=request.POST.get("flyer_background", "gradient-violet"),
            flyer_text_color=request.POST.get("flyer_text_color", "#ffffff"),
            flyer_layout=request.POST.get("flyer_layout", "centered"),
            flyer_title=request.POST.get("flyer_title", ""),
            flyer_body=request.POST.get("flyer_body", ""),
            flyer_cta=request.POST.get("flyer_cta", ""),
            music_track=request.POST.get("music_track", ""),
            motion_effect=request.POST.get("motion_effect", "none"),
            poll_question=request.POST.get("poll_question", ""),
            poll_options=request.POST.get("poll_options", ""),
            media_type=request.POST.get("media_type", "text"),
            allow_comments="allow_comments" in request.POST,
            allow_share="allow_share" in request.POST,
            save_story="save_story" in request.POST,
            premium_badge="premium_badge" in request.POST,
            save_draft="save_draft" in request.POST,
            media_file=media_file,
        )
    return redirect(f"{reverse('user_dashboard')}?section=posts")


@login_required(login_url="login")
@csrf_protect
def studio_view(request):
    post_type = _post_type_from_request(request)
    form_class = _form_for_post_type(post_type)
    form = form_class(request.POST or None, request.FILES or None, author=request.user)
    if request.method == "POST" and form.is_valid():
        post = form.save()
        if post.status == Post.Status.DRAFT:
            messages.success(request, "Draft saved.")
            return redirect("studio_draft", uuid=post.uuid)
        messages.success(request, "Post published.")
        return redirect("post_detail", uuid=post.uuid)

    return render(
        request,
        "posts/creator_studio.html",
        {
            "form": form,
            "active_type": post_type,
            "post_types": Post.PostType.choices,
            "audiences": Post.Audience.choices,
            "share_targets": Post.ShareTarget.choices,
            "recent_drafts": Post.objects.filter(author=request.user, status=Post.Status.DRAFT).prefetch_related("media")[:6],
        },
    )


@login_required(login_url="login")
@csrf_protect
def save_draft_view(request):
    if request.method != "POST":
        return redirect("studio")
    mutable_post = request.POST.copy()
    mutable_post["save_draft"] = "on"
    post_type = mutable_post.get("post_type") or Post.PostType.TEXT
    if post_type == "live_announcement":
        post_type = Post.PostType.LIVE
        mutable_post["post_type"] = post_type
    form_class = _form_for_post_type(post_type)
    form = form_class(mutable_post, request.FILES, author=request.user)
    if form.is_valid():
        post = form.save()
        messages.success(request, "Draft saved.")
        return redirect("studio_draft", uuid=post.uuid)
    return render(
        request,
        "posts/creator_studio.html",
        {
            "form": form,
            "active_type": post_type,
            "post_types": Post.PostType.choices,
            "audiences": Post.Audience.choices,
            "share_targets": Post.ShareTarget.choices,
        },
    )


@login_required(login_url="login")
def studio_draft_view(request, uuid):
    post = get_object_or_404(
        Post.objects.select_related("author", "community", "target_user").prefetch_related("media", "poll__options"),
        uuid=uuid,
        author=request.user,
        status=Post.Status.DRAFT,
    )
    return render(request, "posts/studio_draft.html", {"post": post})


@login_required(login_url="login")
def preview_post_view(request, uuid):
    post = get_object_or_404(
        Post.objects.select_related("author", "author__profile", "community").prefetch_related("media", "poll__options"),
        uuid=uuid,
        author=request.user,
    )
    return render(request, "posts/post_preview.html", {"post": post})


@login_required(login_url="login")
@csrf_protect
def edit_post_view(request, uuid):
    post = get_object_or_404(Post.objects.select_related("author").prefetch_related("media"), uuid=uuid)
    if post.author != request.user:
        return HttpResponseForbidden("You cannot edit this post.")
    form_class = _form_for_post_type(post.post_type)
    form = form_class(request.POST or None, request.FILES or None, instance=post, author=request.user)
    if request.method == "POST" and form.is_valid():
        edited_post = form.save()
        edited_post.is_edited = True
        edited_post.save(update_fields=["is_edited", "updated_at"])
        messages.success(request, "Post updated.")
        return redirect("post_detail", uuid=post.uuid)
    return render(
        request,
        "posts/creator_studio.html",
        {
            "form": form,
            "post": post,
            "active_type": post.post_type,
            "post_types": Post.PostType.choices,
            "audiences": Post.Audience.choices,
            "share_targets": Post.ShareTarget.choices,
        },
    )


@login_required(login_url="login")
@require_http_methods(["POST"])
def delete_post_view(request, uuid):
    post = get_object_or_404(Post, uuid=uuid)
    if post.author != request.user:
        return HttpResponseForbidden("You cannot delete this post.")
    post.soft_delete()
    messages.success(request, "Post deleted.")
    return redirect("author_posts", username=request.user.profile.username)


@login_required(login_url="login")
@require_http_methods(["POST"])
def publish_draft_view(request, uuid):
    post = get_object_or_404(Post, uuid=uuid, author=request.user, status=Post.Status.DRAFT)
    post.publish()
    messages.success(request, "Draft published.")
    return redirect("post_detail", uuid=post.uuid)


def post_detail_view(request, uuid):
    post = get_object_or_404(_post_queryset_for_user(request), uuid=uuid)
    post.is_boosted = bool(active_boosted_post_ids([post.id]))
    post.author_premium_badge = premium_badge_for(post.author)
    comments = threaded_comments_for_post(post)
    liked = request.user.is_authenticated and Like.objects.filter(user=request.user, post=post).exists()
    saved = request.user.is_authenticated and Save.objects.filter(user=request.user, post=post).exists()
    default_gift = active_gifts().first()
    return render(
        request,
        "posts/post_detail.html",
        {
            "post": post,
            "comments": comments,
            "liked": liked,
            "saved": saved,
            "comment_reaction_choices": Like.ReactionType.choices,
            "default_gift": default_gift,
            "under_review": post.is_hidden_by_moderation,
        },
    )


def author_posts_list_view(request, username):
    profile = get_object_or_404(Profile.objects.select_related("user"), username__iexact=username)
    posts = _post_queryset_for_user(request).filter(author=profile.user)
    paginator = Paginator(posts, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_obj.object_list = _decorate_posts_for_display(page_obj.object_list)
    return render(request, "posts/author_posts.html", {"profile": profile, "page_obj": page_obj})


def community_posts_list_view(request, slug):
    community = get_object_or_404(Community.objects.select_related("owner"), slug__iexact=slug)
    posts = _post_queryset_for_user(request).filter(community=community)
    paginator = Paginator(posts, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "posts/community_posts.html", {"community": community, "page_obj": page_obj})


def community_feed_view(request, slug):
    community = get_object_or_404(Community.objects.select_related("owner"), slug__iexact=slug)
    queryset = base_visible_posts(request.user).published().filter(community=community)
    return _paginated_feed(
        request,
        queryset,
        title=f"{community.name} Feed",
        subtitle=community.description,
        active_feed="community",
    )


def get_comments_view(request, uuid):
    post = get_object_or_404(Post, uuid=uuid)
    if not Post.objects.visible_to(request.user).filter(pk=post.pk).exists():
        return HttpResponseForbidden("You cannot view comments for this post.")
    
    comments = threaded_comments_for_post(post)
    comment_data = []
    for c in comments:
        profile = getattr(c.author, "profile", None)
        comment_data.append({
            "id": c.id,
            "author": profile.username if profile else c.author.username,
            "display_name": (profile.display_name if profile else "") or c.author.username,
            "avatar": profile.avatar.url if profile and profile.avatar else "/static/images/default-avatar.svg",
            "body": c.body,
            "created_at": "Just now" if (timezone.now() - c.created_at).total_seconds() < 60 else f"{int((timezone.now() - c.created_at).total_seconds() // 60)}m ago",
            "like_count": c.like_count,
            "is_pinned": c.is_pinned,
            "replies": [{
                "author": r.author.profile.username if hasattr(r.author, "profile") else r.author.username,
                "body": r.body
            } for r in c.replies.all() if not r.is_deleted]
        })
    
    return JsonResponse({
        "comments": comment_data,
        "comment_count": post.comment_count,
        "allow_comments": post.allow_comments
    })


def reels_feed_view(request):
    safe_mode_message = ""
    liked_post_ids = []
    saved_post_ids = []
    followed_user_ids = []
    try:
        queryset = (
            base_visible_posts(request.user)
            .published()
            .filter(post_type__in=[Post.PostType.REEL, Post.PostType.VIDEO])
            .select_related("author", "author__profile")
            .prefetch_related("media", "comments__author__profile")
        )
        ranked_posts = FeedRankingService(request.user).rank(queryset, limit=50)
        ranked_posts = _decorate_posts_for_display(ranked_posts)

        if request.user.is_authenticated:
            liked_post_ids = list(Like.objects.filter(user=request.user, post__in=ranked_posts).values_list("post_id", flat=True))
            saved_post_ids = list(Save.objects.filter(user=request.user, post__in=ranked_posts).values_list("post_id", flat=True))
            author_ids = [p.author_id for p in ranked_posts]
            followed_user_ids = list(Follow.objects.filter(follower=request.user, following_id__in=author_ids).values_list("following_id", flat=True))

    except Exception as exc:
        safe_mode_message = _handle_feed_exception(exc)
        ranked_posts = []

    default_gift = active_gifts().first()

    return render(
        request,
        "posts/reels_fullscreen.html",
        {
            "reels": ranked_posts,
            "liked_post_ids": liked_post_ids,
            "saved_post_ids": saved_post_ids,
            "followed_user_ids": followed_user_ids,
            "default_gift": default_gift,
            "safe_mode_message": safe_mode_message,
        },
    )


def discover_view(request):
    return render(
        request,
        "posts/discover.html",
        {
            "hashtags": trending_hashtags(),
            "suggested_people": suggested_users_for(request.user),
            "suggested_communities": suggested_communities_for(request.user),
        },
    )


def search_view(request):
    query = request.GET.get("q", "").strip()
    users = Profile.objects.none()
    posts = Post.objects.none()
    stories = StoryItem.objects.none()
    live_rooms = LiveSession.objects.none()
    communities = Community.objects.none()
    if query:
        users = Profile.objects.select_related("user").filter(
            Q(username__icontains=query) | Q(display_name__icontains=query) | Q(bio__icontains=query)
        )[:20]
        posts = base_visible_posts(request.user).published().filter(
            Q(title__icontains=query)
            | Q(caption__icontains=query)
            | Q(author__profile__location__icontains=query)
            | Q(community__name__icontains=query)
        )[:20]
        stories = visible_stories_for(request.user).filter(
            Q(text_content__icontains=query)
            | Q(caption__icontains=query)
            | Q(author__profile__username__icontains=query)
            | Q(author__profile__display_name__icontains=query)
        )[:12]
        live_rooms = LiveSession.objects.select_related("host", "host__profile").filter(
            access_type=LiveSession.AccessType.PUBLIC
        ).filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(host__profile__username__icontains=query)
            | Q(host__profile__display_name__icontains=query)
        ).order_by("-is_featured", "-viewer_count", "-starts_at")[:12]
        communities = Community.objects.select_related("owner").filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(slug__icontains=query)
        )[:20]
    return render(
        request,
        "posts/search.html",
        {
            "query": query,
            "users": users,
            "posts": posts,
            "stories": stories,
            "live_rooms": live_rooms,
            "communities": communities,
        },
    )


@login_required(login_url="login")
def saved_posts_view(request):
    saves = (
        Save.objects.filter(user=request.user)
        .select_related("post", "post__author", "post__author__profile", "post__community")
        .prefetch_related("post__media", "post__poll__options")
        .order_by("-created_at")
    )
    saved_posts = [row.post for row in saves if row.post.status == Post.Status.PUBLISHED]
    media_saved_posts = [
        post
        for post in saved_posts
        if post.post_type in {Post.PostType.PHOTO, Post.PostType.VIDEO, Post.PostType.REEL}
    ]
    return render(
        request,
        "posts/saved.html",
        {"saved_posts": saved_posts, "media_saved_posts": media_saved_posts},
    )


@login_required(login_url="login")
def media_albums_view(request):
    media_posts = list(
        Post.objects.filter(author=request.user, status=Post.Status.PUBLISHED)
        .prefetch_related("media")
        .order_by("-published_at", "-created_at")
    )
    albums = [
        {
            "slug": "photos",
            "title": "Photos",
            "description": "Published photo posts and image-first updates.",
            "posts": [post for post in media_posts if post.post_type == Post.PostType.PHOTO],
        },
        {
            "slug": "videos",
            "title": "Videos",
            "description": "Longer clips and creator video drops.",
            "posts": [post for post in media_posts if post.post_type == Post.PostType.VIDEO],
        },
        {
            "slug": "reels",
            "title": "Reels",
            "description": "Short-form vertical video content.",
            "posts": [post for post in media_posts if post.post_type == Post.PostType.REEL],
        },
        {
            "slug": "flyers",
            "title": "Flyers",
            "description": "Promotional graphics and event artwork.",
            "posts": [post for post in media_posts if post.post_type == Post.PostType.FLYER],
        },
    ]
    return render(request, "posts/albums.html", {"albums": albums})


@login_required(login_url="login")
def media_album_detail_view(request, kind):
    album_map = {
        "photos": Post.PostType.PHOTO,
        "videos": Post.PostType.VIDEO,
        "reels": Post.PostType.REEL,
        "flyers": Post.PostType.FLYER,
    }
    if kind not in album_map:
        return redirect("media_albums")
    posts = list(
        Post.objects.filter(author=request.user, status=Post.Status.PUBLISHED, post_type=album_map[kind])
        .prefetch_related("media")
        .order_by("-published_at", "-created_at")
    )
    return render(
        request,
        "posts/album_detail.html",
        {"album_kind": kind, "album_title": kind.title(), "posts": posts},
    )


def hashtag_view(request, tag):
    normalized = tag if tag.startswith("#") else f"#{tag}"
    posts = [
        post
        for post in base_visible_posts(request.user).published()[:300]
        if normalized.lower() in [item.lower() for item in (post.hashtags or [])]
    ]
    paginator = Paginator(posts, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "posts/hashtag.html",
        {"tag": normalized, "page_obj": page_obj, "posts": page_obj.object_list},
    )


def people_suggestions_view(request):
    return render(
        request,
        "posts/people_suggestions.html",
        {"suggested_people": suggested_users_for(request.user, limit=30)},
    )


def community_suggestions_view(request):
    return render(
        request,
        "posts/community_suggestions.html",
        {"suggested_communities": suggested_communities_for(request.user, limit=30)},
    )


@login_required(login_url="login")
@require_http_methods(["POST"])
def like_post_view(request, uuid):
    post = get_object_or_404(Post, uuid=uuid)
    if not can_interact_with_post(request.user, post):
        return HttpResponseForbidden("You cannot react to this post.")
    reaction = request.POST.get("reaction_type") or Like.ReactionType.LIKE
    if reaction not in Like.ReactionType.values:
        reaction = Like.ReactionType.LIKE
    like, active = toggle_like(request.user, post, reaction)
    if active:
        from accounts.models import Notification, notify
        notify(
            recipient=post.author,
            notification_type=Notification.Type.LIKE,
            sender=request.user,
            message=f"@{request.user.username} liked your post.",
            target_url=reverse("post_detail", kwargs={"uuid": post.uuid}),
        )
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        post.refresh_from_db()
        return JsonResponse(
            {
                "liked": active,
                "like_count": post.like_count,
                "reaction_type": getattr(like, "reaction_type", ""),
            }
        )
    messages.success(request, "Reaction saved." if active else "Reaction removed.")
    return _post_action_redirect(request, post)


@login_required(login_url="login")
@require_http_methods(["POST"])
def save_post_toggle_view(request, uuid):
    post = get_object_or_404(Post, uuid=uuid)
    if not can_interact_with_post(request.user, post):
        return HttpResponseForbidden("You cannot save this post.")
    _, active = toggle_save(request.user, post)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        post.refresh_from_db()
        return JsonResponse({"saved": active, "save_count": post.save_count})
    messages.success(request, "Post saved." if active else "Post removed from saves.")
    return _post_action_redirect(request, post)


@login_required(login_url="login")
@require_http_methods(["POST"])
def share_post_view(request, uuid):
    post = get_object_or_404(Post, uuid=uuid)
    if not can_interact_with_post(request.user, post):
        return HttpResponseForbidden("You cannot share this post.")
    target = request.POST.get("target") or Share.Target.FEED
    if target not in Share.Target.values:
        target = Share.Target.FEED
    share = create_share(request.user, post, target=target, message=request.POST.get("message", ""))
    if not share:
        return HttpResponseForbidden("You cannot share this post.")
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        post.refresh_from_db()
        return JsonResponse({"status": "success", "share_count": post.share_count})
    messages.success(request, "Post shared.")
    return _post_action_redirect(request, post)


@require_http_methods(["POST"])
def track_post_view(request, uuid):
    post = get_object_or_404(Post, uuid=uuid)
    if request.user.is_authenticated and not can_interact_with_post(request.user, post):
        return HttpResponseForbidden("You cannot view-track this post.")
    if not request.user.is_authenticated and not Post.objects.visible_to(request.user).filter(pk=post.pk).exists():
        return HttpResponseForbidden("You cannot view-track this post.")
    if not request.session.session_key:
        request.session.save()
    view = track_view(
        request.user,
        post,
        session_key=request.session.session_key,
        duration_seconds=request.POST.get("duration_seconds", 0),
        completed=request.POST.get("completed") in {"1", "true", "on", "yes"},
    )
    if not view:
        return HttpResponseForbidden("You cannot view-track this post.")
    return JsonResponse({"ok": True, "view_count": Post.objects.get(pk=post.pk).view_count})


@login_required(login_url="login")
@require_http_methods(["POST"])
def add_comment_view(request, uuid):
    post = get_object_or_404(Post, uuid=uuid)
    if not can_interact_with_post(request.user, post):
        return HttpResponseForbidden("You cannot comment on this post.")
    body = request.POST.get("body", "").strip()
    if not body:
        messages.error(request, "Comment cannot be empty.")
        return _post_action_redirect(request, post)
    comment = add_comment(request.user, post, body)
    if not comment:
        return HttpResponseForbidden("You cannot comment on this post.")
    
    from accounts.models import Notification, notify
    if post.author_id != request.user.id:
        notify(
            recipient=post.author,
            notification_type=Notification.Type.COMMENT,
            sender=request.user,
            message=f"@{request.user.username} commented on your post.",
            target_url=reverse("post_detail", kwargs={"uuid": post.uuid}),
        )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "status": "success",
            "body": comment.body,
            "author": comment.author.username,
            "created_at": "Just now",
            "comment_count": post.comment_count
        })

    messages.success(request, "Comment added.")
    return _post_action_redirect(request, post)


@login_required(login_url="login")
@require_http_methods(["POST"])
def react_comment_view(request, id):
    comment = get_object_or_404(Comment.objects.select_related("post"), id=id)
    reaction_type = request.POST.get("reaction_type") or Like.ReactionType.LIKE
    if reaction_type not in Like.ReactionType.values:
        reaction_type = Like.ReactionType.LIKE
    _, active = toggle_comment_reaction(request.user, comment, reaction_type)
    messages.success(request, "Reply reaction saved." if active else "Reply reaction removed.")
    return _post_action_redirect(request, comment.post)


@login_required(login_url="login")
@require_http_methods(["POST"])
def reply_comment_view(request, id):
    parent = get_object_or_404(Comment.objects.select_related("post"), id=id, is_deleted=False)
    body = request.POST.get("body", "").strip()
    if not body:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"status": "error", "message": "Reply cannot be empty."}, status=400)
        messages.error(request, "Reply cannot be empty.")
        return _post_action_redirect(request, parent.post)
    comment = add_comment(request.user, parent.post, body, parent=parent)
    if not comment:
        return HttpResponseForbidden("You cannot reply to this comment.")
    from accounts.models import Notification, notify
    if parent.author_id != request.user.id:
        notify(
            recipient=parent.author,
            notification_type=Notification.Type.COMMENT,
            sender=request.user,
            message=f"@{request.user.username} replied to your comment.",
            target_url=reverse("post_detail", kwargs={"uuid": parent.post.uuid}),
        )
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        parent.post.refresh_from_db()
        return JsonResponse(
            {
                "status": "success",
                "body": comment.body,
                "author": comment.author.username,
                "comment_count": parent.post.comment_count,
            }
        )
    messages.success(request, "Reply added.")
    return _post_action_redirect(request, parent.post)


@login_required(login_url="login")
@require_http_methods(["POST"])
def delete_comment_view(request, id):
    comment = get_object_or_404(Comment.objects.select_related("post", "author"), id=id)
    if not delete_comment(request.user, comment):
        return HttpResponseForbidden("You cannot delete this comment.")
    messages.success(request, "Comment deleted.")
    return _post_action_redirect(request, comment.post)


@login_required(login_url="login")
@require_http_methods(["POST"])
def pin_comment_view(request, id):
    comment = get_object_or_404(Comment.objects.select_related("post", "author"), id=id)
    if not toggle_pin_comment(request.user, comment):
        return HttpResponseForbidden("Only the post owner can pin comments.")
    messages.success(request, "Pinned comment updated.")
    return _post_action_redirect(request, comment.post)


@login_required(login_url="login")
@require_http_methods(["POST"])
def report_post_view(request, uuid):
    post = get_object_or_404(Post, uuid=uuid)
    if not can_interact_with_post(request.user, post):
        return HttpResponseForbidden("You cannot report this post.")
    reason = request.POST.get("reason") or Report.Reason.OTHER
    if reason not in Report.Reason.values:
        reason = Report.Reason.OTHER
    report = create_report(request.user, post=post, reason=reason, details=request.POST.get("details", ""))
    if not report:
        return HttpResponseForbidden("You cannot report this post.")
    messages.success(request, "Report submitted.")
    return _post_action_redirect(request, post)


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def report_user_view(request, username):
    profile = get_object_or_404(Profile.objects.select_related("user"), username__iexact=username)
    if request.method == "POST":
        reason = request.POST.get("reason") or Report.Reason.OTHER
        if reason not in Report.Reason.values:
            reason = Report.Reason.OTHER
        create_report(request.user, reported_user=profile.user, reason=reason, details=request.POST.get("details", ""))
        messages.success(request, "Report submitted.")
        return redirect("profile_detail", username=profile.username)
    return render(request, "posts/report_user.html", {"profile": profile, "reasons": Report.Reason.choices})


def reel_quick_create_view(request):
    if request.method == "POST":
        return render(request, "posts/reel_quick_create.html", {"posted": True})
    return render(request, "posts/reel_quick_create.html")
