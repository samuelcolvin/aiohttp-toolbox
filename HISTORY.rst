.. :changelog:

History
-------

v0.4.0 (2019-04-09)
...................
* add ``spa_static_handler``

v0.3.3 (2019-03-21)
...................
* tweak ``patch_paths``

v0.3.2 (2019-03-15)
...................
* add ``patch_paths`` to settings
* ``exc_info`` adding middleware warning

v0.3.1 (2019-03-13)
...................
* add ``auto`` command to CLI

v0.3.0 (2019-03-08)
...................
* support ``arq >= 0.16`` and ``pydantic > 0.20``, #12

v0.2.2 (2019-02-13)
...................
* ``pg_middleware`` now respects ``pg_middleware_check`` function, fix #10


v0.2.1 (2019-02-07)
...................
* tweak imports, repr method for ``JsonErrors``

v0.2.0 (2019-02-04)
...................
* improved ``class_views``
* use ``argparse`` in cli
* fix logging setup
* allow patches to not be coroutines
* add ``skip_if_offline`` pytest decorator

v0.1.0 (2019-01-24)
...................
* improve logging output #9
* cleanup cli
* add commands: ``flush_redis`` and ``check_web``, implement ``wait_for_services`` #7

v0.0.11 (2018-12-27)
....................
* uprev aiohttp-session
* support latest aiohttp

v0.0.9 (2018-12-16)
...................
* allow settings and redis and postgres to be optional when creating apps

v0.0.8 (2018-12-12)
...................
* optional ``conn`` on ``View``
* improve ``raw_json_response``
* add ``JsonErrors.HTTPAccepted``
* rename ``parse_request -> parse_request_json``
* add ``parse_request_query``

v0.0.7 (2018-11-28)
...................
* improved CSRF

v0.0.6 (2018-11-22)
...................
* allow for requests without a ``conn``

v0.0.5 (2018-11-22)
...................
* improve bread, use ``handle`` not ``check_permissions``

v0.0.4 (2018-11-21)
...................
* add ``check_grecaptcha``
* improve middleware

v0.0.3 (2018-11-20)
...................
* tweak cli and how worker is run

v0.0.2 (2018-11-19)
...................
* change module name

v0.0.1 (2018-11-19)
...................
* first release
