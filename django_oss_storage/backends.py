# coding=utf-8

import os
import urllib

import six
import shutil

try:
    from urllib.parse import urljoin, urlsplit, urlunsplit
except ImportError:
    from urlparse import urljoin

from datetime import datetime
from django.core.files import File
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from django.core.files.storage import Storage
from django.conf import settings
from django.utils.encoding import force_text, force_bytes
from django.utils.deconstruct import deconstructible
from django.utils.timezone import utc
from tempfile import SpooledTemporaryFile, NamedTemporaryFile

import oss2.utils
import oss2.exceptions
from oss2 import Auth, Service, Bucket, ObjectIterator, StsAuth

from .defaults import logger


def _get_config(name):
    config = os.environ.get(name, getattr(settings, name, None))
    if config is not None:
        if isinstance(config, six.string_types):
            return config.strip()
        else:
            return config
    else:
        raise ImproperlyConfigured("'%s not found in env variables or setting.py" % name)


def _normalize_endpoint(endpoint):
    if not endpoint.startswith('http://') and not endpoint.startswith('https://'):
        return 'https://' + endpoint
    else:
        return endpoint


class OssError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


@deconstructible
class OssStorage(Storage):
    """
    Aliyun OSS Storage
    """

    def __init__(self, access_key_id=None, access_key_secret=None, end_point=None, bucket_name=None):
        self.access_key_id = access_key_id if access_key_id else _get_config('OSS_ACCESS_KEY_ID')
        self.access_key_secret = access_key_secret if access_key_secret else _get_config('OSS_ACCESS_KEY_SECRET')
        self.end_point = _normalize_endpoint(end_point if end_point else _get_config('OSS_ENDPOINT'))

        self.bucket_name = bucket_name if bucket_name else _get_config('OSS_BUCKET_NAME')

        sts_token = getattr(settings, 'ALIYUN_STS_TOKEN', None)
        # 这里表示如果有sts_token，需要使用stsauth进行鉴权
        if sts_token:
            self.auth = StsAuth(self.access_key_id, self.access_key_secret, sts_token)
        else:
            self.auth = Auth(self.access_key_id, self.access_key_secret)

        self.service = Service(self.auth, self.end_point)

        use_oss_internal = getattr(settings, 'OSS_USE_INTERNAL', None)
        # 这里表示，如果是阿里云的内网机器，默认走内网的end_point，否则使用外网的end_point
        # 使用内网end_point，速度快，不收费
        if use_oss_internal:
            self.end_point_internal = _normalize_endpoint(
                end_point if end_point else _get_config('OSS_ENDPOINT_INTERNAL'))
            self.bucket = Bucket(self.auth, self.end_point_internal, self.bucket_name)
        else:
            self.bucket = Bucket(self.auth, self.end_point, self.bucket_name)
        self.bucket_public = Bucket(self.auth, self.end_point, self.bucket_name)

        # try to get bucket acl to check bucket exist or not
        try:
            self.bucket.get_bucket_acl().acl
        except oss2.exceptions.NoSuchBucket:
            raise SuspiciousOperation("Bucket '%s' does not exist." % self.bucket_name)

    def _get_key_name(self, name):
        """
        Get the object key name in OSS, e.g.,
        location: /media/
        input   : test.txt
        output  : media/test.txt
        """
        base_path = force_text(self.location)
        final_path = urljoin(base_path + "/", name)
        name = os.path.normpath(final_path.lstrip('/'))
        name = name.replace('\\', '/')
        if six.PY2:
            name = name.encode('utf-8')
        return name

    def _open(self, name, mode='rb'):
        logger().debug("name: %s, mode: %s", name, mode)
        if mode != "rb":
            raise ValueError("OSS files can only be opened in read-only mode")

        target_name = self._get_key_name(name)
        logger().debug("target name: %s", target_name)
        try:
            # Load the key into a temporary file
            tmpf = NamedTemporaryFile()  # 10MB
            obj = self.bucket.get_object(target_name)
            logger().info("content length: %d, requestid: %s", obj.content_length, obj.request_id)
            if obj.content_length is None:
                shutil.copyfileobj(obj, tmpf)
            else:
                oss2.utils.copyfileobj_and_verify(obj, tmpf, obj.content_length, request_id=obj.request_id)
            tmpf.seek(0)
            return OssFile(tmpf, target_name, self)
        except oss2.exceptions.NoSuchKey:
            raise OssError("%s does not exist" % name)
        except:
            raise OssError("Failed to open %s" % name)

    def _save(self, name, content):
        target_name = self._get_key_name(name)
        logger().debug("target name: %s", target_name)
        logger().debug("content: %s", content)
        self.bucket.put_object(target_name, content)
        return os.path.normpath(name)

    def create_dir(self, dirname):
        target_name = self._get_key_name(dirname)
        if not target_name.endswith('/'):
            target_name += '/'

        self.bucket.put_object(target_name, '')

    def exists(self, name):
        target_name = self._get_key_name(name)
        logger().debug("name: %s, target name: %s", name, target_name)
        if name.endswith("/"):
            # This looks like a directory, but OSS has no concept of directories
            # need to check whether the key starts with this prefix
            result = self.bucket.list_objects(prefix=target_name, delimiter='', marker='', max_keys=1)
            if len(result.object_list) == 0:
                logger().debug("object list: %s", result.object_list)
            else:
                logger().debug("object list: %s", result.object_list[0].key)
            return bool(result.object_list)

        exist = self.bucket.object_exists(target_name)
        logger().debug("'%s' exist: %s", target_name, exist)
        if not exist:
            # It's not a file, but it might be a directory. Check again that it's not a directory.
            name2 = name + "/"
            logger().debug("to check %s", name2)
            return self.exists(name2)

        return exist

    def get_file_meta(self, name):
        name = self._get_key_name(name)
        return self.bucket.get_object_meta(name)

    def size(self, name):
        file_meta = self.get_file_meta(name)
        return file_meta.content_length

    def modified_time(self, name):
        file_meta = self.get_file_meta(name)
        return datetime.fromtimestamp(file_meta.last_modified)

    created_time = accessed_time = modified_time

    def get_modified_time(self, name):
        file_meta = self.get_file_meta(name)

        if settings.USE_TZ:
            return datetime.utcfromtimestamp(file_meta.last_modified).replace(tzinfo=utc)
        else:
            return datetime.fromtimestamp(file_meta.last_modified)

    get_created_time = get_accessed_time = get_modified_time

    def content_type(self, name):
        name = self._get_key_name(name)
        file_info = self.bucket.head_object(name)
        return file_info.content_type

    def listdir(self, name):
        if name == ".":
            name = ""
        name = self._get_key_name(name)
        if not name.endswith('/'):
            name += "/"
        logger().debug("name: %s", name)

        files = []
        dirs = []

        for obj in ObjectIterator(self.bucket, prefix=name, delimiter='/'):
            if obj.is_prefix():
                dirs.append(obj.key)
            else:
                files.append(obj.key)

        logger().debug("dirs: %s", list(dirs))
        logger().debug("files: %s", files)
        return dirs, files

    def url(self, name, expire=60 * 60):
        key = self._get_key_name(name)
        custom_domain = getattr(settings, 'OSS_CUSTOM_DOMAIN', None)
        # return self.bucket.sign_url('GET', key, expire)
        # 这里一般是提供给浏览器用的，所以走外网的end_point
        url = self.bucket_public.sign_url('GET', key, expire)
        url = url.replace('%2F', '/')
        if custom_domain:
            url_list = list(urlsplit(url))
            custom_domain_list = list(urlsplit(custom_domain))
            url_list[0] = custom_domain_list[0]
            url_list[1] = custom_domain_list[1]
            url = urlunsplit(url_list)
        return url

    def delete(self, name):
        name = self._get_key_name(name)
        logger().debug("delete name: %s", name)
        result = self.bucket.delete_object(name)

    def delete_with_slash(self, dirname):
        name = self._get_key_name(dirname)
        if not name.endswith('/'):
            name += '/'
        logger().debug("delete name: %s", name)
        result = self.bucket.delete_object(name)


