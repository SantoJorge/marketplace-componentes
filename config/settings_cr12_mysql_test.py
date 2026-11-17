from copy import deepcopy
from uuid import uuid4
from .settings import *
DATABASES = deepcopy(DATABASES)
if DATABASES["default"]["ENGINE"] != "django.db.backends.mysql": raise RuntimeError("CR12 requiere MySQL")
DATABASES["default"]["TEST"] = {"NAME": "test_mc_cr12_isolada", "MIGRATE": True}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
