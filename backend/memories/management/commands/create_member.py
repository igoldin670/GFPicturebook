from getpass import getpass
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "Create a non-admin member using a hidden password prompt."
    def add_arguments(self, parser):
        parser.add_argument("username")
    def handle(self, *args, **options):
        User = get_user_model()
        user = User(username=options["username"])
        password = getpass("Password: ")
        if password != getpass("Password again: "):
            raise CommandError("Passwords do not match.")
        try:
            user.full_clean(exclude=["password"])
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS("Member created."))
