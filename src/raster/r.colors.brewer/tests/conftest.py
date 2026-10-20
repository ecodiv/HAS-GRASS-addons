import os

import pytest

import grass.script as gs
from grass.tools import Tools


@pytest.fixture
def tools(tmp_path):
    """Tools object in an XY project with a small continuous raster."""
    project = tmp_path / "brewer_test"
    gs.create_project(project)
    with (
        gs.setup.init(project, env=os.environ.copy()) as session,
        Tools(session=session) as session_tools,
    ):
        session_tools.g_region(s=0, n=5, w=0, e=5, res=1)
        session_tools.r_mapcalc(expression="rast = row() + col()")
        yield session_tools
