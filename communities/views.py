from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CommunityForm
from .models import Community, CommunityMembership


def community_list_view(request):
    query = request.GET.get("q", "").strip()
    communities = Community.objects.select_related("owner").annotate(
        active_members=Count("memberships", filter=Q(memberships__status=CommunityMembership.Status.ACTIVE))
    )
    if query:
        communities = communities.filter(Q(name__icontains=query) | Q(description__icontains=query))
    communities = communities.order_by("-active_members", "-created_at")[:40]
    return render(request, "communities/community_list.html", {"communities": communities, "query": query})


def community_detail_view(request, slug):
    community = get_object_or_404(
        Community.objects.select_related("owner").prefetch_related("memberships__user"),
        slug__iexact=slug,
    )
    membership = None
    if request.user.is_authenticated:
        membership = CommunityMembership.objects.filter(community=community, user=request.user).first()
    return render(
        request,
        "communities/community_detail.html",
        {
            "community": community,
            "membership": membership,
            "can_manage": membership and membership.role in {
                CommunityMembership.Role.OWNER,
                CommunityMembership.Role.ADMIN,
                CommunityMembership.Role.MODERATOR,
            },
        },
    )


@login_required(login_url="login")
def community_create_view(request):
    form = CommunityForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        community = form.save(commit=False)
        community.owner = request.user
        community.save()
        CommunityMembership.objects.create(
            community=community,
            user=request.user,
            role=CommunityMembership.Role.OWNER,
            status=CommunityMembership.Status.ACTIVE,
        )
        community.member_count = 1
        community.save(update_fields=["member_count"])
        messages.success(request, "Community created.")
        return redirect("community_detail", slug=community.slug)
    return render(request, "communities/community_form.html", {"form": form})


@login_required(login_url="login")
@require_POST
def community_join_view(request, slug):
    community = get_object_or_404(Community, slug__iexact=slug)
    status = (
        CommunityMembership.Status.PENDING
        if community.privacy != Community.Privacy.PUBLIC
        else CommunityMembership.Status.ACTIVE
    )
    membership, created = CommunityMembership.objects.get_or_create(
        community=community,
        user=request.user,
        defaults={"status": status},
    )
    if not created and membership.status == CommunityMembership.Status.ACTIVE:
        membership.delete()
        community.member_count = CommunityMembership.objects.filter(
            community=community,
            status=CommunityMembership.Status.ACTIVE,
        ).count()
        community.save(update_fields=["member_count"])
        messages.success(request, "You left the community.")
    else:
        membership.status = status
        membership.save(update_fields=["status", "updated_at"])
        community.member_count = CommunityMembership.objects.filter(
            community=community,
            status=CommunityMembership.Status.ACTIVE,
        ).count()
        community.save(update_fields=["member_count"])
        messages.success(request, "Community request saved." if status == CommunityMembership.Status.PENDING else "You joined the community.")
    return redirect("community_detail", slug=community.slug)
