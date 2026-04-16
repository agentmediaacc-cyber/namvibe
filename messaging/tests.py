from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from unittest.mock import patch

from .models import Conversation, Message


class MessagingFlowTests(TestCase):
    def setUp(self):
        self.alina = User.objects.create_user(username="alina", email="alina@example.com", password="Pass12345")
        self.ben = User.objects.create_user(username="ben", email="ben@example.com", password="Pass12345")
        self.cato = User.objects.create_user(username="cato", email="cato@example.com", password="Pass12345")

    def test_start_chat_creates_direct_conversation(self):
        self.client.login(username="alina", password="Pass12345")

        response = self.client.get(reverse("messaging:start_chat", args=[self.ben.id]))

        conversation = Conversation.objects.get()
        self.assertEqual(set(conversation.participants.values_list("username", flat=True)), {"alina", "ben"})
        self.assertRedirects(
            response,
            f"{reverse('user_dashboard')}?section=messages&conversation={conversation.id}",
            fetch_redirect_response=False,
        )

    def test_send_message_requires_participant(self):
        conversation = Conversation.objects.create()
        conversation.participants.add(self.alina, self.ben)
        self.client.login(username="cato", password="Pass12345")

        response = self.client.post(reverse("messaging:send_message", args=[conversation.id]), {"text": "Nope"})

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Message.objects.exists())

    def test_send_text_reply_forward_and_attachment(self):
        conversation = Conversation.objects.create()
        conversation.participants.add(self.alina, self.ben)
        self.client.login(username="alina", password="Pass12345")

        first = self.client.post(reverse("messaging:send_message", args=[conversation.id]), {"text": "Hello 😀"})
        first_message = Message.objects.get()

        image = SimpleUploadedFile("hello.png", b"image-bytes", content_type="image/png")
        second = self.client.post(
            reverse("messaging:send_message", args=[conversation.id]),
            {"text": "Replying", "reply_to": first_message.id, "attachment": image},
        )
        reply = Message.objects.exclude(pk=first_message.pk).get()

        third = self.client.post(
            reverse("messaging:send_message", args=[conversation.id]),
            {"forward_to": first_message.id},
        )
        forwarded = Message.objects.exclude(pk__in=[first_message.pk, reply.pk]).get()

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(third.status_code, 302)
        self.assertEqual(reply.reply_to, first_message)
        self.assertEqual(reply.attachment_type, Message.ATTACHMENT_IMAGE)
        self.assertEqual(forwarded.forwarded_from, first_message)
        self.assertEqual(forwarded.text, "Hello 😀")

    def test_sender_can_soft_delete_own_message(self):
        conversation = Conversation.objects.create()
        conversation.participants.add(self.alina, self.ben)
        message = Message.objects.create(conversation=conversation, sender=self.alina, text="Delete me")
        self.client.login(username="alina", password="Pass12345")

        response = self.client.post(reverse("messaging:delete_message", args=[message.id]))

        message.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(message.is_deleted)
        self.assertEqual(message.text, "")

    def test_user_cannot_delete_someone_elses_message(self):
        conversation = Conversation.objects.create()
        conversation.participants.add(self.alina, self.ben)
        message = Message.objects.create(conversation=conversation, sender=self.ben, text="Keep me")
        self.client.login(username="alina", password="Pass12345")

        response = self.client.post(reverse("messaging:delete_message", args=[message.id]))

        message.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertFalse(message.is_deleted)
        self.assertEqual(message.text, "Keep me")

    @patch("accounts.views.get_posts_by_user", return_value=[])
    def test_dashboard_marks_incoming_messages_read(self, _posts):
        conversation = Conversation.objects.create()
        conversation.participants.add(self.alina, self.ben)
        message = Message.objects.create(conversation=conversation, sender=self.ben, text="Unread")
        self.client.login(username="alina", password="Pass12345")

        response = self.client.get(reverse("user_dashboard"), {"section": "messages", "conversation": conversation.id})

        message.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(message.read_at)

    @patch("accounts.views.get_posts_by_user", return_value=[])
    def test_dashboard_messages_can_render_without_selected_chat(self, _posts):
        conversation = Conversation.objects.create()
        conversation.participants.add(self.alina, self.ben)
        Message.objects.create(conversation=conversation, sender=self.ben, text="Pick me")
        self.client.login(username="alina", password="Pass12345")

        response = self.client.get(reverse("user_dashboard"), {"section": "messages"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a chat")
        self.assertContains(response, "Pick me")
