import logging
from pathlib import Path

from aiohttp.web_exceptions import HTTPNotFound
from aiohttp.web_fileresponse import FileResponse

logger = logging.getLogger('atoolbox.views')


async def spa_static_handler(request):
    """
    Handler suitable for use with single page apps.

    Use with web.get(r'/{path:.*}', spa_static_handler, name='static')

    modified from aiohttp_web_urldispatcher.StaticResource_handle
    """
    request_path = request.match_info['path'].lstrip('/')

    directory = request.app['static_dir']
    csp_headers = request.app.get('static_headers') or {}
    if request_path == '':
        return FileResponse(directory / 'index.html', headers=csp_headers)

    # probably other paths to return 404 for?
    if request_path.startswith('.well-known/'):
        raise HTTPNotFound()

    try:
        filename = Path(request_path)
        if filename.anchor:  # pragma: no cover
            # shouldn't happen on linux, but keep it just in case
            # request_path is an absolute name like
            # /static/\\machine_name\c$ or /static/D:\path
            # where the static dir is totally different
            raise RuntimeError('request path has anchor')
        filepath = directory.joinpath(filename).resolve()
        filepath.relative_to(directory)
    except Exception:  # pragma: no cover
        logger.warning('error resolving path %r', request_path, exc_info=True)
        filepath = directory

    if filepath.is_file():
        return FileResponse(filepath, headers=csp_headers)
    else:
        return FileResponse(directory / 'index.html', headers=csp_headers)
