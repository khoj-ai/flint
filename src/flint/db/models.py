from flint.manage import init_django
init_django()

import uuid

from django.db import models
from django.contrib.auth.models import User
from phonenumber_field.modelfields import PhoneNumberField
from django.db.models.signals import post_save
from django.dispatch import receiver

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.__class__.__name__}({self.id})"

    def __repr__(self):
        return self.__str__()
    
class KhojUser(BaseModel):
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = PhoneNumberField()
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    class Meta:
        db_table = "khoj_user"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.__class__.__name__}({self.id})"
    
@receiver(post_save, sender=User)
def create_khoj_user(sender, instance, created, **kwargs):
    if created:
        KhojUser.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_khoj_user(sender, instance, **kwargs):
    instance.khojuser.save()


class Conversation(BaseModel):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False, related_name="conversations")
    user_message = models.TextField()
    bot_message = models.TextField()

    class Meta:
        db_table = "conversation"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.__class__.__name__}({self.id})"