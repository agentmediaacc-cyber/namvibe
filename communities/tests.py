from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Community, CommunityMembership


class CommunityFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tuli", password="StrongPass1")

    def test_create_community_adds_owner_membership(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("community_create"),
            {
                "name": "Windhoek Creators",
                "slug": "windhoek-creators",
                "description": "Creators around Windhoek.",
                "privacy": Community.Privacy.PUBLIC,
            },
        )

        community = Community.objects.get(slug="windhoek-creators")
        self.assertRedirects(response, reverse("community_detail", kwargs={"slug": community.slug}))
        self.assertEqual(community.owner, self.user)
        self.assertTrue(
            CommunityMembership.objects.filter(
                community=community,
                user=self.user,
                role=CommunityMembership.Role.OWNER,
                status=CommunityMembership.Status.ACTIVE,
            ).exists()
        )

    def test_join_public_community_toggles_membership(self):
        owner = User.objects.create_user(username="owner", password="StrongPass1")
        community = Community.objects.create(name="Oshana Events", slug="oshana-events", owner=owner)

        self.client.force_login(self.user)
        join_response = self.client.post(reverse("community_join", kwargs={"slug": community.slug}))
        community.refresh_from_db()

        self.assertRedirects(join_response, reverse("community_detail", kwargs={"slug": community.slug}))
        self.assertEqual(community.member_count, 1)
        self.assertTrue(CommunityMembership.objects.filter(community=community, user=self.user).exists())

        leave_response = self.client.post(reverse("community_join", kwargs={"slug": community.slug}))
        community.refresh_from_db()

        self.assertRedirects(leave_response, reverse("community_detail", kwargs={"slug": community.slug}))
        self.assertEqual(community.member_count, 0)
        self.assertFalse(CommunityMembership.objects.filter(community=community, user=self.user).exists())