class OssMediaStorage(OssStorage):
    def __init__(self):
        if hasattr(settings, "OSS_HOME_DIR"):
            self.location = urljoin(settings.OSS_HOME_DIR + '/', settings.MEDIA_URL.lstrip('/'))
        else:
            self.location = settings.MEDIA_URL
        logger().debug("locatin: %s", self.location)
        super(OssMediaStorage, self).__init__()

    def save(self, name, content, max_length=None):
        return super(OssMediaStorage, self)._save(name, content)


class OssStaticStorage(OssStorage):
    def __init__(self):
        if hasattr(settings, "OSS_HOME_DIR"):
            self.location = urljoin(settings.OSS_HOME_DIR + '/', settings.STATIC_URL.lstrip('/'))
        else:
            self.location = settings.STATIC_URL
        logger().info("locatin: %s", self.location)
        super(OssStaticStorage, self).__init__()

    def save(self, name, content, max_length=None):
        save_name = super()._save(name, content)
        object_name = self._get_key_name(name)
        # static file support public read
        public_read = getattr(settings, "OSS_STATIC_PUBLIC_READ", False)
        if public_read:
            self.bucket.put_object_acl(object_name, oss2.OBJECT_ACL_PUBLIC_READ)
        return save_name

    def _get_oss_host(self):
        if hasattr(settings, "OSS_CUSTOM_DOMAIN"):
            host = settings.OSS_CUSTOM_DOMAIN
        else:
            host = 'https://{bucket}.{oss_endpoint}'.format(bucket=self.bucket_name,
                                                            oss_endpoint=_get_config('OSS_ENDPOINT'))
        return host

    def url(self, name, expire=60 * 60):
        key = self._get_key_name(name)
        # static file support public read
        public_read = getattr(settings, "OSS_STATIC_PUBLIC_READ", False)
        if public_read:
            host = self._get_oss_host()
            url = urljoin(host, key)
        else:
            url = super().url(name, expire)
        return url


class OssFile(File):
    """
    A file returned from AliCloud OSS
    """

    def __init__(self, content, name, storage):
        super(OssFile, self).__init__(content, name)
        self._storage = storage

    def open(self, mode="rb"):
        if self.closed:
            self.file = self._storage.open(self.name, mode).file
        return super(OssFile, self).open(mode)
