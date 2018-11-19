import pytest

from aiohttptools.utils import slugify


@pytest.mark.parametrize(
    'input,output', [('This is the input ', 'this-is-the-input'), ('in^put', 'input'), ('in_put', 'in_put')]
)
def test_slugify(input, output):
    assert slugify(input) == output
