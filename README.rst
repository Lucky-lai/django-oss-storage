Django AliCloud OSS Storage
=========================

**django-oss-storage** provides a Django AliCloud OSS file storage.


Features
========

- Django file storage for AliCloud OSS
- Django static file storage for AliCloud OSS
- Works in Python 2 & 3

Installation
============

* Install

.. code-block:: bash

    $ pip install django-oss-storage

- Add ``'django_oss_storage'`` to your ``INSTALLED_APPS`` setting
- Set your ``DEFAULT_FILE_STORAGE`` setting to ``"django_oss_storage.backends.OssMediaStorage"``
- Set your ``STATICFILES_STORAGE`` setting to ``"django_oss_storage.backends.OssStaticStorage"``
- Configure your AliCloud OSS settings (Refer below).

Use the following settings for file storage.

.. code-block:: bash

    STATICFILES_STORAGE = 'django_oss_storage.backends.OssStaticStorage'

    DEFAULT_FILE_STORAGE = 'django_oss_storage.backends.OssMediaStorage'

Authentication settings
=======================

Use the following settings to authenticate with AliCloud OSS.

.. code-block:: bash

    # AliCloud access key ID
    OSS_ACCESS_KEY_ID = <Your Access Key ID>

    # AliCloud access key secret
    OSS_ACCESS_KEY_SECRET = <Your Access Key Secret>

    # AliCloud STS token, if not none,use sts auth
    ALIYUN_STS_TOKEN = None
File storage settings
=====================

Use the following settings to configure AliCloud OSS file storage.

.. code-block:: bash

    # The name of the bucket to store files in
    OSS_BUCKET_NAME = <Your bucket name>

    # Can set a home dir for the project
    OSS_HOME_DIR = <Some dir>

    # The URL of AliCloud OSS endpoint
    # Refer https://www.alibabacloud.com/help/zh/doc-detail/31837.htm for OSS Region & Endpoint
    OSS_ENDPOINT = <Your access endpoint>

    # If use in aliyun internal,add OSS_ENDPOINT_INTERNAL,OSS_USER_INTERNAL,可选的
    OSS_ENDPOINT_INTERNAL = <Your access internal endpoint>
    OSS_USE_INTERNAL = True



    # The default location for your files
    MEDIA_URL = '/media/'

Staticfiles storage settings
============================

All of the file storage settings are available for the staticfiles storage.

.. code-block:: bash

    # The default location for your static files
    STATIC_URL = '/static/'

staticfiles provides command 'collectstatic'. Run following command to collect all sub-folder 'static' of each app
and upload to STATIC_URL.

.. code-block:: bash

    $ python manage.py collectstatic


计划添加远程文件check功能，即保留本地文件，每次打开文件时，如果远端文件有更新才会尝试重新下载

Testing
=======

First set the required AccessKeyId, AccessKeySecret, endpoint and bucket information for the test through environment variables (**Do not use the bucket for the production environment**).
Take the Linux system for example:

.. code-block:: bash

    $ export OSS_ACCESS_KEY_ID=<AccessKeyId>
    $ export OSS_ACCESS_KEY_SECRET=<AccessKeySecret>
    $ export OSS_BUCKET_NAME=<bucket>
    $ export OSS_ENDPOINT=<endpoint>

Support and announcements
=========================

Downloads and bug tracking can be found at the `main project website <http://github.com/aliyun/django-oss-storage>`_.

License
=======

- `MIT <https://github.com/aliyun/django-oss-storage/blob/master/LICENSE>`_.
